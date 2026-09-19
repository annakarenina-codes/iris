# Held-out batch 1

New posts that IRIS was never developed on. This is the batch that measures accuracy; the 34 development cases cannot, because IRIS was tuned on them.

## 1. Collect posts (you)

Fill in [posts.txt](posts.txt). Each `### POST Hxx` block is one post; unused blocks are skipped.

- Collect **about 25 posts** from Philippine news pages on Facebook, published **after 19 September 2026** and **not** among the 34 development cases or anything you tested while developing.
- Suggested mix:

  | Kind | About | Category value |
  |---|---|---|
  | Straight news in English | 8 | `news` |
  | News in Filipino or Taglish | 5 | `filipino` |
  | Quotes and attributed statements | 4 | `quote` |
  | False or fact-checked claims, as they circulated | 4 | `false_claim` |
  | Opinion, satire, rhetorical or non-news posts | 4 | `opinion_satire` |

- Paste the post text **exactly as shown**, between the `<<<` and `>>>` lines, including hashtags and "See more"/"See less" if you would select them in real use. Text-only posts; image checks are not part of this runner.
- For false claims: find a VERA Files or Rappler fact-check first, then paste the claim as it circulated, not the fact-check's headline.

## 2. Write your expected results before running IRIS (you)

Fill in `EXPECTED OVERALL`, `EXPECTED CLAIMS` and `REFERENCES` **before** step 3, without looking at what IRIS returns. This keeps the evaluation blind. The runner refuses posts whose expected results are empty, and records a fingerprint of what you wrote so later edits are flagged in the report.

`EXPECTED OVERALL` is one of: `Verified`, `Partially Verified`, `Not Found`, `No Checkable Claims`.

IRIS has no "False" label. A false claim is handled correctly when IRIS returns **Not Found**, or marks the part **contradicted**; a Verified or Partially Verified result on a false claim is a **false positive**, the most serious error.

## 3. Run IRIS (Claude or you)

From the repository root:

```bash
python evaluation/heldout-batch-1/heldout.py validate
```

```bash
python evaluation/heldout-batch-1/heldout.py run
```

`run` uses the real backend pipeline with the verdict cache bypassed and TRACE capture on, one post at a time, and saves each result in `results/`. It never overwrites an existing result; delete a result file to rerun that post.

## 4. Judge each claim (you)

```bash
python evaluation/heldout-batch-1/heldout.py review
```

This writes `review.txt` (your judgment sheet) and `REPORT.md` (every claim with its verdict, cited passages and evidence links). For each post, fill in `Routing:` and `Missed claims:`, and a `Judgment:` for every claim, using the options at the top of `review.txt`.

## 5. Score (Claude or you)

```bash
python evaluation/heldout-batch-1/heldout.py score
```

Writes `SCORES.md`: claim-level accuracy, false positives, false negatives, routing accuracy, missed claims, technical failures and response times. Only judged items count; `cannot_judge` is reported separately and excluded from accuracy.
