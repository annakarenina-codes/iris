## Findings (Claude's provisional review, for you to validate)

The remaining 17 of the 34 development cases, on `ab9bcf2` (same pipeline as the final priority run). All 17 returned HTTP 200. On 18 Sept, A03 and A05 ended in a whole-request 503; both now complete.

| Case | 18 Sept | Now | Claude's view |
|---|---|---|---|
| A02 | Failed | Review Failed, Not Found, then 5× Verified | **Improved.** The Robin/Robinhood Padilla quotations (claims 3–7) are now verified (DZRH, Manila Bulletin, Rappler). Claim 1 failed technically (see pattern 1). Claim 2 (the AOM questions) is Not Found. |
| A03 | Failed (503) | 11× Verified, 1 Review Failed | **Much improved.** The UNESCO advocacy is now kept and verified. Claim 5 (investigation status) failed technically (pattern 1). Took 741s. |
| A05 | Failed (503) | 4× Verified, 3× Not Found | **Improved.** The quotations and the ₱360,000 bail are verified. "Became emotional", the impeachment-mechanism remark and "asked Senate President Win Gatchalian" are Not Found: sources describe him as "troubled" and don't name the addressee. Please judge. |
| A06 | Failed | Not Found, Review Failed, Verified, 3× Not Found | **Mixed.** Claim 1 was rejected only because no source mentions "peeling" (strict, but by the rules). Claim 2 failed technically (pattern 1). Check the P1.2 billion source (OneNews): an LRT-1 P1.2 billion passage was correctly rejected. The Sonza claims remain unconfirmed. Claim 6 ("Dizon has not released any statement") is Not Found, and sources show he did respond. |
| A07 | Failed | 3× Verified, Review Failed | **Improved.** No duplicate claim any more; background, medicines and terrorism are each verified. The funds-rationale claim failed technically (pattern 1). |
| A08 | Cannot yet judge | 4× Not Found | Consistent: no source establishes the DZRH interview. |
| A09 | Failed | Not Found | Search-index gap (OPEN-ISSUES.md). |
| B01 | Cannot yet judge | Verified, Not Found | Consistent: Perez verified; Matibag's statement is still Not Found. |
| B04 | Failed | 6× Verified, 1 Not Found | **Improved** ("last seen March 14, 2025" is now verified). Claim 5, the expert-panel quotation, still has no speaker, so the speaker check rejects all 33 articles (pattern 2). |
| B05 | Failed | Not Found | Correct given that no article exists (you deferred this case). |
| B07 | Failed | 4× Not Found, 1 Verified | **Still failing.** Generic "vote wisely" advocacy is still extracted, and one line is verified by opinion columns (opinion.inquirer.net, PNA opinion). |
| B08 | Cannot yet judge | Not Found | Consistent with the nickname limitation. |
| B12 | Failed | 6× Verified | **Improved.** The "causes" split is gone. Claims 1–5 cite the Philstar opinion column the post appears to be based on; check that you accept a column as the source for what La Viña said. |
| B16 | Failed | 2× Not Found, Review Failed | **Still failing.** The NASA-only post is still checked (out of Philippine scope, plan Step 7). |
| C06 | Failed | 3× Not Found | **Still failing.** "Sen. Robinhood Padilla" is still turned into no speaker (pattern 2), and the final quotation is still not flagged political. |
| C07 | Failed | Verified, Not Found | **Passes**, matching your earlier validation: claim 2 is not in the article. |
| C08 | Failed | Not Found | **Still failing.** The VERA fact-check was not retrieved, and "This is fake" is still dropped as unclear. |

**Patterns found:**

1. **Review Failed (6 claims in A02, A03, A06, A07, B16).** When splitting a claim, the model paraphrases instead of quoting exactly: it fills in ellipses ("investigators are *interviewing witnesses*"), inserts "…", or changes the grammar. The rule that context must be quoted word for word then rejects the answer, the one retry repeats the mistake, and the whole claim fails. Replayed offline from the saved answers.
2. **Speaker set to "unknown" (B04 claim 5, C06).** An attributed statement with no speaker makes the speaker check reject every article; in C06 an explicitly named speaker was lost. This is plan Step 4.
3. **Screening (B07, B16)** is plan Step 7; **C08** is plan Steps 5 and 6.
4. **Speed.** Long posts take minutes because each claim runs its own searches and five or six gpt-4.1 calls in turn: A03 took 741s (12 claims), B04 306s, B12 289s, B07 274s, A05 278s, A02 228s.
