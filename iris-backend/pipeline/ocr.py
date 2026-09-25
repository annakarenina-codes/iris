"""
OCR helpers for IRIS image-to-text verification.

This module extracts readable text from a user-submitted image. It does not
judge whether the image is authentic, edited, AI-generated, or contextually
accurate.
"""

from __future__ import annotations

from iris_trace.core import traced, event, CURRENT, span

import base64
import binascii
import os
import re
from io import BytesIO
from typing import Dict, List, Optional, Tuple


MAX_IMAGE_BYTES = int(os.getenv("IRIS_OCR_MAX_IMAGE_BYTES", str(8 * 1024 * 1024)))
MAX_IMAGE_PIXELS = int(os.getenv("IRIS_OCR_MAX_IMAGE_PIXELS", str(16_000_000)))
MAX_IMAGE_SIDE = int(os.getenv("IRIS_OCR_MAX_IMAGE_SIDE", "1800"))
MIN_NORMALIZED_SIDE = int(os.getenv("IRIS_OCR_MIN_NORMALIZED_SIDE", "900"))
OCR_MIN_WORDS = int(os.getenv("IRIS_OCR_MIN_WORDS", "10"))
OCR_LOW_CONFIDENCE_THRESHOLD = float(os.getenv("IRIS_OCR_LOW_CONFIDENCE", "0.45"))
OCR_MAX_REGIONS = int(os.getenv("IRIS_OCR_MAX_REGIONS", "50"))

DEFAULT_LANGUAGES = ("en", "tl")
SUPPORTED_FORMATS = {"jpeg", "png", "webp", "bmp", "tiff"}
_READER_CACHE = {}


def _image_format_from_magic(image_bytes: bytes) -> Optional[str]:
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return "webp"
    if image_bytes.startswith(b"BM"):
        return "bmp"
    if image_bytes.startswith(b"II*\x00") or image_bytes.startswith(b"MM\x00*"):
        return "tiff"
    return None


def _error(status: str, message: str, http_status: int = 400) -> Dict[str, object]:
    return {
        "status": status,
        "message": message,
        "http_status": http_status,
    }


def validate_image_bytes(image_bytes: bytes) -> Dict[str, object]:
    """Performs cheap validation before Pillow/EasyOCR touches the image."""
    if not image_bytes:
        return _error("missing_image", "No image data was provided.")

    if len(image_bytes) > MAX_IMAGE_BYTES:
        return _error(
            "image_too_large",
            f"Image is larger than the {MAX_IMAGE_BYTES} byte OCR limit.",
            413,
        )

    image_format = _image_format_from_magic(image_bytes)
    if image_format not in SUPPORTED_FORMATS:
        return _error(
            "unsupported_image_type",
            "Unsupported image type. Use PNG, JPEG, WEBP, BMP, or TIFF.",
        )

    return {
        "status": "ok",
        "image_format": image_format,
        "byte_size": len(image_bytes),
    }


def decode_base64_image(base64_text: str) -> Dict[str, object]:
    """Decodes a raw base64 string or data URI into image bytes."""
    if not isinstance(base64_text, str) or not base64_text.strip():
        return _error("missing_image", "No base64 image data was provided.")

    payload = base64_text.strip()
    if "," in payload and payload.lower().startswith("data:"):
        payload = payload.split(",", 1)[1]

    payload = re.sub(r"\s+", "", payload)

    try:
        image_bytes = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        return _error("invalid_base64", "Image data is not valid base64.")

    validation = validate_image_bytes(image_bytes)
    if validation["status"] != "ok":
        return validation

    validation["image_bytes"] = image_bytes
    return validation


def _import_ocr_dependencies() -> Dict[str, object]:
    missing = []

    try:
        from PIL import Image, ImageEnhance, ImageOps, UnidentifiedImageError
    except ImportError:
        Image = None
        ImageEnhance = None
        ImageOps = None
        UnidentifiedImageError = None
        missing.append("Pillow")

    try:
        import cv2
    except ImportError:
        cv2 = None
        missing.append("opencv-python-headless")

    try:
        import numpy as np
    except ImportError:
        np = None
        missing.append("numpy")

    try:
        import easyocr
    except ImportError:
        easyocr = None
        missing.append("easyocr")

    return {
        "missing": missing,
        "Image": Image,
        "ImageEnhance": ImageEnhance,
        "ImageOps": ImageOps,
        "UnidentifiedImageError": UnidentifiedImageError,
        "cv2": cv2,
        "np": np,
        "easyocr": easyocr,
    }


