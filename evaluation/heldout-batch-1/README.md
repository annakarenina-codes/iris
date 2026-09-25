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

- Paste the post text **exactly as shown**, between the `<<<` and `>>>` lines, including hashtags and "See more"/"See less" if you would select them in real use.
- For false claims: find a VERA Files or Rappler fact-check first, then paste the claim as it circulated, not the fact-check's headline.

### Image posts

Fabricated statements usually circulate as pictures, so the batch should contain some. Save the picture in [images/](images), give its path in the block's `IMAGE:` field (`images/H07.jpg`), and leave `TEXT:` empty.

- **Do not retype the words of the image into TEXT.** That would test IRIS without the part that reads the picture, and a misread name or number is a real result worth recording.
- **Do write them into `IMAGE TEXT:`**, in its own `<<< >>>` block: **the statement that should be checked, not everything printed on the picture**. Branding, hashtags, captions and page names can be left out; OCR will read them and they are not counted against the result. That text is never sent to IRIS. It is compared with what OCR produced, and the report shows both with the share of the statement's words that survived; `SCORES.md` carries the median and the worst. Without it, a verdict on a misread claim cannot be told from a verdict on the right one. A post that records it does not need EXPECTED CLAIMS.
- Save it as a phone screenshot, not a cropped or sharpened copy: under 8 MB, `.jpg .jpeg .png .webp .bmp .tif .tiff`.
- If a post has both a picture and a caption, use the picture. IRIS reads one or the other, as the extension and the phone app do.
- The runner sends these to `/verify-image`, and records what OCR read next to the verdict, so an image failure can be attributed to the reading or to the checking.

### Posts by VERA Files

Two posts by VERA Files itself are worth including, because an expert will try one. Expect either result, and record which happened: **Verified** when IRIS checks the post's own statement ("VERA Files found X is fake") against the fact-check, or **Refuted** when it checks the claim inside the post. Both are right. Note in the thesis that such a check rests on one publisher, the same one that made the post: `corroboration_count` in the result shows how many sources stood behind the verdict. Prefer one fact-check card and one piece of their ordinary reporting, so the two posts do not test the same path twice.

## 2. Write your expected results before running IRIS (you)

Fill in `EXPECTED OVERALL`, `EXPECTED CLAIMS` and `REFERENCES` **before** step 3, without looking at what IRIS returns. This keeps the evaluation blind. The runner refuses a post with no `EXPECTED OVERALL`, and records a fingerprint of what you wrote so later edits are flagged in the report.

`EXPECTED CLAIMS` is optional, and the runner only warns when a post has none. What you lose by leaving them out:

- **The missed-claim count** becomes a judgment you make while reviewing, from the post in front of you, instead of a comparison against what you wrote beforehand.
- **Wrong-level judgments** (Verified where Partially Verified was right) rest on your reading at review time rather than on a stated expectation.

What you keep: `EXPECTED OVERALL` still records, before the run, what you thought the post deserved, and the fingerprint still flags any later edit. That is enough for claim accuracy, false positives and false negatives, which are judged per claim in `review.txt` anyway.

Worth writing claims for even if you skip the rest: the `false_claim` posts, where the verdict turns on one specific statement.

`EXPECTED OVERALL` is one of: `Verified`, `Partially Verified`, `Not Found`, `No Checkable Claims`.

`Refuted` is IRIS's verdict for a claim that VERA Files has published a finding against; it was added on 20 September 2026 and only VERA Files can trigger it. For a false claim, **Refuted** is the best outcome and **Not Found** is acceptable, since no fact-check may exist yet. A **Verified or Partially Verified result on a false claim is a false positive**, the most serious error.

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
