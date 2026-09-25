import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from pipeline import claim_extractor as extractor
from pipeline.claim_coverage import validate_coverage, apply_grouping, preserve_single_assertion
from pipeline.claim_coverage import review_claim_coverage


def factual(text):
    return {'claim_text': text, 'normalized_claim': text, 'claim_type': 'factual_claim'}


def test_rejected_merge_preserves_validated_inventory():
    sentences = ['The agency opened 12 clinics.', 'The agency hired 40 nurses.']
    payload = {'claims': [factual(t) for t in sentences], 'coverage': [
        {'segment_id': i, 'disposition': 'checkable', 'claim_indexes': [i], 'reason': 'Factual.'}
        for i in range(2)]}
    response = SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',
        message=SimpleNamespace(refusal=None, content=json.dumps(payload)))])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: response)))
    with patch('pipeline.claim_coverage.consolidate_claims', side_effect=ValueError('grouping_changed_numbers')):
        result = review_claim_coverage(client, 'test-model', ' '.join(sentences), [])
    assert [c['normalized_claim'] for c in result['claims']] == sentences
    assert result['grouping_status'] == 'not_applied'
    assert result['grouping_error'] == 'grouping_changed_numbers'
    assert all(c['source_quotes'] for c in result['claims'])


def test_no_ten_claim_truncation():
    claims = [factual(f'The agency opened {i} clinics in region {i}.') for i in range(15)]
    parsed = extractor._parse_claim_response(json.dumps({'claims': claims}))
    assert len(parsed) == len(extractor._renumber_claims(parsed)) == 15
    assert len(extractor._finalize_claims(parsed, '')) == 15


def test_profiler_does_not_drop_sentences_after_thirty():
    from pipeline.content_profiler import _split_segments, _align_translated_segments
    text = ' '.join(f'The agency opened {i} clinics.' for i in range(35))
    assert len(_split_segments(text)) == 35
    assert len(_align_translated_segments(text, text)) == 35


def test_deduplication_preserves_late_qualifiers_and_negation():
    prefix = 'The regional authority publicly announced during its regular press conference on Monday that the new district hospital was '
    texts = [prefix + 'opened in 2016.', prefix + 'not opened in 2016.', prefix + 'opened in 2017.']
    assert len(extractor._dedupe_claim_dicts([factual(t) for t in texts])) == 3


def test_quote_punctuation_duplicate_but_different_speaker_is_not():
    def attributed(speaker, quote):
        return {'claim_type': 'attributed_statement', 'attribution': {
            'speaker': speaker, 'statement': quote}}
    rows = [attributed('Romano Cardi\u00f1o', 'The killing was a "senseless act of violence".'),
            attributed('Romano Cardi\u00f1o', "The killing was a 'senseless act of violence'."),
            attributed('Another Official', 'The killing was a "senseless act of violence".')]
    assert len(extractor._dedupe_claim_dicts(rows)) == 2


def test_ledger_rejects_missing_sentences_or_unlinked_claims():
    row = {'segment_id': 0, 'disposition': 'checkable', 'claim_indexes': [0], 'reason': 'Factual action.'}
    payload = {'claims': [{**factual('He testified.'),
                          'source_quotes': [{'segment_id': 0, 'quote': 'He testified.'}]}], 'coverage': [row]}
    assert validate_coverage(payload, ['He testified.']) is payload
    with pytest.raises(ValueError):
        validate_coverage(payload, ['He testified.', 'The tribunal ruled.'])
    with pytest.raises(ValueError):
        validate_coverage({**payload, 'claims': [*payload['claims'], factual('Invented.') ]}, ['He testified.'])
    with pytest.raises(ValueError):
        validate_coverage({**payload, 'coverage': [{**row, 'claim_indexes': []}]}, ['He testified.'])
    with pytest.raises(ValueError):
        validate_coverage(payload, ['He did not testify.'])


def test_source_provenance_is_original_unicode_not_model_regeneration():
    source = 'Romano Cardi\u00f1o called the killing a \u201csenseless act of violence\u201d.'
    payload = {'claims': [factual(source)], 'coverage': [
        {'segment_id': 0, 'disposition': 'checkable', 'claim_indexes': [0], 'reason': 'Reported statement.'}]}
    result = validate_coverage(payload, [source], materialize_sources=True)
    assert result['claims'][0]['source_quotes'] == [{'segment_id': 0, 'quote': source}]


def test_single_assertion_cannot_drop_its_cited_rationale():
    original = 'Padilla asked Wamil about medicines and terrorism\u2014issues cited as reasons for confidential funds.'
    short = 'Padilla asked Wamil about medicines and terrorism.'
    payload = {'claims': [factual(short)], 'ignored_segments': [], 'coverage': [
        {'segment_id': 0, 'disposition': 'checkable', 'claim_indexes': [0], 'reason': 'Factual statement.'}]}
    result = preserve_single_assertion(payload, [original])
    assert result['claims'][0]['normalized_claim'] == original


