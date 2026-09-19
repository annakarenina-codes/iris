## Findings (Claude's review of the final run)

Final 17-case run on `dfc6920` (Step 3, first-pass shortlist, borrowed-date and reported-speech fixes, full-sentence queries restored). C01 was then fixed again in `143fd90` and rerun twice (`results-v5a`, `results-v5b`): **Verified, Verified** both times. All runs returned HTTP 200 with no technical failures.

**Against your review of the first run: 16 of 17 cases now match what you judged correct.**

| Case | Your review (first run) | Final | Notes |
|---|---|---|---|
| A01 A04 A10 B06 B09 B10 B11 B13 B14 C02 C03 C05 B15 | correct | same as the run you reviewed | Unchanged verdicts. The cited passages can differ between runs, so spot-check them. |
| B02 | correct | Verified | Briefly regressed on `74ef8ed` (keyword query), fixed by restoring full-sentence queries. |
| **B03** | incorrect (claim 2) | **Verified, Verified** | Claim 2 is now judged as "did Remulla announce this?" and is supported by Philstar and ABS-CBN reports. |
| **C01** | incorrect (claim 2) | **Verified, Verified** (on `143fd90`, twice) | "Sept. 23" belongs to Baste's testimony and is no longer required for the court's examination. |
| C04 | incorrect | Not Found, Verified, Not Found | Claim 2 is supported by the 11 Sept Manila Bulletin excerpt. Claim 1 was Verified in the first run from the same excerpt, but the final check now judges "Angara cited employer feedback" as not saying DepEd has "still work to be done": a borderline paraphrase. Claim 3 exists only in the GMA article that the search provider does not index (see OPEN-ISSUES.md). |

**Run-to-run variation seen across the four runs today.** The model calls run at temperature 0 but are not fully deterministic:

- A01 was once extracted as a factual claim (Not Found) instead of No Checkable Claims.
- B03 claim 2 was once rejected by the first-pass reviewer. This is now mitigated: its listed passages always reach the stricter checks.
- C04 claim 1 flips on a borderline paraphrase.

Search results also change over time as new articles are indexed.

Open issues (not addressed, see `evaluation/OPEN-ISSUES.md`): B15 claim 1 is verified by a 2024 Instagram caption; GMA articles for C04, A09 and B05 are missing from the search index.
