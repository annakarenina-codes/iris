# Translation

The translation stage uses OpenAI Chat Completions with strict structured output, replacing the failing deep-translator Google webpage integration. It uses the backend's existing OPENAI_API_KEY; no Google credentials are needed. The runtime dependency on deep-translator has been removed. Historical provider-diagnosis scripts still require that old package if rerun.

## Configuration

Set these in the backend environment or existing .env file, then restart the backend:

| Setting | Behavior |
| --- | --- |
| OPENAI_API_KEY | Existing backend API credential; never expose it to either frontend. |
| IRIS_TRANSLATION_MODEL | Optional override. Otherwise OPENAI_MODEL is used, falling back to gpt-4o-mini. Choose a Chat Completions model supporting strict JSON-schema output. |
| IRIS_TRANSLATION_TIMEOUT_SECONDS | Default 45 seconds. Valid numeric settings are clamped to 1-120 seconds. Invalid/nonfinite settings use 45. |

There are no automatic API retries. A cancellable asynchronous deadline bounds the API call, in addition to the SDK timeout. The synchronous Flask wrapper creates and closes its own event loop and client; it does not leave a background translation worker running. Calls from an already-running asynchronous loop fail safely to the original text instead of nesting event loops.

## Data Handling

English input bypasses the API. Filipino/Taglish input is divided into quotation-aware source segments and submitted together in a single request. Complete segment IDs and order are required in the response. Translation instructions explicitly preserve names, attribution, negation, amounts, dates, uncertainty, hypotheticals, and satire qualifiers, and prohibit following instructions found in the submitted post.

The validator checks segment count/order, nonempty strings, service-error/HTML contamination, and per-segment numeric literals and currency/percent symbols. Missing or changed numbers reject the entire translation. These checks are intentionally conservative: even a mathematically equivalent rewrite such as replacing 1.2 billion with 1,200,000,000 falls back to the original.

Timeouts, missing dependencies or credentials, provider errors, refusal, truncated output, invalid JSON, and invalid segment responses all retain the entire original input. An unchanged response is recorded as fallback, not translation success. No fallback returns a service error as claim text. The existing function signature and both frontend API contracts are unchanged.

TRACE records translation.request (provider, model, timeout, segment count), translation.success, or translation.fallback with a safe reason and preserve_original action. Authentication headers and API credentials are never included. Original and translated post contents remain available according to the existing TRACE artifact settings.

## Limits and Validation

Schema validation does not prove translation accuracy. Names, negation scope, implied meaning, and natural-language quantities still require calibration and review; the deterministic number check is not a semantic judge. Keeping the original after a failure does not guarantee adequate downstream multilingual retrieval.

The five affected saved cases were live-tested on September 13, 2026. All completed with accepted English translations using gpt-4o-mini, in approximately 1.6-6.5 seconds. Numeric checks passed, and the case-by-case review found no material reversal of the tested assertions, with minor phrasing caveats recorded. See [the retest review](../evaluation/trace-ten-cases/translation-replacement-retest/RETEST-REVIEW.md).

The retest did not measure final verdict accuracy. It does not clear earlier evidence-review crashes or unresolved reference-evidence decisions. Use fresh TRACE calibration runs when testing the full pipeline so old cached verdicts do not obscure changes.

Implementation reference: [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs) and [Python SDK](https://developers.openai.com/api/reference/python).
