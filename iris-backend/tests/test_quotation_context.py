import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from pipeline import claim_extractor as extractor, content_profiler as profiler
from pipeline.claim_coverage import review_claim_coverage, apply_grouping
from pipeline.quotation_context import speech_scopes, utterances, validate_speech_coverage
from pipeline.quotation_context import QuotationExtractionError
from pipeline.text_boundaries import split_statement_segments

CASES = json.loads((Path(__file__).parent / 'fixtures/quotation_cases.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('key', ['text', 'translated_text'])
def test_saved_imagined_questions_keep_shared_scope(key):
    text = CASES['imagined'][key]
    profile = profiler.profile_content(text, use_ai=False)
    assert not profile['eligible_for_verification']
    assert len(profile['segments']) == 3
    assert all(s['speech_scope'] == 'imagined' for s in profile['segments'])
    assert sum(len(utterances(s['text'])) for s in profile['segments']) == 3
    assert extractor._fallback_extract_claims(text) == []


def test_ai_cannot_promote_explicitly_imagined_quote():
    text = CASES['imagined']['translated_text']
    local = profiler._local_profile(text, None)
    advice = {'result': {'segments': [{'segment_id': s['segment_id'],
        'top_label': 'factual_claim', 'eligible_for_verification': True, 'top_label_score': 1}
        for s in local['segments']]}}
    assert not profiler._merge_openai_segment_advice(local, advice)['eligible_for_verification']


def test_actual_quote_with_hypothetical_content_is_still_reported():
    text = '"Imagine the mayor said no. What would happen?" Ana asked.'
    assert speech_scopes([text]) == ['reported']
    assert profiler.profile_content(text, use_ai=False)['eligible_for_verification']


def test_actual_reported_questions_not_confused_with_waiting_for_questions():
    actual = '"Where did you graduate?" Robin asked the witness.'
    imagined = 'I am waiting for Robin to ask: "Where did you graduate?"'
    assert speech_scopes([actual, imagined]) == ['reported', 'imagined']
    assert profiler.profile_content(actual, use_ai=False)['eligible_for_verification']
    assert not profiler.profile_content(imagined, use_ai=False)['eligible_for_verification']


def test_reported_plan_is_not_rewritten_as_completed_speech_or_discarded():
    text = 'Ana said she would ask the witness: "Where were you?"'
    assert speech_scopes([text]) == ['reported']
    assert profiler.profile_content(text, use_ai=False)['verification_text'] == text
    assert speech_scopes(['In a fictional interview, Ana said: "Where were you?"']) == ['imagined']


def test_quoted_title_is_not_a_direct_utterance():
    text = 'Mariel stated that her husband passed a law dubbed the "Robin Padilla Law".'
    assert speech_scopes([text]) == ['reported_indirect']
    assert utterances(text) == []
    assert speech_scopes(['That said, this is the worst idea.']) == ['none']


def test_scope_does_not_leak_into_independent_facts_or_another_speaker():
    text = ('I imagine Robin saying: "Why?" "What now?" '
            'The agency opened 12 clinics. "Do not stop," Ana said.')
    profile = profiler.profile_content(text, use_ai=False)
    assert '12 clinics' in profile['verification_text']
    assert 'Ana said' in profile['verification_text']
    assert 'imagine' not in profile['verification_text']
    assert 'What now' not in profile['verification_text']


@pytest.mark.parametrize('key', ['text', 'translated_text'])
def test_saved_reported_quotes_survive_screening_in_full(key):
    text = CASES['reported'][key]
    profile = profiler.profile_content(text, use_ai=False)
    reported = [s for s, scope in zip(split_statement_segments(text), speech_scopes(split_statement_segments(text)))
                if scope == 'reported']
    assert len(reported) == 2
    for s in reported:
        assert s in profile['verification_text']


def inventory(text, excluded=False):
    return {'claims': [] if excluded else [{'claim_text': text, 'normalized_claim': text,
             'claim_type': 'attributed_statement', 'attribution': {'speaker': 'Ana', 'statement': text}}],
            'ignored_segments': [], 'coverage': [{'segment_id': 0,
                'disposition': 'excluded' if excluded else 'checkable',
                'claim_indexes': [] if excluded else [0], 'reason': 'A reported speech act.'}]}


def test_reported_opinion_question_and_legal_reference_cannot_be_dropped():
    text = '"This is awful. What is your position? See Article 11, Section 2," Ana said.'
    good = inventory(text)
    assert validate_speech_coverage(good, [text]) is good
    with pytest.raises(ValueError, match='reported_utterance_excluded'):
        validate_speech_coverage(inventory(text, True), [text])
    for key in ['claim_text', 'normalized_claim']:
        bad = deepcopy(good)
        bad['claims'][0][key] = 'Ana said the Constitution applies.'
        with pytest.raises(ValueError, match='reported_utterance_shortened'):
            validate_speech_coverage(bad, [text])


def test_imagined_attribution_cannot_pass_coverage():
    text = 'I imagine Ana asking: "Who are you?"'
    with pytest.raises(ValueError, match='imagined_speech_promoted'):
        validate_speech_coverage(inventory(text), [text])
    assert validate_speech_coverage(inventory(text, True), [text])['claims'] == []


def test_indirect_speech_cannot_be_discarded_as_not_a_direct_quote():
    text = 'He noted that impeachment is the constitutional mechanism for removal.'
    assert speech_scopes([text]) == ['reported_indirect']
    with pytest.raises(ValueError, match='reported_speech_act_excluded'):
        validate_speech_coverage(inventory(text, True), [text])


def test_coverage_repairs_reported_question_exclusion_once():
    text = '"What is your position?" Ana asked.'
    replies = [inventory(text, True), inventory(text)]
    calls = []
    def create(**kwargs):
        calls.append(deepcopy(kwargs))
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',
            message=SimpleNamespace(refusal=None, content=json.dumps(replies.pop(0))))])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    result = review_claim_coverage(client, 'test', text, [])
    assert len(calls) == 2
    assert 'reported_utterance_excluded' in calls[1]['messages'][-1]['content']
    assert result['claims'][0]['source_quotes'] == [{'segment_id': 0, 'quote': text}]


