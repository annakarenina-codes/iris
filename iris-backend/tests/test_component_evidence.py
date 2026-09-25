import sys
import unittest
import json
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.component_evidence import validate_review, review_components, require_completed_review, ComponentReviewError, partition_from_token_ends
from pipeline.component_evidence import apply_entailment_checks, entailment_schema
from pipeline.component_evidence import partition_from_breakpoints, indexed_passages, materialize_assessments
from pipeline.component_evidence import mapped_review_entries, assessment_schema
from pipeline.component_context import FIELDS


class ComponentTests(unittest.TestCase):
    def test_both_requests_explicitly_request_json(self):
        calls = []
        replies = [{"split_after": [], "contexts": [{k: [] for k in FIELDS}]}, {"assessments": {
            "0": {"status": "not_supported", "passage_ids": []}}}]
        def create(**kwargs):
            calls.append(kwargs)
            self.assertIn("JSON", kwargs["messages"][0]["content"])
            self.assertEqual(kwargs['response_format']['type'], 'json_schema')
            self.assertTrue(kwargs['response_format']['json_schema']['strict'])
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop', message=SimpleNamespace(refusal=None, content=json.dumps(replies.pop(0))))])
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch.dict(sys.modules, {"openai": SimpleNamespace(OpenAI=lambda **kw: client)}), \
             patch.dict('os.environ', {'IRIS_EVIDENCE_REVIEW_MODEL': 'review-test-model', 'OPENAI_MODEL': 'draft-test-model'}):
            result = review_components("Example claim.", [])
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]['model'], 'review-test-model')
        # The first-pass assessment uses the review model unless explicitly overridden.
        self.assertEqual(calls[1]['model'], 'review-test-model')
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result['assessment_model'], 'review-test-model')

        calls.clear()
        replies.extend([{"split_after": [], "contexts": [{k: [] for k in FIELDS}]}, {"assessments": {
            "0": {"status": "not_supported", "passage_ids": []}}}])
        with patch.dict(sys.modules, {"openai": SimpleNamespace(OpenAI=lambda **kw: client)}), \
             patch.dict('os.environ', {'IRIS_EVIDENCE_REVIEW_MODEL': 'review-test-model',
                                       'IRIS_ASSESSMENT_MODEL': 'assessment-test-model'}):
            review_components("Example claim.", [])
        self.assertEqual(calls[1]['model'], 'assessment-test-model')

    def test_rate_limit_remains_a_clear_technical_error(self):
        RateLimitError = type('RateLimitError', (Exception,), {})
        def fail(**kwargs):
            raise RateLimitError('Provider limit reached.')
        with patch.dict(sys.modules, {'openai': SimpleNamespace(OpenAI=fail)}):
            result = review_components('Example claim.', [])
        self.assertEqual(result['error_code'], 'review_rate_limited')
        self.assertIsNone(result['verdict'])
        self.assertEqual(result['supporting_urls'], [])

    def test_api_failure_is_not_a_verdict(self):
        def fail(**kwargs):
            raise RuntimeError("API failure")
        with patch.dict(sys.modules, {"openai": SimpleNamespace(OpenAI=fail)}):
            result = review_components("Example claim.", [])
        self.assertEqual(result["status"], "error")
        self.assertIsNone(result["verdict"])
        with self.assertRaises(ComponentReviewError):
            require_completed_review(result)

    def setUp(self):
        self.parts = ["Padilla asked Wamil about medicines", "and terrorism."]
        self.claim = " ".join(self.parts)
        self.articles = [{"url": "https://example.org/news", "text":
            "Padilla questioned Wamil about the need for medicines. Later he questioned Wamil about terrorism."}]

    def assess(self, second=True, url="https://example.org/news"):
        return [{"component_id": 0, "status": "supported", "citations": [
            {"url": url, "quote": "Padilla questioned Wamil about the need for medicines."}]},
            {"component_id": 1, "status": "supported" if second else "not_supported", "citations": [
            {"url": url, "quote": "Later he questioned Wamil about terrorism."}]}]

    def test_full_and_partial_support(self):
        for supported, verdict in [(True, "Verified"), (False, "Partially Verified")]:
            result = validate_review(self.claim, self.parts, self.assess(supported), self.articles)
            self.assertEqual(result["verdict"], verdict)

    def test_invented_url_and_passage_rejected(self):
        result = validate_review(self.claim, self.parts, self.assess(url="https://fake.org"), self.articles)
        self.assertEqual(result["verdict"], "Not Found")
        assessments = self.assess()
        for item in assessments:
            item["citations"][0]["quote"] = "This quotation is not in the retrieved article."
        self.assertEqual(validate_review(self.claim, self.parts, assessments, self.articles)["verdict"], "Not Found")

    def test_real_passage_from_wrong_event_cannot_support_investigation(self):
        claim = 'The suspects remain at large, and investigators are reviewing CCTV footage.'
        quote = 'Probers are reviewing MMDA videos of the Jose Luis Yulo ambush.'
        article = {'url': 'https://www.philstar.com/nation/2019/02/20/1895068/probers-review-mmda-videos-jose-luis-yulo-ambush', 'text': quote}
        preliminary = validate_review(claim, [claim], [{'component_id': 0, 'status': 'supported',
            'citations': [{'url': article['url'], 'quote': quote}]}], [article])
        self.assertEqual(preliminary['verdict'], 'Verified')  # Verbatim alone is insufficient.
        final = apply_entailment_checks(claim, preliminary, [{'component_id': 0,
            'same_subject_and_event': False, 'assertion_supported': False,
            'qualifiers_preserved': False, 'citation_ids': [],
            'reason': 'This is the Yulo ambush, not the Carpenter home invasion.'}], [article])
        self.assertEqual(final['verdict'], 'Not Found')
        self.assertEqual(final['supporting_urls'], [])

    def test_same_speaker_but_missing_relationship_becomes_partial(self):
        preliminary = validate_review(self.claim, self.parts, self.assess(), self.articles)
        checks = [{'component_id': i, 'same_subject_and_event': True,
                   'assertion_supported': i == 0, 'qualifiers_preserved': True,
                   'citation_ids': [0] if i == 0 else [],
                   'reason': 'Supported.' if i == 0 else 'The quoted passage does not establish this relationship.'}
                  for i in range(2)]
        final = apply_entailment_checks(self.claim, preliminary, checks, self.articles)
        self.assertEqual(final['verdict'], 'Partially Verified')
        self.assertEqual(final['components'][1]['citations'], [])
        with self.assertRaises(ValueError):
            apply_entailment_checks(self.claim, preliminary, checks[:1], self.articles)

    def test_model_schema_only_allows_real_passage_ids_for_each_component(self):
        schema = entailment_schema([
            {'component_id': 0, 'passages': [{'citation_id': 0}]},
            {'component_id': 3, 'passages': [{'citation_id': 0}, {'citation_id': 1}]}])
        fields = schema['properties']['checks']['properties']
        first, second = fields['0'], fields['3']
        self.assertEqual(schema['properties']['checks']['required'], ['0', '3'])
        self.assertEqual(first['properties']['citation_ids']['items']['enum'], [0])
        self.assertEqual(second['properties']['citation_ids']['items']['enum'], [0, 1])

    def test_independent_check_receives_unverified_context_and_cannot_reuse_proposed_verdict(self):
        calls = []
        replies = [{'split_after': [], 'contexts': [{k: [] for k in FIELDS}]}, {'assessments': {
            '0': {'status': 'supported', 'passage_ids': [0]}}},
            {'groups': [{'component_ids': [0], 'referent': 'Padilla questioning Wamil',
                         'sources': {'0': {'status': 'matched', 'passage_ids': [0],
                                           'reason': 'Same participants and questioning.'}}}]},
            {'checks': {'0': {'same_subject_and_event': True,
                         'assertion_supported': False, 'qualifiers_preserved': True,
                         'citation_ids': [], 'reason': 'Only medicines is supported.'}}}]
        def create(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',
                message=SimpleNamespace(refusal=None, content=json.dumps(replies.pop(0))))])
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch.dict(sys.modules, {'openai': SimpleNamespace(OpenAI=lambda **kw: client)}):
            result = review_components(self.claim, self.articles, source_context='Unverified post.')
        self.assertEqual(len(calls), 4)
        last_payload = json.loads(calls[-1]['messages'][1]['content'])
        self.assertEqual(last_payload['source_context_not_evidence'], 'Unverified post.')
        self.assertNotIn('verdict', last_payload)
        self.assertEqual(result['verdict'], 'Not Found')

    def test_component_maps_cannot_omit_or_repeat_ids(self):
        self.assertEqual(mapped_review_entries({'3': {'status': 'supported'}}, [3]),
                         [{'component_id': 3, 'status': 'supported'}])
        for value in [{}, {'0': {}, '1': {}}, [], {'0': None}]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                mapped_review_entries(value, [0])
        schema = assessment_schema(2, 3)['properties']['assessments']
        self.assertEqual(schema['required'], ['0', '1'])
        self.assertEqual(schema['properties']['1']['properties']['passage_ids']['items']['maximum'], 2)

    def test_undated_passage_leaves_the_year_unconfirmed(self):
        claim = 'The fan meeting is set for October 10, 2026.'
        article = {'url': 'https://example.org/fanmeet',
                   'text': 'The fan meeting is set for October 10, organizers said.'}
        reviewed = validate_review(claim, [claim], [{'component_id': 0, 'status': 'supported',
            'citations': [{'url': article['url'], 'quote': article['text']}]}], [article])
        final = apply_entailment_checks(claim, reviewed, [{
            'component_id': 0, 'same_subject_and_event': True, 'assertion_supported': True,
            'qualifiers_preserved': True, 'contradicted': False, 'citation_ids': [0],
            'reason': 'Same fan meeting.'}], [article])
        self.assertEqual(final['verdict'], 'Partially Verified')
        self.assertEqual(final['components'][0]['status'], 'partially_supported')

    def test_different_year_cannot_pass_even_when_model_approves(self):
        claim = 'Carpenter delivered oral testimony during the 2015 hearing.'
        quote = 'Carpenter delivered oral testimony during the 2016 hearing.'
        article = {'url': 'https://example.org/news', 'text': quote}
        preliminary = validate_review(claim, [claim], [{'component_id': 0,
            'status': 'supported', 'citations': [{'url': article['url'], 'quote': quote}]}], [article])
        final = apply_entailment_checks(claim, preliminary, [{'component_id': 0,
            'same_subject_and_event': True, 'assertion_supported': True,
            'qualifiers_preserved': True, 'citation_ids': [0], 'reason': 'Model approved.'}], [article])
        self.assertEqual(final['verdict'], 'Not Found')
        self.assertIn('2015', final['entailment_checks'][0]['reason'])

    def test_omitted_or_rewritten_component_rejected(self):
        for parts in [[self.parts[0]], ["Padilla did not ask Wamil about medicines", self.parts[1]]]:
            with self.assertRaises(ValueError):
                validate_review(self.claim, parts, self.assess(), self.articles)

    def test_unicode_claim_text_is_sliced_not_regenerated(self):
        claims = [
            'Police Brigadier General Romano Cardi\u00f1o condemned the killing as a "senseless act of violence" and vowed to bring those responsible to justice.',
            'Senator-judge Robin Padilla asks state auditor Roderick Wamil about his personal background, noting whether he understood the need for medicines in far-flung areas and the threat of terrorism in the country\u2014issues cited as among the reasons for Vice President Sara Duterte\u2019s use of confidential funds.',
        ]
        for claim in claims:
            with self.subTest(claim=claim):
                parts = partition_from_token_ends(claim, [5, len(claim.split())-1])
                self.assertEqual(' '.join(parts), claim)
                self.assertFalse(any(ord(c) < 32 for c in ''.join(parts)))

    def test_internal_breakpoints_always_retain_the_final_clause(self):
        claim = 'Padilla asked about medicines and the stated confidential funds rationale.'
        self.assertEqual(' '.join(partition_from_breakpoints(claim, [3])), claim)
        self.assertEqual(partition_from_breakpoints(claim, []), [claim])
        with self.assertRaises(ValueError):
            partition_from_breakpoints(claim, [len(claim.split()) - 1])

    def test_possessive_cannot_be_split_from_its_object(self):
        for possessive in ["Duterte's", 'Duterte\u2019s']:
            claim = f'Issues cited as reasons for {possessive} use of confidential funds.'
            self.assertEqual(partition_from_breakpoints(claim, [5]), [claim])

    def test_source_passages_are_selected_not_generated(self):
        passages = indexed_passages(self.articles)
        assessments = materialize_assessments([
            {'component_id': 0, 'status': 'supported', 'passage_ids': [0]}], passages)
        self.assertEqual(assessments[0]['citations'][0]['quote'], passages[0]['text'])
        self.assertIn(assessments[0]['citations'][0]['quote'], self.articles[0]['text'])
        self.assertEqual(assessments[0]['citations'][0]['url'], self.articles[0]['url'])
        with self.assertRaises(ValueError):
            materialize_assessments([{'component_id': 0, 'status': 'supported', 'passage_ids': [999]}], passages)

    def test_saved_corrupt_output_is_still_rejected(self):
        claim = 'Romano Cardi\u00f1o condemned the killing.'
        with self.assertRaises(ValueError):
            validate_review(claim, ['Romano Cardi\u001fo condemned the killing.'], [], [])

    def test_invalid_boundary_ids_cannot_drop_text(self):
        for ends in [None, [], [0], [2], [-1, 1], [1, 0], [0, 0, 1], [True], ['1']]:
            with self.subTest(ends=ends), self.assertRaises(ValueError):
                partition_from_token_ends('Two tokens.', ends)

    def test_malformed_assessment_is_a_processing_failure(self):
        bad = [None, 'garbled', {'component_id': 0, 'status': 'Verified', 'citations': []},
               {'component_id': False, 'status': 'supported', 'citations': []},
               {'component_id': 0, 'status': 'supported', 'citations': [None]}]
        for item in bad:
            with self.subTest(item=item), self.assertRaises(ValueError):
                validate_review('Example.', ['Example.'], [item], [])

    def test_incomplete_review_cannot_be_accepted(self):
        for review in [None, {}, {'status': 'ok', 'verdict': 'Verified'},
                       {'status': 'unknown', 'verdict': 'Not Found'}]:
            with self.subTest(review=review), self.assertRaises(ComponentReviewError):
                require_completed_review(review)

    def test_broken_partition_never_reaches_evidence_assessment(self):
        calls = []
        def create(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',
                message=SimpleNamespace(refusal=None, content='{"component_ends": [0]}'))])
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch.dict(sys.modules, {'openai': SimpleNamespace(OpenAI=lambda **kw: client)}):
            result = review_components('Example claim.', [])
        # One corrective retry of the partition, then the failure stands.
        self.assertEqual(len(calls), 2)
        self.assertEqual({c['response_format']['json_schema']['name'] for c in calls}, {'component_boundaries'})
        self.assertIn('CORRECTION', calls[1]['messages'][0]['content'])
        self.assertIsNone(result['verdict'])
        self.assertEqual(result['failed_stage'], 'partition')

    def test_http_error_has_no_verdict_or_evidence(self):
        import app as iris
        error = ComponentReviewError('invalid_review_response', 'partition')
        with patch.object(iris, 'verify_text_payload', side_effect=error):
            response = iris.app.test_client().post('/verify', json={'text': 'Example claim.'})
        self.assertEqual(response.status_code, 503)
        body = response.get_json()
        self.assertEqual(body['status'], 'processing_error')
        self.assertIsNone(body['verdict'])
        self.assertEqual(body['evidence_sources'], [])
        self.assertEqual(body['failed_stage'], 'partition')

    def test_failure_cannot_reuse_positive_fallback_or_write_cache(self):
        import app as iris
        claim = {'claim_id': 1, 'claim_text': 'Padilla asked Wamil about medicines.',
                 'normalized_claim': 'Padilla questioned Wamil.',
                 'claim_type': 'attributed_statement'}
        article = {'url': 'https://www.philstar.com/headlines/example', 'text': 'Some evidence.'}
        search_result = {'articles': [article], 'total_search_results': 1, 'searched_articles': 1,
                         'extracted_articles': 1, 'source_summary': []}
        with patch.object(iris, 'quote_paraphrase_for_claim', return_value={}),              patch.object(iris, 'get_cached_verdict', return_value=None),              patch.object(iris, 'get_claim_flags', return_value={'politically_sensitive': False, 'flags': []}),              patch.object(iris, 'build_claim_search_result', return_value=(search_result, 'test')),              patch.object(iris, 'get_search_status', return_value={'status': 'ok'}),              patch.object(iris, 'generate_verdict', return_value={'verdict': 'Verified', 'reason': 'test'}),              patch.object(iris, 'apply_low_confidence_fallback', return_value={
                 'verdict': 'Verified', 'message': 'test', 'openai_fallback': {}, 'keyword_fallback': None}),              patch.object(iris, 'build_public_evidence_sources', return_value=[article]),              patch.object(iris, 'compact_evidence_source', return_value=article),              patch.object(iris, 'attribution_evidence_gate', return_value={'matches': True}),              patch('pipeline.component_evidence.review_components', return_value={
                 'status': 'error', 'verdict': None, 'error_code': 'review_rate_limited',
                 'failed_stage': 'entailment_check'}) as review,              patch.object(iris, 'save_cached_verdict') as save:
            result = iris.verify_claim(claim, 'english')
        # The failed claim gets an explicit technical status, never the positive fallback.
        self.assertEqual(result['verdict'], iris.REVIEW_FAILED_VERDICT)
        self.assertEqual(result['review_error'], {'reason_code': 'review_rate_limited',
                                                  'failed_stage': 'entailment_check', 'retryable': True})
        self.assertEqual(result['evidence_sources'], [])
        self.assertIsNone(result['primary_evidence'])
        save.assert_not_called()
        self.assertEqual(review.call_args.args[0], claim['claim_text'])

    def test_request_fails_only_when_every_claim_review_failed(self):
        import app as iris
        failed = {'verdict': 'Review Failed', 'review_error': {
            'reason_code': 'review_rate_limited', 'failed_stage': 'entailment_check', 'retryable': True}}
        done = {'verdict': 'Verified', 'review_error': None}
        iris.raise_if_every_review_failed([done, failed])
        iris.raise_if_every_review_failed([])
        with self.assertRaises(ComponentReviewError) as caught:
            iris.raise_if_every_review_failed([failed, failed])
        self.assertEqual(caught.exception.reason_code, 'review_rate_limited')
        self.assertEqual(caught.exception.stage, 'entailment_check')

    def test_original_assertions_have_distinct_cache_keys(self):
        import app as iris
        a = {'claim_text': 'The singer spoke on September 17.'}
        b = {'claim_text': 'The singer spoke on September 18.'}
        self.assertNotEqual(iris.build_claim_cache_basis('The singer spoke.', a, None, None),
                            iris.build_claim_cache_basis('The singer spoke.', b, None, None))


if __name__ == "__main__":
    unittest.main()
