import asyncio
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from pipeline import translator as t


def response(rows, finish='stop', refusal=None):
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish,
        message=SimpleNamespace(content=json.dumps({'segments': rows}), refusal=refusal))])


def client_factory(result):
    client = Mock()
    client.chat.completions.create = AsyncMock(return_value=result)
    manager = AsyncMock()
    manager.__aenter__.return_value = client
    return Mock(return_value=manager), client, manager


def test_structured_provider_and_timeout_settings():
    factory, client, manager = client_factory(response([{'id': 1, 'translation': 'The rate is 62.513.'}]))
    with patch.object(t, 'AsyncOpenAI', factory):
        translated = asyncio.run(t._request_translation(['Ang palitan ay 62.513.'], 'test', 'model', 3))
    assert translated == 'The rate is 62.513.'
    factory.assert_called_once_with(api_key='test', timeout=3, max_retries=0)
    assert client.chat.completions.create.call_args.kwargs['response_format']['json_schema']['strict']
    manager.__aexit__.assert_awaited_once()


@pytest.mark.parametrize('rows', [[], [{'id': 2, 'translation': 'The rate is 62.513.'}],
    [{'id': True, 'translation': 'The rate is 62.513.'}],
    [{'id': 1, 'translation': ''}], [{'id': 1, 'translation': 'The rate is 62.531.'}],
    [{'id': 1, 'translation': "Error 500 (Server Error)!!"}],
    [{'id': 1, 'translation': '<html>Failure</html>'}],
    [{'id': 1, 'translation': 'The rate is 62.513.'}]*2,
])
def test_invalid_translation_is_rejected(rows):
    with pytest.raises(ValueError):
        t._validate_segments(['Ang palitan ay 62.513.'], json.dumps({'segments': rows}))


def test_missing_or_changed_currency_is_rejected():
    with pytest.raises(ValueError, match='numeric_mismatch'):
        t._validate_segments(['\u20b162.513 = $1'], json.dumps({'segments': [{'id': 1, 'translation': '62.513 = $1'}]}))


def test_reordered_or_missing_segments_are_rejected():
    with pytest.raises(ValueError):
        t._validate_segments(['Una.', 'Pangalawa.'], json.dumps({'segments': [
            {'id': 2, 'translation': 'Second.'}, {'id': 1, 'translation': 'First.'}]}))


@pytest.mark.parametrize('finish,refusal', [('length', None), ('stop', 'Cannot comply')])
def test_truncation_and_refusal_return_original(monkeypatch, finish, refusal):
    monkeypatch.setenv('OPENAI_API_KEY', 'test')
    factory, _, _ = client_factory(response([], finish, refusal))
    with patch.object(t, 'AsyncOpenAI', factory):
        assert t.translate_to_english('Hindi ito imbestigasyon.', 'tagalog') == 'Hindi ito imbestigasyon.'


def test_deadline_cancels_request_and_preserves_original(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test')
    factory, client, manager = client_factory(None)
    cancelled = []

    async def stuck(**kwargs):
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.append(True)

    client.chat.completions.create.side_effect = stuck
    started = time.monotonic()
    with patch.object(t, 'AsyncOpenAI', factory), patch.object(t, '_timeout_seconds', return_value=0.03), patch.object(t, 'event') as event:
        assert t.translate_to_english('Hindi ito imbestigasyon.', 'tagalog') == 'Hindi ito imbestigasyon.'
    assert time.monotonic()-started < 2
    assert cancelled == [True]
    manager.__aexit__.assert_awaited_once()
    assert event.call_args.kwargs['reason'] == 'TimeoutError'


@pytest.mark.parametrize('failure', [RuntimeError('authentication or quota error'), ConnectionError('offline')])
def test_provider_error_preserves_entire_original(monkeypatch, failure):
    monkeypatch.setenv('OPENAI_API_KEY', 'test')
    with patch.object(t, 'AsyncOpenAI', Mock()), patch.object(t, '_request_translation', new=AsyncMock(side_effect=failure)):
        assert t.translate_to_english('Una. Hindi pangalawa.', 'tagalog') == 'Una. Hindi pangalawa.'


def test_missing_key_never_calls_provider(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    with patch.object(t, 'AsyncOpenAI', Mock()), patch.object(t, '_request_translation', new_callable=AsyncMock) as provider:
        assert t.translate_to_english('Kumusta.', 'tagalog') == 'Kumusta.'
        provider.assert_not_called()


@pytest.mark.parametrize('setting,expected', [('nan',45),('inf',45),('bad',45),('-1',1),('999',120),('30',30)])
def test_timeout_configuration_is_bounded(monkeypatch, setting, expected):
    monkeypatch.setenv('IRIS_TRANSLATION_TIMEOUT_SECONDS', setting)
    assert t._timeout_seconds() == expected
