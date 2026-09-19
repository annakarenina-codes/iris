## Findings (Claude's review, for you to validate)

Run: 17 priority cases on commit `7693397` (new sources, search excerpts, search passes, per-claim errors). This run does **not** include Step 3 or the passage-selection fix. All 17 returned HTTP 200 with no technical failures. The automated checker found no failures; B03 and C01 are flagged for review because their verdicts changed.

| Case | 18 Sept → now | What happened | Status |
|---|---|---|---|
| A01 A04 A10 B02 B06 B09 B10 B11 B13 B14 C05 | unchanged | Same verdicts. Evidence and citations may differ, so check the cited passages. | Your review |
| **B03** claim 2 | Verified → **Not Found** | **Regression from the new search passes.** 33 readable articles (300+ passages, against 6 articles on 18 Sept) overwhelmed the first-pass reviewer, which answered "not supported" while listing 300+ passage IDs. The ABS-CBN and Philstar articles were in the pool. **Fixed** in `d6538dc`, which keeps the 80 most relevant passages. Rerun on the latest code gives **Partially Verified**: the announcement is supported, but claim extraction split "that Austria did not accept…" into its own factual component, which is not established because Roque disputes it. That remainder is an attribution issue (plan Step 4), not retrieval. See `results-latest/B03.json`. | Partly fixed |
| **C01** claim 2 | Verified → **Not Found** | **Step 2 bug, not caused by today's changes.** Context resolution attached "Sept. 23" (Baste's testimony date) to "the Senate impeachment court is examining allegations…". The date rule then rejected all four matching sources for not showing Sept. 23. The 18 Sept baseline passed because it ran before Step 2. | Needs fix |
| C02 | Partially → **Verified** | The Philstar passage states the whole claim word for word and is now accepted. | Improved |
| C03 | Verified, Partially → **Verified, Verified** | "…and I think it's great" is now supported. | Improved |
| B15 claim 3 | Partially → **Verified** | October 10, 2026, The Secret Library and the SM Mall of Asia Arena are supported by Manila Bulletin and Inquirer search excerpts. | Improved |
| B15 claim 1 | Verified → Verified | **Still wrong:** supported by a **2024** Manila Bulletin photo caption ("posted these photos taken in Manila on his Instagram account"). An old Instagram post is not the current update. The claim states no date, so the date rule does not apply. | Unresolved |
| B15 claim 2 | No Search Results → Not Found | "So handsome," commented one netizen is still extracted as a claim; it should be excluded (plan Step 5). | Unresolved |
| C04 claims 1–2 | Verified, Partially → **Verified, Verified** | Supported by a current Manila Bulletin excerpt (11 Sept 2026) with Angara's employer-feedback remark and the 640-hour proposal. The speaker is now kept as Sonny Angara. | Improved |
| C04 claim 3 | Not Found → Not Found | The known GMA article is still not retrieved, and the "he added" statement appears only there. | Unresolved |

Step 3 (commit `9b5975b`) and the passage-selection fix (`d6538dc`) are on branch `step3-evidence-review`; only B03 has been rerun on them.