def _resize_for_ocr(image, image_module, max_side: int):
    width, height = image.size
    longest_side = max(width, height)
    shortest_side = min(width, height)

    scale = 1.0
    if longest_side > max_side:
        scale = max_side / longest_side
    elif longest_side < MIN_NORMALIZED_SIDE:
        scale = min(2.0, MIN_NORMALIZED_SIDE / max(1, longest_side))

    if scale == 1.0:
        return image, {
            "resized": False,
            "scale": 1.0,
            "normalized_size": [width, height],
        }

    new_width = max(1, int(width * scale))
    new_height = max(1, int(height * scale))
    resampling = getattr(getattr(image_module, "Resampling", None), "LANCZOS", None)

    if resampling is None:
        resampling = getattr(image_module, "LANCZOS", 1)

    resized = image.resize((new_width, new_height), resampling)
    return resized, {
        "resized": True,
        "scale": round(scale, 3),
        "normalized_size": [new_width, new_height],
        "original_shortest_side": shortest_side,
    }


@traced('image.preprocess', dependency=False)
def _preprocess_image(image_bytes: bytes, dependencies: Dict[str, object]) -> Dict[str, object]:
    Image = dependencies["Image"]
    ImageEnhance = dependencies["ImageEnhance"]
    ImageOps = dependencies["ImageOps"]
    UnidentifiedImageError = dependencies["UnidentifiedImageError"]
    cv2 = dependencies["cv2"]
    np = dependencies["np"]

    try:
        image = Image.open(BytesIO(image_bytes))
        image.load()
    except Exception as error:
        if UnidentifiedImageError is not None and isinstance(error, UnidentifiedImageError):
            return _error("corrupt_image", "The image file is corrupt or unreadable.")

        return _error("corrupt_image", f"The image could not be opened: {error}")

    original_width, original_height = image.size
    pixel_count = original_width * original_height

    if pixel_count > MAX_IMAGE_PIXELS:
        return _error(
            "image_too_large",
            f"Image is larger than the {MAX_IMAGE_PIXELS} pixel OCR limit.",
            413,
        )

    original_format = (image.format or "unknown").lower()
    image = image.convert("RGB")
    image, resize_metadata = _resize_for_ocr(image, Image, MAX_IMAGE_SIDE)

    grayscale = ImageOps.grayscale(image)
    grayscale = ImageOps.autocontrast(grayscale)
    grayscale = ImageEnhance.Contrast(grayscale).enhance(1.4)

    image_array = np.array(grayscale)
    denoised = cv2.fastNlMeansDenoising(image_array, None, 10, 7, 21)
    normalized = cv2.equalizeHist(denoised)

    return {
        "status": "ok",
        "image": normalized,
        "metadata": {
            "original_format": original_format,
            "original_size": [original_width, original_height],
            "byte_size": len(image_bytes),
            "preprocessing": {
                "grayscale": True,
                "autocontrast": True,
                "contrast_factor": 1.4,
                "denoised": True,
                "histogram_equalized": True,
                **resize_metadata,
            },
        },
    }


def _gpu_enabled() -> bool:
    return os.getenv("IRIS_OCR_GPU", "false").lower() in {"1", "true", "yes"}


@traced('image.reader', dependency=False)
def _get_reader(easyocr, languages: Tuple[str, ...]):
    gpu = _gpu_enabled()
    cache_key = (languages, gpu)

    if cache_key not in _READER_CACHE:
        _READER_CACHE[cache_key] = easyocr.Reader(
            list(languages),
            gpu=gpu,
            verbose=False,
        )

    return _READER_CACHE[cache_key]


def _region_bounds(region: Dict[str, object]) -> Tuple[float, float, float, float]:
    xs = []
    ys = []

    for point in region.get("bbox") or []:
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            xs.append(float(point[0]))
            ys.append(float(point[1]))

    return (min(xs or [0.0]), min(ys or [0.0]), max(xs or [0.0]), max(ys or [0.0]))


def _region_position(region: Dict[str, object]) -> Tuple[float, float]:
    left, top, _, _ = _region_bounds(region)
    return (top, left)


LINE_TOLERANCE = 0.6
# How close two boxes must be before the reader treats them as one. The default merges
# neighbouring words in a tightly set graphic, which turned "MILF AT INC, Nagdeklara ng suporta"
# into "MILFATINC, NAGDEKLARANG SUPORTAKAY" and left held-out post H19 unsearchable.
BOX_MERGE_WIDTH = 0.1


