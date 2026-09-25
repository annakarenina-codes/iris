# Quotation handling: changes and retest

Final implementation: `week7-quotation-context-v14`.
Validation recorded September 17, 2026; summary finalized September 18.

## What changed

IRIS now distinguishes "someone actually asked this" from "I imagine someone
asking this." The first can be verified as attribution, even when the quoted
words are questions or opinions. The second is not evidence of an actual utterance.

- Shared framing rules preserve context across consecutive quotations without
  applying it to unrelated prose or another explicitly attributed speaker.
- Both direct quotations and indirect reports such as "He noted that..." require
  coverage. Repeated narrative and quotation versions are consolidated without
  shortening the protected utterance or removing legal references.
- The claim parser preserves reporting frames and balanced quotation marks instead
  of rewriting every attribution as "speaker said."
- Excluded imagined speech cannot return through the local fallback. A validated
  empty extraction remains empty.
- A coverage failure gets one repair attempt. Unsafe direct-quotation extraction
  produces a clear technical error, with no verdict, rather than guessed attribution.
- Existing cross-event, speaker, source-link and final evidence checks remain.
- The cache version changed so old cached verdicts are not reused.

## Final results

| Check | Observed result | Status |
|---|---|---|
| Saved Padilla post | Four claims; both complete quotations retained; Article 11, Section 2 preserved; separate impeachment-mechanism statement and P360,000 bail event retained | Passed for extraction |
| Saved anticipated questions to former SC justices | All three questions retain imagined framing; no extraction or evidence verification triggered | Passed for routing |
| Backend regression suite | 203 passed, 1 skipped, 40 subtests passed | Passed |

The final four claims concern: the request for the Senate's position with its full
quotation; the constitutional attribution with its full quotation; the reported
impeachment-mechanism statement; and the bail event. Four is the observed count,
not a hard-coded quota for future posts.

Reported-case replay TRACE: `159adfe290764d969546168104c201c6`.
Imagined-case replay TRACE: `19950a9ebdc84630877d9cb5defcc8ca`.
Details: `quotation-live-result.json`, `quotation-traces.sqlite3`, and
`quotation-tests.xml` in this directory. The skipped test is the pre-existing
manual full-post claim-count placeholder.

Earlier replay attempts exposed invalid coverage links and loss of indirect
speech or a non-speech event. They prompted the coverage corrections above and
remain in timestamped JSON records; they are not counted as successful runs.
The full suite also caught the quoted-law-title regression, fixed before the
final run.

## Scope and next test

Live calls covered screening/extraction using saved translations. They did not
rerun translation, search, evidence retrieval, verdict generation or either
frontend. Correct extraction does not mean the statements are verified.

Framing detection is bounded and model reasoning can still err, particularly with
implicit satire, unusual multilingual constructions or ambiguous pronouns. No
general accuracy percentage is established by these two cases.

Restart the backend, then submit both original posts again. No extension or
Android rebuild is needed. In TRACE, inspect speech scopes, coverage links and
the resulting complete assertions before assessing the final evidence/verdicts.
