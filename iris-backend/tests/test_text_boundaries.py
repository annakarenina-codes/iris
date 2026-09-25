from unittest.mock import patch

import pytest

from pipeline import content_profiler as profiler
from pipeline import claim_extractor
from pipeline.text_boundaries import has_reported_quote, split_statement_segments


@pytest.mark.parametrize('quote', [
    '"Hindi po siya imbestigasyon. Evaluation po," the witness answered.',
    '"DO YOU AGREE?" Wamil asked.',
    '"Do you believe agents should be identified? State their real names," Padilla said.',
    '\u201cIt is not an investigation. It is an evaluation,\u201d Wamil replied.',
    '\u201cWe should not ban it. We should examine the issue,\u201d Samaniego said.',
    '"If a child watches a film, should we close the cinema? Or check the ratings?" he asked.',
    '"We must check the \'classified\' records. Don\'t publish them," Wamil said.',
    '"Ang tunay na dahilan hindi \'yung laro. Tingnan ang isyu," Samaniego said.',
    '"Para \'yang sa MTRCB, merong rating. Kung may nakapanood na bata, ipapasara ba natin? Ganun lang \'yun," Samaniego said.',
    'Wamil said, "It is not an investigation.\nIt is an evaluation."',
    '"First part; second part.\nThird part," Wamil said.',
])
def test_complete_attributed_utterance_survives_screening(quote):
    assert split_statement_segments(quote) == [quote]
    profile = profiler.profile_content(quote, use_ai=False)
    assert len(profile['segments']) == 1
    assert profile['eligible_for_verification']
    assert profile['contains_quote']
    assert profile['verification_text'] == ' '.join(quote.split())
    assert 'reported_attribution_needs_verification' in profile['ambiguity_reasons']
    assert len(claim_extractor._split_segments(quote)) == 1


@pytest.mark.parametrize('title', ['SEC.', 'Sec.', 'sec.', 'Sen.', 'Atty.', 'Dr.', 'Gen.', 'Rep.'])
def test_titles_do_not_break_names(title):
    text = f'{title} Vince Dizon announced repairs. Work began yesterday.'
    assert split_statement_segments(text) == [f'{title} Vince Dizon announced repairs.', 'Work began yesterday.']


def test_edsa_headline_is_separate_and_unchanged():
    text = '"ANG GALING NI SEC. VINCE" Muling nabuksan ang usapin sa EDSA.'
    assert split_statement_segments(text) == ['"ANG GALING NI SEC. VINCE"', 'Muling nabuksan ang usapin sa EDSA.']
    profile = profiler.profile_content(text, use_ai=False)
    assert profile['segments'][0]['text'] == '"ANG GALING NI SEC. VINCE"'
    assert 'VINCE" Muling' not in profile['verification_text']


def test_headline_followed_by_report_is_not_a_trailing_speech_tag():
    headline = "'NAKARATING NA PO BA KAYO NG BARMM?'"
    report = 'Senator-judge Robinhood Padilla asked former auditor Wamil about terrorism.'
    profile = profiler.profile_content(headline + ' ' + report, use_ai=False)
    assert [s['text'] for s in profile['segments']] == [headline, report]
    assert profile['verification_text'] == report


def test_neighboring_sentences_and_quote_attribution_stay_separate():
    text = 'Wamil testified. "Not an investigation. An evaluation," Wamil said. Padilla listened.'
    assert split_statement_segments(text) == ['Wamil testified.', '"Not an investigation. An evaluation," Wamil said.', 'Padilla listened.']
    assert split_statement_segments('"Enough!" Wamil said. "Why?" Padilla asked.') == ['"Enough!" Wamil said.', '"Why?" Padilla asked.']


def test_decimal_initials_and_apostrophes():
    text = "Dr. Maria A. Santos reported 62.513 pesos. The child's account doesn't change."
    assert len(split_statement_segments(text)) == 2
    assert not has_reported_quote("The child's account doesn't change.")
    assert not has_reported_quote('"He said the project failed."')


def test_unclosed_quote_does_not_swallow_later_paragraphs():
    parts = split_statement_segments('"Unfinished text.\n\nThe agency reported 20 cases. Another report followed.')
    assert 'The agency reported 20 cases.' in parts


def test_long_quote_has_no_arbitrary_260_character_limit():
    quote = '"' + 'This is a hypothetical comparison, not an actual event. ' * 8 + '" the expert said.'
    assert has_reported_quote(quote)
    assert profiler.profile_content(quote, use_ai=False)['eligible_for_verification']


def test_unattributed_opinion_is_not_promoted_by_reporting_verb_inside_quotes():
    text = '"He said this is the worst idea and I hate it."'
    assert not has_reported_quote(text)
    assert not profiler.profile_content(text, use_ai=False)['eligible_for_verification']


def test_ai_advice_cannot_remove_complete_local_attribution():
    text = '"Do not ban games. Review the issue," Samaniego said.'
    advice = {'used': True, 'status': 'ok', 'result': {'segments': [{
        'segment_id': 's1', 'top_label': 'call_to_action',
        'top_label_score': 0.9, 'eligible_for_verification': False,
    }]}}
    with patch.object(profiler, '_request_openai_profile', return_value=advice):
        assert profiler.profile_content(text)['verification_text'] == text
