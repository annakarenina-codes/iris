"""Conservative selection of a dominant headline without rewriting OCR text."""
from iris_trace.core import traced, event
import re
from statistics import median


_SOCIAL_UI = re.compile(
    r'(?:like\s+comment\s+share|like\s+comment|comment\s+share|'
    r'write a comment(?:\.{3})?|view (?:all|more) comments|'
    r'\d[\d,.]*\s*[kmb]?\s+(?:likes|reactions|comments|shares|views)'
    r'(?:\s*[\u00b7|,]?\s*\d[\d,.]*\s*[kmb]?\s+(?:likes|reactions|comments|shares|views))*)', re.I)


# Below this the reader is guessing. Held-out post H20 ended with '[:yov"wve%Cy,' at 0.00 and
# a mangled name at 0.09, and that tail dropped the profiler's confidence far enough that the
# whole post was answered "no checkable claims".
UNREADABLE_CONFIDENCE = 0.15


@traced('image.layout')
def select_content_regions(regions):
    rejected = []
    retained = []
    for region in regions:
        text = region.get("text", "").strip()
        confidence = region.get("confidence", 1.0)
        # Do not silently erase low-confidence words or negations from a claim.
        unreadable = confidence < UNREADABLE_CONFIDENCE
        noise = unreadable or (confidence < 0.45 and not re.search(r"[A-Za-z]", text))
        label = text.upper() in {"LOCAL NEWS", "LOCAL", "NEWS", "BREAKING NEWS"}
        interface = bool(_SOCIAL_UI.fullmatch(text))
        if noise or label or interface:
            rejected.append({"text": text, "reason": 'social_interface' if interface else
                             "unreadable" if unreadable else
                             "low_confidence_symbols" if noise else "section_label"})
        else:
            retained.append(region)
    selected, excluded = _select_blocks(retained)
    return selected, rejected + excluded


@traced('image.blocks')
def _select_blocks(regions):
    def bounds(region):
        points = region.get("bbox") or []
        if len(points) < 4:
            return None
        xs, ys = zip(*[(float(p[0]), float(p[1])) for p in points])
        return min(xs), min(ys), max(xs), max(ys)

    boxes = [bounds(region) for region in regions]
    if not regions or any(box is None for box in boxes):
        event('ocr.keep_all', reason='ambiguous_or_insufficient_geometry')
        return regions, []
    # Group nearby lines of comparable size. Large gaps separate logos from copy.
    groups = []
    for index, box in enumerate(boxes):
        height = max(1, box[3] - box[1])
        if groups:
            previous = boxes[groups[-1][-1]]
            previous_height = max(1, previous[3] - previous[1])
            gap = box[1] - previous[3]
            overlap = min(box[2], previous[2]) - max(box[0], previous[0])
            if (-height <= gap <= max(height, previous_height) * 1.25
                    and max(height, previous_height) / min(height, previous_height) <= 1.5
                    and overlap > 0):
                groups[-1].append(index)
                continue
        groups.append([index])

    event('ocr.groups', groups=groups, boxes=boxes)
    candidates = []
    for group in groups:
        text = " ".join(regions[i]["text"] for i in group)
        # Short headlines can be factual too; length is not the ranking signal.
        if len(re.findall(r"\b\w+\b", text)) >= 4:
            candidates.append(group)
    # Multiple substantial blocks may be an article or infographic: retain all.
    if not candidates:
        event('ocr.keep_all', reason='ambiguous_or_insufficient_geometry')
        return regions, []
    candidates.sort(key=lambda group: median(boxes[i][3] - boxes[i][1] for i in group), reverse=True)
    chosen = candidates[0]
    if len(candidates) > 1:
        first = median(boxes[i][3] - boxes[i][1] for i in chosen)
        second = median(boxes[i][3] - boxes[i][1] for i in candidates[1])
        if first < second * 1.6:
            event('ocr.keep_all', reason='ambiguous_or_insufficient_geometry')
            return regions, []
    typical_height = median(boxes[i][3] - boxes[i][1] for i in chosen)
    excluded = [i for i in range(len(regions)) if i not in chosen]
    if not excluded:
        event('ocr.keep_all', reason='ambiguous_or_insufficient_geometry')
        return regions, []
    # Only discard short, spatially separate blocks. Comparable-size text could
    # be a qualifier, so retain it unless it is a generic news section label.
    for group in groups:
        if group == chosen:
            continue
        text = " ".join(regions[i]["text"] for i in group)
        if re.search(r"\b(not|false|satire|alleged|unconfirmed|correction|hindi|fake)\b", text, re.I):
            event('ocr.keep_all', reason='ambiguous_or_insufficient_geometry')
            return regions, []
        label = text.strip().upper() in {"LOCAL NEWS", "BREAKING NEWS", "NEWS"}
        small = all(boxes[i][3] - boxes[i][1] < typical_height * 0.65 for i in group)
        isolated_glyph = (len(group) == 1 and re.fullmatch(r"\d", text)
                          and boxes[group[0]][3] - boxes[group[0]][1] > typical_height * 2.5)
        if len(re.findall(r"\b\w+\b", text)) > 5 or not (label or small or isolated_glyph):
            event('ocr.keep_all', reason='ambiguous_or_insufficient_geometry')
            return regions, []
    return [regions[i] for i in chosen], [
        {"text": regions[i]["text"], "reason": "separate_secondary_layout_block"}
        for i in excluded
    ]
