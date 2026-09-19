import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.ocr_layout import select_content_regions


def region(text, y, height=60):
    return {"text": text, "bbox": [[0, y], [900, y], [900, y + height], [0, y + height]]}


class LayoutTests(unittest.TestCase):
    def test_observed_image_geometry(self):
        # Heights, vertical positions and confidences observed in the supplied image.
        observations = [
            ("LOCAL", 64, 78, .9963), ("NEWS", 68, 76, .9986),
            ("4", 374, 76, .1784), ("2", 408, 347, .7475),
            ("9,8,", 787, 203, .1866),
            ("MARIEL PADILLA'S CLAIM THAT", 1149, 101, .6319),
            ('HER HUSBAND "PASSED A', 1256, 102, .7488),
            ('LAW" BEFORE BECOMING A', 1364, 102, .6026),
            ("LEGISLATOR IS FALSE", 1468, 104, .8304),
            ("THE SERVANT'S", 1635, 48, .8099), ("CHRONICLES", 1670, 50, .7893),
        ]
        regions = [dict(region(text, y, height), confidence=confidence)
                   for text, y, height, confidence in observations]
        selected, excluded = select_content_regions(regions)
        self.assertEqual(selected, regions[5:9])
        self.assertEqual(len(excluded), 7)

    def test_short_claim_with_smaller_footer(self):
        claim = region("DOH: Dengue cases up 40%", 300)
        selected, _ = select_content_regions([claim, region("Example Publisher", 900, 20)])
        self.assertEqual(selected, [claim])

    def test_headline_keeps_negation_and_removes_separate_branding(self):
        headline = [region("MARIEL PADILLA'S CLAIM THAT", 1000),
                    region('HER HUSBAND "PASSED A LAW"', 1080),
                    region("BEFORE BECOMING A LEGISLATOR IS FALSE", 1160)]
        selected, excluded = select_content_regions(
            [region("LOCAL NEWS", 20), region("4 2 9,8", 200, 15)]
            + headline + [region("THE SERVANT'S CHRONICLES", 1400, 25)])
        self.assertEqual(selected, headline)
        self.assertEqual(len(excluded), 3)
        self.assertTrue(selected[-1]["text"].endswith("IS FALSE"))

    def test_ambiguous_layout_and_qualifiers_are_retained(self):
        headline = region("This is a sufficiently long headline about an event that needs verification", 100)
        for extra in (region("NOT CONFIRMED", 900, 20),
                      region("Another substantial paragraph with enough words to represent a second distinct assertion", 900, 20)):
            regions = [headline, extra]
            self.assertEqual(select_content_regions(regions), (regions, []))


if __name__ == "__main__":
    unittest.main()