def test_embedded_verdict_is_not_restored_as_the_proposition_to_verify():
    headline = 'The claim that the hospital closed is false.'
    payload = {'claims': [factual('The hospital closed.')], 'coverage': [{'disposition': 'checkable'}]}
    assert preserve_single_assertion(payload, [headline])['claims'][0]['normalized_claim'] == 'The hospital closed.'


def test_reviewed_inventory_not_overwritten_by_longer_local_fallback():
    text = 'Carpenter began studying marine ecosystems in 1975 and became a leading expert.'
    reviewed = {'claims': [{**factual('Carpenter began studying marine ecosystems in 1975.'),
                            'source_quotes': [{'segment_id': 0, 'quote': text}]}],
                'ignored_segments': [{'text': 'became a leading expert', 'segment_type': 'opinion'}],
                'coverage': [{'segment_id': 0, 'disposition': 'mixed', 'claim_indexes': [0],
                              'reason': 'Preserve the year; exclude the evaluative superlative.'}]}
    draft = {'claims': [factual(text)], 'ignored_segments': []}
    replies = [draft, reviewed]
    def create(**kwargs):
        message = SimpleNamespace(refusal=None, content=json.dumps(replies.pop(0)))
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop', message=message)])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    with patch.object(extractor, 'OpenAI', return_value=client), \
         patch.object(extractor, '_get_api_key', return_value='test-only'), \
         patch.object(extractor, '_fallback_extract_claims', return_value=[factual('Wrong.')]*12):
        result = extractor.extract_claims(text)
    assert result['status'] == 'ok'
    assert len(result['claims']) == 1
    assert 'leading expert' not in result['claims'][0]['normalized_claim']
    assert result['claims'][0]['evidence_context'] == text
    assert result['coverage'] == reviewed['coverage']


def test_claim_cache_separates_identical_words_in_different_events():
    from app import build_claim_cache_basis
    claim = 'Police are reviewing CCTV footage.'
    first = build_claim_cache_basis(claim, {'evidence_context': 'Carpenter home invasion.'}, claim, None)
    second = build_claim_cache_basis(claim, {'evidence_context': 'Yulo ambush.'}, claim, None)
    assert first != second


def test_grouping_merges_incident_and_splits_distinct_actions_without_losing_sources():
    texts = ['Ada was allegedly killed at home.', 'An intruder entered the home on July 12.',
             'Ada researched the reef and advocated for its protection.']
    payload = {'claims': [factual(t) for t in texts], 'coverage': [
        {'segment_id': i, 'disposition': 'checkable', 'claim_indexes': [i], 'reason': 'Factual assertion.'}
        for i in range(3)]}
    # A report credit on an event fact is not a speaker-attribution claim.
    payload['claims'][1]['attribution'] = {'speaker': 'Police'}
    groups = [{'operation': 'merge', 'input_ids': [0, 1],
               'assertions': ['Ada was allegedly killed at home after an intruder entered on July 12.']},
              {'operation': 'split', 'input_ids': [2],
               'assertions': ['Ada researched the reef.', 'Ada advocated for protection of the reef.']}]
    result = apply_grouping(payload, groups, texts)
    assert len(result['claims']) == 3
    assert result['coverage'][0]['claim_indexes'] == result['coverage'][1]['claim_indexes'] == [0]
    assert result['coverage'][2]['claim_indexes'] == [1, 2]
    assert result['claims'][0]['source_quotes'] == [
        {'segment_id': i, 'quote': texts[i]} for i in [0, 1]]
    with pytest.raises(ValueError):
        apply_grouping(payload, groups[:1], texts)
    with pytest.raises(ValueError):
        apply_grouping(payload, [{**groups[0], 'assertions': ['Ada was killed at home on July 12.']}, groups[1]], texts)
    with pytest.raises(ValueError):
        apply_grouping(payload, [{**groups[0], 'assertions': ['Ada was allegedly killed at home on July 13.']}, groups[1]], texts)


def test_grouping_cannot_merge_a_speaker_report_with_an_underlying_fact():
    texts = ['Ada said the clinic opened.', 'The clinic opened.']
    claims = [factual(t) for t in texts]
    claims[0].update(claim_type='attributed_statement', attribution={'speaker': 'Ada'})
    payload = {'claims': claims, 'coverage': []}
    with pytest.raises(ValueError):
        apply_grouping(payload, [{'operation': 'merge', 'input_ids': [0, 1],
                                 'assertions': ['The clinic opened.']}], texts)
