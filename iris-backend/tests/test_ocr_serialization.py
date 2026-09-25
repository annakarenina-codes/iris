"""Regression coverage for EasyOCR's non-native coordinate types."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from flask import Flask, jsonify
from pipeline.ocr import _parse_easyocr_result


class OcrSerializationTests(unittest.TestCase):
    def test_numpy_coordinates_serialize_in_public_and_debug_fields(self):
        for dtype in (np.int32, np.int64, np.float32, np.float64):
            with self.subTest(dtype=dtype):
                bbox = np.array([[1, 2], [30, 2], [30, 15], [1, 15]], dtype=dtype)
                regions = _parse_easyocr_result([(bbox, "Sample claim", np.float32(0.9))])
                self.assertEqual(regions[0]["bbox"], bbox.tolist())
                app = Flask(__name__)
                with app.app_context():
                    response = jsonify(ocr_regions=regions, debug={"ocr": {"regions": regions}})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(json.loads(response.get_data())["ocr_regions"], regions)

    def test_native_coordinates_and_empty_results(self):
        regions = _parse_easyocr_result([([[1, 2], [3, 2], [3, 4], [1, 4]], "Text", 0.8)])
        json.dumps(regions, allow_nan=False)
        self.assertEqual(_parse_easyocr_result([]), [])


if __name__ == "__main__":
    unittest.main()