def reading_order(regions: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """
    Orders text boxes the way the picture is read: each line left to right, lines top to bottom.

    Ordering by the top edge of every box put the words of one line in the order their boxes
    happened to start, which scrambled a quotation into nonsense whenever the letters of a line
    sat at slightly different heights (held-out post H18, where half the statement was lost).
    """
    lines: List[Dict[str, object]] = []
    for region in sorted(regions, key=_region_position):
        _, top, _, bottom = _region_bounds(region)
        centre, height = (top + bottom) / 2, max(1.0, bottom - top)
        for line in lines:
            if abs(centre - line["centre"]) <= LINE_TOLERANCE * max(height, line["height"]):
                line["regions"].append(region)
                line["centre"] = sum((_region_bounds(r)[1] + _region_bounds(r)[3]) / 2
                                     for r in line["regions"]) / len(line["regions"])
                line["height"] = max(line["height"], height)
                break
        else:
            lines.append({"centre": centre, "height": height, "regions": [region]})

    lines.sort(key=lambda line: line["centre"])
    ordered = []
    for line in lines:
        ordered.extend(sorted(line["regions"], key=lambda r: _region_bounds(r)[0]))
    return ordered


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def _confidence(regions: List[Dict[str, object]]) -> Optional[float]:
    if not regions:
        return None

    weighted_total = 0.0
    weight_sum = 0
    for region in regions:
        text_weight = max(1, _word_count(str(region.get("text") or "")))
        weighted_total += float(region.get("confidence") or 0.0) * text_weight
        weight_sum += text_weight

    return round(weighted_total / max(1, weight_sum), 4)


# A reader looking at a stylised graphic returns stray marks as words: an opening quotation
# mark comes back as "66", a decorative bar as ">", a clipped letter as a lone "D". They travel
# into the claim and are checked as if the post had said them (held-out post H18 became
# "66 TWO KINDS ONLY ArGD DEFENDING KAY D BBM").
QUOTE_ARTEFACT = re.compile(r"^(?:6{2,}|9{2,})$")
OPENS_A_WORD = r"\w" + "\"'(\u201c\u2018"
CLOSES_A_WORD = r"\w" + "\".,:;!?)'\u201d\u2019"
EDGE_JUNK = re.compile("^[^" + OPENS_A_WORD + "]+|[^" + CLOSES_A_WORD + "]+$")
KEPT_SINGLE_LETTERS = {"a", "i"}


def _keep_token(token: str) -> bool:
    if not token or QUOTE_ARTEFACT.match(token):
        return False
    # A lone letter is a fragment of a word the reader lost; a lone digit can be a real figure.
    return not (len(token) == 1 and token.isalpha() and token.lower() not in KEPT_SINGLE_LETTERS)


def clean_region_text(text: str) -> str:
    """Removes the stray marks a reader returns as words, keeping the words themselves."""
    kept = []
    for token in str(text or "").split():
        token = EDGE_JUNK.sub("", token)
        if _keep_token(token):
            kept.append(token)
    return " ".join(kept)


@traced('image.regions', dependency=False)
def _parse_easyocr_result(raw_result) -> List[Dict[str, object]]:
    regions = []

    for item in raw_result:
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            continue

        bbox, text, confidence = item[:3]
        text = clean_region_text(_clean_text(str(text)))
        if not text:
            continue

        regions.append({
            "text": text,
            "confidence": round(float(confidence), 4),
            # EasyOCR coordinates can be NumPy scalars, which Flask cannot serialize.
            "bbox": [[float(coordinate) for coordinate in point] for point in bbox],
        })

    regions = reading_order(regions)
    return regions[:OCR_MAX_REGIONS]


@traced('image.ocr', dependency=True)
def extract_text_from_image(
    image_bytes: bytes,
    languages: Tuple[str, ...] = DEFAULT_LANGUAGES,
) -> Dict[str, object]:
    """
    Extracts text from an image using EasyOCR.

    Returns a stable dictionary even when OCR dependencies are not installed.
    """
    validation = validate_image_bytes(image_bytes)
    if validation["status"] != "ok":
        return {
            "status": validation["status"],
            "text": "",
            "word_count": 0,
            "confidence": None,
            "low_confidence": True,
            "warnings": [validation["message"]],
            "error": validation["message"],
            "image": {
                "byte_size": len(image_bytes or b""),
                "format": validation.get("image_format"),
            },
            "regions": [],
            "image_authenticity_checked": False,
        }

    dependencies = _import_ocr_dependencies()
    if dependencies["missing"]:
        missing = ", ".join(dependencies["missing"])
        return {
            "status": "missing_dependency",
            "text": "",
            "word_count": 0,
            "confidence": None,
            "low_confidence": True,
            "warnings": [f"Missing OCR dependencies: {missing}."],
            "error": f"Missing OCR dependencies: {missing}.",
            "image": {
                "byte_size": validation["byte_size"],
                "format": validation["image_format"],
            },
            "regions": [],
            "image_authenticity_checked": False,
        }

    preprocessed = _preprocess_image(image_bytes, dependencies)
    if preprocessed["status"] != "ok":
        return {
            "status": preprocessed["status"],
            "text": "",
            "word_count": 0,
            "confidence": None,
            "low_confidence": True,
            "warnings": [preprocessed["message"]],
            "error": preprocessed["message"],
            "image": {
                "byte_size": validation["byte_size"],
                "format": validation["image_format"],
            },
            "regions": [],
            "image_authenticity_checked": False,
        }

    warnings = []
    easyocr = dependencies["easyocr"]

    try:
        reader = _get_reader(easyocr, tuple(languages))
    except Exception as error:
        if tuple(languages) != ("en",):
            warnings.append(
                "Filipino OCR language support could not initialize; retried with English only."
            )
            try:
                reader = _get_reader(easyocr, ("en",))
            except Exception as retry_error:
                return {
                    "status": "error",
                    "text": "",
                    "word_count": 0,
                    "confidence": None,
                    "low_confidence": True,
                    "warnings": warnings,
                    "error": f"EasyOCR initialization failed: {retry_error}",
                    "image": preprocessed["metadata"],
                    "regions": [],
                    "image_authenticity_checked": False,
                }
        else:
            return {
                "status": "error",
                "text": "",
                "word_count": 0,
                "confidence": None,
                "low_confidence": True,
                "warnings": warnings,
                "error": f"EasyOCR initialization failed: {error}",
                "image": preprocessed["metadata"],
                "regions": [],
                "image_authenticity_checked": False,
            }

    try:
        with span('image.recognition', {'image': preprocessed['metadata']}) as recognition:
            raw_result = reader.readtext(preprocessed["image"], width_ths=BOX_MERGE_WIDTH)
            if recognition is not None:
                recognition['output'] = raw_result
    except Exception as error:
        return {
            "status": "error",
            "text": "",
            "word_count": 0,
            "confidence": None,
            "low_confidence": True,
            "warnings": warnings,
            "error": f"EasyOCR text extraction failed: {error}",
            "image": preprocessed["metadata"],
            "regions": [],
            "image_authenticity_checked": False,
        }

    from pipeline.ocr_layout import select_content_regions

    trace = CURRENT.get()
    if trace is not None:
        trace.artifact('image', image_bytes, 'application/octet-stream')
    raw_regions = _parse_easyocr_result(raw_result)
    raw_text = _clean_text(" ".join(region["text"] for region in raw_regions))
    if trace is not None:
        trace.artifact('ocr_regions', raw_regions)
    regions, excluded_regions = select_content_regions(raw_regions)
    event('ocr.selection', raw_regions=raw_regions, retained=regions, excluded=excluded_regions, image=preprocessed['metadata'])
    text = _clean_text(" ".join(region["text"] for region in regions))
    words = _word_count(text)
    confidence = _confidence(regions)

    if not text:
        return {
            "status": "no_text",
            "text": "",
            "word_count": 0,
            "confidence": confidence,
            "low_confidence": True,
            "warnings": warnings + ["No readable text was extracted from the image."],
            "error": None,
            "image": preprocessed["metadata"],
            "regions": regions,
            "image_authenticity_checked": False,
        }

    if words < OCR_MIN_WORDS:
        warnings.append(
            f"OCR extracted only {words} words, below the {OCR_MIN_WORDS}-word review threshold."
        )

    if confidence is not None and confidence < OCR_LOW_CONFIDENCE_THRESHOLD:
        warnings.append(
            f"OCR average confidence {confidence} is below the {OCR_LOW_CONFIDENCE_THRESHOLD} threshold."
        )

    return {
        "status": "ok",
        "text": text,
        "raw_text": raw_text,
        "raw_regions": raw_regions,
        "excluded_regions": excluded_regions,
        "word_count": words,
        "confidence": confidence,
        "low_confidence": bool(warnings),
        "warnings": warnings,
        "error": None,
        "image": preprocessed["metadata"],
        "regions": regions,
        "image_authenticity_checked": False,
    }