def test_coverage_cannot_retry_forever():
    text = '"What is your position?" Ana asked.'
    def create(**kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',
            message=SimpleNamespace(refusal=None, content=json.dumps(inventory(text, True))))])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    with pytest.raises(ValueError, match='reported_utterance_excluded'):
        review_claim_coverage(client, 'test', text, [])


def test_consolidation_cannot_shorten_quote_into_its_narrative_summary():
    texts = ['Ana requested a position.', '"What is your position? Explain it," Ana said.']
    payload = {'claims': [inventory(t)['claims'][0] for t in texts], 'coverage': [
        {'segment_id': i, 'disposition': 'checkable', 'claim_indexes': [i], 'reason': 'Same speech act.'}
        for i in range(2)]}
    with pytest.raises(ValueError, match='reported_utterance_shortened'):
        apply_grouping(payload, [{'operation': 'merge', 'input_ids': [0, 1],
                                 'assertions': ['Ana requested a position.']}], texts)


def test_parser_keeps_negated_speech_frame_and_balanced_quotes():
    text = 'Ana denied saying "Close the clinic."'
    raw = inventory(text)['claims'][0]
    raw['attribution']['statement'] = 'Close the clinic.'
    claim = extractor._parse_claim_response(json.dumps({'claims': [raw]}))[0]
    assert claim['normalized_claim'] == text
    assert claim['claim_text'] == text


def test_validated_empty_inventory_never_resurrects_local_draft():
    text = 'I imagine Ana asking: "Who are you?"'
    response = SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',
        message=SimpleNamespace(refusal=None, content='{"claims":[],"ignored_segments":[]}'))])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: response)))
    covered = inventory(text, True)
    with patch.object(extractor, 'OpenAI', return_value=client), \
         patch.object(extractor, '_get_api_key', return_value='test'), \
         patch.object(extractor, '_fallback_extract_claims', return_value=[{'claim_text': 'Invented!'}]), \
         patch('pipeline.claim_coverage.review_claim_coverage', return_value=covered):
        result = extractor.extract_claims(text)
    assert result['status'] == 'ok'
    assert result['claims'] == []


def test_hypothetical_post_stops_before_extraction_and_search():
    import app as iris
    text = CASES['imagined']['translated_text']
    with patch.object(iris, 'detect_language', return_value='english'), \
         patch.object(iris, 'profile_content', side_effect=lambda text, translated:
                      profiler.profile_content(text, translated, use_ai=False)), \
         patch.object(iris, 'extract_claims') as extract:
        iris.verify_text_payload(text)
    extract.assert_not_called()


def test_quote_extraction_failure_cannot_reuse_guessed_local_attribution():
    with patch.object(extractor, 'OpenAI', side_effect=RuntimeError('provider unavailable')), \
         patch.object(extractor, '_get_api_key', return_value='test'):
        with pytest.raises(QuotationExtractionError):
            extractor.extract_claims('"Who are you?" Ana asked.')


def test_quote_failure_returns_technical_error_not_no_checkable_claims():
    import app as iris
    with patch.object(iris, 'extract_claims', side_effect=QuotationExtractionError('quotation_review_failed')), \
         patch.object(iris, 'profile_content', side_effect=lambda text, translated:
                      profiler.profile_content(text, translated, use_ai=False)):
        response = iris.app.test_client().post('/verify', json={'text': '"Who are you?" Ana asked.'})
    body = response.get_json()
    assert response.status_code == 503
    assert body['verdict'] is None
    assert body['evidence_sources'] == []
    assert body['failed_stage'] == 'claim_extraction'
