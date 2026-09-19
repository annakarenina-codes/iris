# Quotation Boundaries and Translation Diagnosis

Date: September 13, 2026 (Asia/Manila).

## Changes

- Screening and local fallback extraction now share a sentence-boundary helper.
- Balanced quoted utterances retain internal periods, questions, semicolons, and line breaks. Straight, curly, and nested quotation marks are supported; contractions and common Filipino elisions are not treated as opening quotes.
- Titles such as SEC., Sec., Sen., Atty., Dr., and Gen., initials, and decimal values no longer cause the observed mid-statement splits.
- A complete quoted headline is separated from the following report, while a trailing speaker tag remains attached to its quotation.
- Attributed questions, recommendations, and hypothetical comparisons are retained cautiously for attribution review. Their inclusion does not assert that the hypothetical event happened or that the speaker's opinion is true.
- Reporting words inside a quotation alone are not treated as external attribution. No speaker identity is invented by this change.
- The existing translation-error filter remains unchanged. No new translation provider, model, credentials, final-verdict threshold, or evidence policy was introduced.

## Live Retest

All ten saved inputs were rerun through language detection, translation, and screening using external services. Eight OpenAI calls completed successfully; two cases used local screening. All ten inputs remained eligible for later extraction. Five translation attempts again fell back safely to the original input.

| Case | Observed result after the boundary fix |
| --- | --- |
| 1: Imaginary ownership | Original qualifier and cautious routing retained. Truth remains unresolved. |
| 2: Padilla-Wamil hearing | Both the investigation/evaluation answer and confidential-agent question now survive whole, with their trailing attributions. Only the standalone headline question is skipped. |
| 3: Carpenter | Main factual content retained; three opinion/eulogy segments excluded. Fourteen screening candidates are not fourteen extracted claims. Vague framing still needs extraction review. |
| 4: Bea Borres | Full reunion/denial sentence retained, including negation. |
| 5: Senate position | Multi-sentence quotations are grouped together; bail amount and named recipient remain. |
| 6: EDSA | SEC. VINCE remains intact in a separate headline; all six substantive paragraphs survive. The headline is still forwarded cautiously, so extraction must not treat praise as a standalone factual claim. |
| 7: Medicines and terrorism | Original assertion retained intact. Earlier evidence-review crashes were not retested. |
| 8: Samaniego | Complete quotations, including the recommendation and MTRCB hypothetical comparison, now survive together with their attributions. The named interview and date remain. |
| 9: Exchange rate | Original Filipino text, amount, currency, and date retained. Translation itself did not succeed. |
| 10: National Artists | Complete announcement and quantity retained. |

Raw case outputs and fresh TRACE IDs are in this directory's case JSON files, summary.json, and traces.sqlite3. The earlier preprocessing-fix directory was not overwritten.

After the live run, an additional uppercase-question regression exposed an ordering issue in fallback extraction. That was repaired and covered by tests. Replaying all ten captured OpenAI responses through the final screening code produced identical verification_text for all ten cases. This final replay is not an additional external-service run.

## Translation Diagnosis

The installed deep-translator 1.11.4 GoogleTranslator implementation retrieves an HTML page and reads its translation container. It is not using a configured Google Cloud translation API. The installed transport does not set a request timeout; diagnostic probes used explicit connect/read timeouts without altering production transport.

Three bounded probes were performed:

| Probe | HTTP/page result | Translation result |
| --- | --- | --- |
| Short Filipino greeting, automatic source language | HTTP 200, Google Translate page, translation container present | Container contained Error 500 service-error text; correctly rejected. |
| Saved peso sentence, automatic source language | HTTP 200, Google Translate page, translation container present | Same service-error text; correctly rejected. |
| Saved peso sentence, explicit tl source language | HTTP 200, Google Translate page, no recognized translation container | TranslationNotFound exception. |

Thus HTTP success is not sufficient to establish translation success. A short input failed too, and selecting Filipino explicitly did not restore translation. The evidence identifies a failing page-based provider integration, not the upstream reason Google generated that page. It does not prove an account, quota, firewall, or regional cause.

The existing safety fix works: invalid provider output is not used as claim text. Translation availability remains unresolved. Do not claim that unchanged Filipino input is a successful English translation. Before relying on English-only downstream retrieval, repair or replace this provider integration and add a bounded production transport; provider migration is a separate implementation decision.

Diagnostic details: ../translation-provider-diagnosis.json. Automated regression results: ../quotation-boundary-tests-final.xml.

## Scope Limits

This run did not perform final claim extraction, article retrieval, evidence adjudication, or verdict generation. Screening candidates are not verified claims. Earlier full-system verdict scores and evidence holds remain unchanged. The Google Docs workbook was not edited during this fix.
