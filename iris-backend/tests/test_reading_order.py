"""Reading a picture line by line: the order the words are in, not the order the boxes start."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.ocr import reading_order


def box(text, left, top, right, bottom):
    return {'text': text, 'confidence': 0.9,
            'bbox': [[left, top], [right, top], [right, bottom], [left, bottom]]}


def read(regions):
    return ' '.join(r['text'] for r in reading_order(regions))


class ReadingOrderTests(unittest.TestCase):
    def test_words_of_one_line_read_left_to_right(self):
        # Tops differ by a few pixels, as they do in a real statement graphic.
        scrambled = [box('mandate', 600, 14, 760, 60), box('no', 300, 10, 360, 58),
                     box('have', 380, 16, 500, 62), box('They', 100, 12, 280, 60)]
        self.assertEqual(read(scrambled), 'They no have mandate'.replace('no have', 'no have'))

    def test_lines_read_top_to_bottom(self):
        regions = [box('second line', 100, 120, 500, 170), box('first line', 100, 20, 500, 70)]
        self.assertEqual(read(regions), 'first line second line')

    def test_a_tall_headline_is_not_merged_with_the_line_below(self):
        regions = [box('HEADLINE', 100, 10, 700, 90), box('caption', 100, 100, 400, 130)]
        self.assertEqual(read(regions), 'HEADLINE caption')

    def test_boxes_at_slightly_different_heights_stay_one_line(self):
        # H18: the quote's words sat at different heights and were read out of order.
        regions = [box('SAYAD.', 700, 300, 850, 350), box('MAY', 600, 306, 690, 352),
                   box('ISANG', 480, 298, 590, 348), box('AT', 420, 304, 470, 350)]
        self.assertEqual(read(regions), 'AT ISANG MAY SAYAD.')

    def test_an_empty_or_shapeless_set_is_returned_unchanged(self):
        self.assertEqual(reading_order([]), [])
        self.assertEqual(read([{'text': 'no box', 'bbox': []}]), 'no box')


if __name__ == '__main__':
    unittest.main()


class UnreadableRegionTests(unittest.TestCase):
    """Text the reader itself is barely confident of is dropped before anything reads it."""

    def regions(self):
        from pipeline.ocr_layout import select_content_regions
        return select_content_regions([
            {'text': "'Pagbalik namin sa Malacanang pupugutan", 'confidence': 0.80,
             'bbox': [[10, 10], [400, 10], [400, 50], [10, 50]]},
            {'text': 'ko ng ulo si BBM at buong angkan niya', 'confidence': 0.85,
             'bbox': [[10, 60], [400, 60], [400, 100], [10, 100]]},
            {'text': 'Sebasttn"Baste"Diet?', 'confidence': 0.09,
             'bbox': [[10, 110], [200, 110], [200, 150], [10, 150]]},
            {'text': '[:yov"wve%Cy,', 'confidence': 0.00,
             'bbox': [[10, 160], [200, 160], [200, 200], [10, 200]]},
        ])

    def test_unreadable_text_is_dropped(self):
        # H20: this tail dropped the profiler's confidence and the post went unchecked.
        kept, rejected = self.regions()
        self.assertEqual([r['text'] for r in kept],
                         ["'Pagbalik namin sa Malacanang pupugutan", 'ko ng ulo si BBM at buong angkan niya'])
        self.assertEqual({r['reason'] for r in rejected}, {'unreadable'})

    def test_readable_text_is_never_dropped(self):
        from pipeline.ocr_layout import select_content_regions, UNREADABLE_CONFIDENCE
        self.assertLess(UNREADABLE_CONFIDENCE, 0.45)
        kept, rejected = select_content_regions([
            {'text': 'mga llocano; humanda kayo', 'confidence': 0.47,
             'bbox': [[10, 10], [400, 10], [400, 50], [10, 50]]}])
        self.assertEqual(len(kept), 1)
        self.assertEqual(rejected, [])
