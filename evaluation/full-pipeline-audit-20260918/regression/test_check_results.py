import copy
import unittest
from check_results import check_output, AUDIT, read


class RegressionCheckerTests(unittest.TestCase):
    def saved(self, ident):
        run = read(AUDIT / 'current-baseline' / f'{ident}.json')
        return run, run['input_sha256']

    def flags(self, ident, run, digest):
        return {c['check']: c['status'] for c in check_output(ident, run, digest)}

    def test_confirmed_matching_failures_are_detected(self):
        for ident, check in [('B05', 'no_detached_arrest_credit'), ('B12', 'no_detached_causes'),
                             ('C02', 'known_supported_assertion'), ('C03', 'known_supported_assertion'),
                             ('B15', 'known_supported_assertion'), ('C06', 'named_speaker_retained'),
                             ('B07', 'routing_does_not_verify'), ('B16', 'routing_does_not_verify')]:
            with self.subTest(case=ident):
                run, digest = self.saved(ident)
                self.assertEqual(self.flags(ident, run, digest)[check], 'FAIL')

    def test_technical_failures_are_not_successful_requests(self):
        for ident in ['A03', 'A05']:
            run, digest = self.saved(ident)
            flags = self.flags(ident, run, digest)
            self.assertEqual(flags['technical_error_is_not_verdict'], 'PASS')
            self.assertEqual(flags['request_completion'], 'FAIL')

    def test_fake_positive_on_error_fails(self):
        run, digest = self.saved('A03')
        run['response']['verdict'] = 'Verified'
        self.assertEqual(self.flags('A03', run, digest)['technical_error_is_not_verdict'], 'FAIL')

    def test_different_input_cannot_pass(self):
        run, _ = self.saved('C02')
        self.assertEqual(self.flags('C02', run, 'different')['capture_integrity'], 'FAIL')

    def test_missing_claim_is_not_an_automatic_pass(self):
        run, digest = self.saved('C02')
        run['response']['claims'] = []
        self.assertEqual(self.flags('C02', run, digest)['known_supported_assertion'], 'NEEDS_REVIEW')

    def test_corrected_label_passes_only_narrow_check(self):
        run, digest = self.saved('C02')
        altered = copy.deepcopy(run)
        for claim in altered['response']['claims']:
            claim['verdict'] = 'Verified'
        self.assertEqual(self.flags('C02', altered, digest)['known_supported_assertion'], 'PASS')
        self.assertNotEqual(run['response']['claims'][0]['verdict'], 'Verified')

    def test_malformed_capture_rejected(self):
        run, digest = self.saved('C02')
        run['response']['claims'] = None
        self.assertEqual(self.flags('C02', run, digest)['capture_integrity'], 'FAIL')


if __name__ == '__main__':
    unittest.main()
