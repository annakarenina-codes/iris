# Translation Replacement: Five-Case Live Review

Date: September 13, 2026 (Asia/Manila). Reviewer: Codex, comparing the saved originals against the actual live outputs. This is an assistant review, not independent human validation.

## Result

All five calls returned accepted English translations, compared with five safe fallbacks in the previous Google-page retest. There were no service-error strings in accepted translations. All numeric-literal/currency checks passed. TRACE records translation.success for each case; none used fallback.

Provider: OpenAI. Model: gpt-4o-mini. Deadline: 45 seconds. Automatic retries: zero. No cached translation or verdict was used. This run covers translation only, not screening, extraction, evidence retrieval, or verdict generation.

## Per-Case Review

| Case | Time | Meaning and coverage | Names | Numbers/dates | Negation and qualifiers | Assessment |
| --- | --- | --- | --- | --- | --- | --- |
| 2: Padilla-Wamil | 6.535 s | All hearing assertions and complete questions/answers retained. The distinction between investigation and evaluation survives. | Robinhood Padilla, Roderick Wamil, BARMM, Sara Duterte, NPA and the Audit Observation Memorandum retained. | No numeric literals in this case. No dates or amounts invented. | "It is not an investigation. It is an evaluation" and "There are no provisions" retained. Questions remain questions, not assertions that agents were identified. | Pass for the tested assertions, with a headline wording caveat below. |
| 5: Senate position and bail | 3.128 s | Constitutional reference, request for the Senate's position, and bail report retained. No attempted correction of the source's named Senate president. | Robin Padilla, Sara Duterte, Win Gatchalian, Ferdinand Marcos Jr., Liza Araneta-Marcos and Martin Romualdez retained. | 1987, Article 11, Section 2, the peso symbol, 360,000, three counts, Monday and Saturday retained. | "This is not helping us" retained. The speech's accountability framing remains attributed rather than independently certified. | Pass, with minor stylistic translation noted below. |
| 6: EDSA | 3.105 s | Separate headline and all six substantive paragraphs retained: early road damage, affected sections, budget estimate, criticism, funding question, and absence of response. | EDSA, EDSA Busway, 24 Oras, Jay Sonza, DPWH and Vince Dizon retained. SEC. is expanded to SECRETARY, not a different person. | Phase 1, P1.2 billion, and Christmas Eve last year retained; no invented calendar year. | "Dizon has not released any statement" and "As of now" retained. Budget remains an estimate. The quoted praise headline remains ambiguous, not proof of good performance. | Pass for the tested assertions; satire interpretation remains a downstream context issue. |
| 8: Samaniego | 4.535 s | Complete quotations and attributions retained, including the game-versus-online-contacts contrast, recommendation, and hypothetical cinema comparison. | Art Samaniego Jr., DZRH News, Special on Saturday, Oxford Internet Institute, GoreBox, Call of Duty, MTRCB and Vivamax retained. | July 4, 14-year-old, more than 20, 18+, and 12-year-old retained. | Never considered shooting, no solid evidence, not the game but the people online, and not banning the game all retained. The Vivamax example remains an "if" question, not an actual incident. | Pass for the tested assertions, with tense/wording caveats below. |
| 9: Exchange rate | 1.556 s | Peso-dollar closing-rate statement retained, including that the rate remains low. | Peso and dollar retained as the currencies. No entity invented. | Peso symbol, 62.513, dollar symbol, 1, Wednesday, September 9 retained. | "Remains low" retains the continuation expressed by nananatili pa ring; no direction reversal. | Pass. |

## Wording Caveats

- Case 2: The headline says "HAVE YOU ARRIVED IN BARMM?" rather than the more contextual "HAVE YOU EVER BEEN TO BARMM?" The following already-English sentence still explicitly says "if he had ever visited," so the actual reported assertion remains intact. This is not a perfect standalone headline translation.
- Case 5: "I have been enveloped by disturbing news" is literal and awkward but does not change the substantive constitutional or bail assertions.
- Case 6: "SECRETARY VINCE IS GREAT" retains the literal quoted praise; neither the translation nor this review establishes whether its intent is sincere or sarcastic.
- Case 8: "I'm playing" is a possible but less natural rendering than habitual "I play" in context. "Shooting in real life" in the headline is more interpretive than "shooting outside" in the body. The body retains outside, the negation, attribution and full causal contrast. No material reversal was identified, but these phrasings remain calibration examples.

## Reproducibility and Safety

Raw source/translation pairs, timings and TRACE IDs are in case-02.json, case-05.json, case-06.json, case-08.json and case-09.json. manifest.json records the provider, model, timeout and code hashes. traces.sqlite3 retains the request/result events. Older retests were not overwritten.

Automated regression tests cover malformed JSON/segments, missing/reordered IDs, altered numbers/currency, service-error contamination, refusal/truncation, missing credentials, provider failures, and cancellation of a simulated stuck request. The final suite result is recorded in tests.xml.

Final regression result: 135 passed, 1 skipped, and 4 subtests passed. A deterministic downstream alignment check also passed: all 32 source segments across these five posts aligned with translated segments (8, 7, 7, 9 and 1 respectively). This alignment check did not call OpenAI screening or run final verification.

The numeric checks are programmatic. Meaning, names, negation and the caveats above are reviewer judgments. Five examples are a targeted regression check, not a measured accuracy rate for all Filipino posts. No final verdict labels or earlier evidence holds were changed, and the Google Docs workbook was not edited in this run.
