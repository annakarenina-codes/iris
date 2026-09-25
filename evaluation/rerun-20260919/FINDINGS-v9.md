## Findings (final run on `3be6db9`)

All 17 priority cases, plus both B02 input versions, ran with HTTP 200 and no technical failures.

**Every case matches your review of the first run, and the three claims you marked wrong are fixed apart from C04 claim 3.**

| Case | Your review (first run) | Final | Notes |
|---|---|---|---|
| A01 A04 A10 B02 B06 B09 B10 B11 B13 B14 C02 C03 C05 B15 | correct | same verdicts | Spot-check cited passages: evidence can differ between runs. |
| B03 | incorrect (claim 2) | **Verified, Verified** | Reported speech is judged as one statement. |
| C01 | incorrect (claim 2) | **Verified, Verified** | Baste's "Sept. 23" is no longer required for the court's examination. |
| C04 | incorrect | **Verified, Verified**, Not Found | Claims 1–2 verified by the 11 Sept Manila Bulletin excerpt. Claim 3 exists only in the GMA article missing from the search index (OPEN-ISSUES.md). |
| B02 Filipino (as scanned) | – | **Verified** | Philstar "Palace leaves impeachment vote threshold to Senate". |
| B02 Facebook English translation | – | **Verified** (also 4 of 4 in earlier runs on this commit) | Same Philstar article. |

**Changes behind the B02 result:**

1. A part ending in "said", "stated", "according to" and similar verbs is rejoined with its content, with or without "that".
2. The first-pass assessment uses gpt-4.1: on the identical saved request, gpt-4o-mini chose general "won't interfere" passages, while gpt-4.1 chose the vote-threshold passages.
3. The final check treats Malacañang, the Palace and the Office of the President as the same entity.

**Cost of change 2: speed.** The gpt-4.1 first pass adds about 7,500 input tokens per claim and brings back OpenAI rate-limit waits in back-to-back runs:

| Case | Rate-limit waits (s) | Final time | Previous time |
|---|---|---|---|
| A10 | 20, 17, 6 | 77s | 29s |
| B10 | 5, 1, 18, 10 | 78s | 36s |
| C01 | 1, 7, 3 | 166s | 60s |

C01 exceeds the Android app's 120-second read timeout. Options are listed in the chat summary.
