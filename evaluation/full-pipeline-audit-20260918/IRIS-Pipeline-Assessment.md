# IRIS: Consolidated Pipeline Assessment

Audit date: 18 September 2026. This is a development-set diagnosis, not a production accuracy claim.

## Start Here

Fresh runs saved: **34 of 34**. **13 passed; 18 failed; 3 cannot yet judge.**

A pass means the specified behavior and cited support were checked in this run. A failure means at least one concrete defect or technical failure was found. Cannot yet judge means the remaining reference evidence is insufficient; it does not mean the post is false.

The strongest recurring safety issue is loss of context between a whole assertion and its smaller components. Search also has gaps, but not every Not Found result is a search failure.

## What Was Tested

- Original ten requests (A01-A10), second batch of sixteen (B01-B16), and eight saved recent text inputs (C01-C08).
- Current backend source files were hashed and frozen. Existing source changes were preserved. No production code was changed for this audit.
- Each request used the configured live services through the Flask verification route with debug capture; verdict-cache reads and writes were bypassed.
- Recorded models: gpt-4o-mini for the default model, gpt-4.1-2025-04-14 for claim coverage and evidence review. The high-stakes reviewer is already using the stronger configured model; these defects cannot be explained as mini-only verdicts.
- Requests were sequential. These are current reruns, not reconstructed historical executions. New blind-test outcomes without TRACE remain user reports.
- Known-URL controls bypass search deliberately. They test downloading/extraction and, separately, evidence review. They do not count as automatic retrieval success.
- All cases were previously examined during development. They are not a held-out benchmark. OCR, Android and extension UI are not covered by these text runs.

## Priority Order

1. Preserve subject, event, time and qualifiers in every evidence component. A detached arrested or causes fragment must not receive its own verdict credit.
2. Make attribution matching recognize supported name variants and resolve court/institution references from context, without inventing a speaker or accepting topic overlap.
3. Reconcile evidence selections: an exact date passage already accepted for event identity must be available to the final qualifier check.
   Also distinguish omission from contradiction: one article not repeating a quote does not invalidate another article that directly contains it.
4. Repair targeted retrieval/extraction failures using the known-reference controls, with bounded alternative queries and publisher-page handling.
5. Repair screening/coverage errors, then rerun these exact regressions and a genuinely new held-out batch.
6. Handle rate limits with measured request/token scheduling. A larger model alone does not fix deterministic gates, absent evidence or discarded context.

## First Confirmed Failure

One primary stage per failed case is counted below. Contributors may overlap. This is not a count of every error and is not a universal ranking for all possible news.

| Stage | Cases |
|---|---:|
| claim_extraction | 6 |
| evidence_review | 6 |
| attribution | 2 |
| screening | 2 |
| technical | 1 |
| retrieval | 1 |

Including contributing defects (overlapping cases): component_context: 10; evidence_review: 10; claim_extraction: 7; attribution: 4; technical: 2; screening: 2; retrieval: 2; article_extraction: 1; political_flags: 1.
Technical failures are counted separately from incorrect factual judgments. A03 has both a demonstrated extraction omission and a later rate-limit failure; A05 has no completed verdict to grade.

## Compared With Earlier Records

- Previously blocked translation/screening inputs now reach verification in several cases, including Bea Borres, EDSA, the peso and National Artists. This is progress, not proof their final results all pass.
- Malacanang attribution now works in B02/B03. The different Robinhood/Robin and null judges failures remain, so attribution is not completely solved.
- A05 now extracts the quoted statements and bail fact, but the live run fails at evidence review due to a rate limit.
- The exact fan-meeting, Eala and Rene articles are now retrieved. Fan-meeting and Eala still suffer downstream rejection; Rene succeeds.
- DepEd remains a known-article retrieval gap. Other reference gaps are not automatically counted as search misses.
- Historical snippets, prior versions and fresh runs are not directly interchangeable. This comparison is qualitative; it is not an old-versus-new accuracy percentage.

## Case Summary

| ID | Topic | Assessment | First failure | Reason |
|---|---|---|---|---|
| A01 | Imaginary nine-dash-line ownership | Passed | - | Imaginary framing did not become a literal ownership verdict; no claims were submitted for evidence review. Pass is limited to this routing behavior. |
| A02 | Padilla-Wamil hearing exchanges | Failed | attribution | The correct ABS-CBN article was retrieved and extracted (491 words), but the Robinhood Padilla speaker anchor rejected Robin Padilla. Claim 2 also contains a detached recruitment component. This is not a missing-search result. |
| A03 | Kent Carpenter biography and killing | Failed | claim_extraction | The extraction coverage ledger excludes UNESCO advocacy as evaluative, although advocacy is a checkable activity. The run then stops with review_rate_limited (HTTP 503); no final accuracy verdict is available. Summary and detailed death assertions remain separate. |
| A04 | Bea Borres reunion and co-parenting denial | Passed | - | Both reunion and the attributed co-parenting denial have direct ABS-CBN passages. The denial is labeled as attribution, not independent proof about private family arrangements. |
| A05 | Padilla Senate position and Duterte bail | Failed | technical | HTTP 503 review_rate_limited prevents a completed result. The saved extraction now includes both quoted statements and the bail fact; this improves coverage but does not prove their verdicts correct. |
| A06 | EDSA rehabilitation and Sonza criticism | Failed | evidence_review | The affected-area claim is Verified using December rehabilitation schedules, which establish where work began, not which sections later developed damage. The damage context was lost. Sonza attribution remains unconfirmed, not disproven. |
| A07 | Padilla medicines and terrorism | Failed | claim_extraction | The entire assertion appears as one claim and its funds rationale appears again as a second claim. Correct ABS-CBN evidence supports several components; the rationale remains unconfirmed. Partial support itself is not the failure; duplicated coverage is. |
| A08 | Samaniego video game interview | Cannot yet judge | - | All eight claims are Not Found. Existing related coverage does not establish the exact DZRH/program/date/quotation combination. Do not relax attribution merely to force a positive verdict; exact-event reference remains a gap. |
| A09 | Peso closing exchange rate | Failed | evidence_review | The partial verdict credits the direction of movement from an article about the previous session (62.625), while the asserted September 9 close is 62.513. Session/date context must stay attached. The known rate reference extracts only 43 words, an additional extraction limitation. |
| A10 | Ten National Artists | Passed | - | The ABS-CBN Lifestyle article directly supports ten new National Artists and the award description. This confirms the expanded publisher section is usable in this run. |
| B01 | Perez death investigation / NBI Matibag | Cannot yet judge | - | Two Perez/mother claims have relevant Philstar passages. Matibag's case-specific announcement remains Not Found, correctly avoiding unrelated NBI investigations. Full-case pass requires a reference for the Matibag statement. |
| B02 | Palace conviction threshold | Passed | - | Malacanang's hands-off position on the conviction vote threshold is directly supported by retrieved ABS-CBN and Philstar passages; the earlier attribution mismatch is not reproduced. |
| B03 | Palace advice on confidential operations | Passed | - | Evidence supports Palace advice to DILG and that Remulla announced the asylum denial. The latter is an attributed announcement, not proof that the disputed denial actually occurred. |
| B04 | ICC second detention review | Failed | attribution | The expert-panel detention quotation is assigned a null speaker with role judges, then every article is rejected for missing speaker, including the relevant GMA and Philstar reports. Other court quotations were successfully reviewed. |
| B05 | Arrest after shooting ex-partner new companion | Failed | evidence_review | The reviewer explicitly recognizes a different victim/motive, but credits the detached component arrested using that different shooting. The resulting Partially Verified is unsafe cross-event support. |
| B06 | Prediction about senator-judges motives | Passed | - | The political prediction/opinion produces no checkable claims and no search, consistent with the expected routing. |
| B07 | Vote wisely civic appeal | Failed | screening | Generic vote-wisely advocacy becomes six claims and consumes roughly four minutes. One value-laden consequence statement is Verified using vote-buying commentary. Opinion agreement is not factual verification. |
| B08 | Solar boy nickname | Cannot yet judge | - | The unresolved nickname produces Not Found. No formal identity should be guessed. This is consistent with the accepted limitation, but cannot establish the underlying statement's truth. |
| B09 | Rhetorical mugshot questions | Passed | - | Rhetorical mugshot commentary stops without invented factual claims or unnecessary search. |
| B10 | Loren return speculation and imprisonment | Passed | - | The factual former-Speaker jail clause is retained and supported by the matching ABS-CBN Payatas report; the speculative political return is not presented as a verified event. |
| B11 | BIR VAT on system loss | Passed | - | The BIR VAT removal fact is directly supported by the matching ABS-CBN report; congratulatory commentary is not turned into extra claims. |
| B12 | Loren defense commentary | Failed | claim_extraction | The mixed essay loses checkable event/background details. Even a verbatim supported environmental-causes statement becomes Partially Verified after causes is split into an unsupported one-word component. De Lima's nearly seven years is also promoted to unqualified seven years. |
| B13 | Imagined Robin questions | Passed | - | Anticipated/imagined Padilla questions are not treated as something he actually said; the run returns no checkable claims. |
| B14 | Carpio detention and quorum quote | Passed | - | The Carpio quotation is supported verbatim by the Philstar report. This is a pass for attribution, not an independent legal ruling. |
| B15 | Byeon Woo-seok fan meeting | Failed | claim_extraction | An anonymous handsome opinion is extracted; an old Instagram photo report supports an unspecified current update. The correct fan-meeting article is found, but the date is downgraded because final selected passages omit 2026, even though event-identity evidence includes the explicit October 10, 2026 quote. |
| B16 | NASA galaxy composite image | Failed | screening | The NASA-only post proceeds to three claims and search despite the expected Philippines scope restriction. Not Found does not explain that scope limitation. |
| C01 | Baste subpoena | Passed | - | The GMA report explicitly states the subpoena and September 23 appearance date, alongside the unexplained-wealth trial context. An earlier ABS-CBN tentative-summons passage is not sufficient alone, but the later explicit GMA evidence supports the assertion. |
| C02 | Zuckerberg DICT budget | Failed | evidence_review | Philstar's extracted opening sentence matches the entire claim verbatim. The final reviewer nevertheless rejects violence and child safety while acknowledging that same passage confirms both. This is a contradictory evidence judgment, not missing retrieval. |
| C03 | Eala and Wintour | Failed | evidence_review | The correct ABS-CBN article and full Wintour quote are present. The reviewer rejects I think it is great because only one of two passages contains it, inventing a requirement that every passage repeat the whole quote. One valid supporting passage should not be cancelled by another passage's omission. |
| C04 | DepEd longer OJT | Failed | retrieval | The known GMA 640-hour article is absent from recorded search/extraction, but direct extraction returns 906 words including the figures. IRIS credits only Angara's job title toward the proposal, yielding misleading partial support; older employability coverage substitutes for the current statement. The final He added claim also loses explicit speaker resolution. |
| C05 | Rene Baterbonia UST | Passed | - | The matching ABS-CBN sports article is retrieved and directly supports the lack of prior UST connection and the reported family support. The earlier missing-source symptom is not reproduced. |
| C06 | Padilla plans and political warnings | Failed | claim_extraction | The explicitly named Sen. Robinhood Padilla becomes a null speaker in attribution metadata, causing automatic speaker rejection. The final Padilla quotation also has politically_sensitive false despite the explicit official-speaker context. Exact-event reference evidence is still missing, so a positive verdict cannot yet be prescribed. |
| C07 | Moira September 17 media appearance | Failed | evidence_review | The September 17 media appearance remains unconfirmed, but the follow-on healing statement receives partial support from a 2022 breakup interview. The post's event context is lost across claims. The known September 14 Spotify article is only a related reference, not proof of the September 17 appearance. |
| C08 | VERA Poquiz false attribution | Failed | claim_extraction | This is fake is discarded as unclear instead of being linked to the preceding alleged quotation. The known VERA fact-check is absent from recorded retrieval, while direct extraction returns 530 words. Preserve the allegation and its denial without assuming either is true before review. |

## Stage Reach and Limits

Counts below use saved spans or dependency artifacts. Missing capture is unknown, not proof a stage did not run. Later stages may be undercounted. Aggregate call durations are not wall-clock stage durations because article work is parallel.

| Stage | Runs with execution evidence | Baseline runs |
|---|---:|---:|
| translation | 34 | 34 |
| screening | 34 | 34 |
| claim_extraction | 32 | 34 |
| retrieval | 30 | 34 |
| article_extraction | 30 | 34 |
| attribution | 30 | 34 |
| evidence_review | 27 | 34 |
| delivery | 12 | 34 |

TRACE has bounded event capture (1 MiB per request and 64 KiB per event). Many traces are marked partial. Full saved response files and dependency artifacts help, but cannot recover information that was never captured. Partial capture is not the same as a failed verification.

## Known Article Checks

Yes means the exact normalized URL was recorded. Credited means at least one component used it, not that every claim admitted it (A02 is an important example). No means it was not observed in that saved collection; with partial capture, absence alone is not definitive proof it was never seen. Direct word count does not by itself prove relevant or correct extraction.

| Case | Reference | In search | Extracted in run | Credited | Direct extraction |
|---|---|---|---|---|---|
| A02 | [S01](https://www.abs-cbn.com/news/nation/2026/8/5/padilla-tests-auditor-on-knowledge-of-terrorism-security-threats-1501) | Yes | Yes | Yes | extracted, 491 words |
| A03 | [S03](https://www.philstar.com/headlines/2026/07/15/2542349/universities-green-groups-demand-justice-slain-marine-biologist-kent-carpenter) | No | No | No | extracted, 895 words |
| A03 | [S04](https://www.philstar.com/headlines/2026/07/15/2542350/robbery-eyed-american-scientists-killing-after-home-ransacked) | Yes | Yes | No | extracted, 559 words |
| A03 | [S17](https://www.philstar.com/headlines/2016/07/12/1602113/verdict-philippines-wins-arbitration-case-vs-china/amp/) | No | No | No | extracted, 547 words |
| A03 | [S18](https://www.gmanetwork.com/news/topstories/regions/994769/american-marine-biologist-shooting-negros/story/) | Yes | Yes | No | extracted, 289 words |
| A04 | [S05](https://www.gmanetwork.com/entertainment/showbiznews/bea-borres-reacts-to-criticism-over-video-reunion-with-ex-boyfriend-meray-yamada/138114/) | Yes | Yes | Yes | extracted, 317 words |
| A05 | [S15](https://newsinfo.inquirer.net/2300646/padilla-why-not-extend-presidential-immunity-from-suit-to-vp-duterte) | No | No | No | error, 0 words |
| A06 | [S07](https://tribune.net.ph/2026/08/10/p6-b-edsa-rehab-marred-by-potholes) | No | No | No | skipped, 0 words |
| A07 | [S01](https://www.abs-cbn.com/news/nation/2026/8/5/padilla-tests-auditor-on-knowledge-of-terrorism-security-threats-1501) | Yes | Yes | Yes | extracted, 491 words |
| A08 | [S08](https://www.philstar.com/headlines/2026/06/26/2537982/gorebox-developer-rejects-senate-invitation-tacloban-school-shooting-probe) | No | No | No | extracted, 620 words |
| A09 | [S20](https://www.philstar.com/other-sections/forex-stocks/2026/09/09/2555147/162513) | No | No | No | extracted, 43 words |
| A10 | [S11](https://www.abs-cbn.com/lifestyle/people-culture-events/2026/9/9/ten-new-national-artists-named-2117) | Yes | Yes | Yes | extracted, 144 words |
| A10 | [S12](https://www.philstar.com/lifestyle/2026/09/10/2555313/bing-lao-nicanor-tiongson-among-10-new-national-artists/amp/) | No | No | No | extracted, 264 words |
| B15 | [R-fanmeet](https://www.abs-cbn.com/entertainment/showbiz/events/2026/6/9/byeon-woo-seok-returning-to-ph-for-october-fan-meet-1729) | Yes | Yes | Yes | extracted, 188 words |
| C03 | [R-eala](https://www.abs-cbn.com/entertainment/showbiz/celebrities/2026/9/14/alex-eala-shares-front-row-with-anna-wintour-at-new-york-fashion-week-show-2307) | Yes | Yes | Yes | extracted, 427 words |
| C04 | [R-deped](https://www.gmanetwork.com/news/topstories/nation/1001536/are-k-12-grads-ready-for-work-adult-life-deped-eyes-longer-ojt/story/) | No | No | No | extracted, 906 words |
| C05 | [R-rene](https://www.abs-cbn.com/sports/basketball/2026/9/16/-para-kay-rene-ust-dedicates-uaap-season-89-campaign-to-baterbonia-family-2352) | Yes | Yes | Yes | extracted, 383 words |
| C07 | [R-moira](https://www.abs-cbn.com/entertainment/showbiz/music/2026/9/14/moira-dela-torre-hits-11-million-followers-on-spotify-1247) | No | No | No | extracted, 145 words |
| C08 | [R-vera](https://verafiles.org/articles/fact-check-romeo-poquiz-did-not-make-viral-statement-vs-marcoses) | No | No | No | extracted, 530 words |

## Controlled Evidence Reviews

The following runs were given a known article. They are diagnostic model outputs, not independent truth labels and not retrieval passes. Full-input controls may include editorial wording that would normally be screened out.

- A07: Partially Verified; status ok. [Saved control](reference-controls/A07-review.json).
- B15: Not Found; status ok. [Saved control](reference-controls/B15-review.json).
- C04: Verified; status ok. [Saved control](reference-controls/C04-review.json).
- C07: Not Found; status ok. [Saved control](reference-controls/C07-review.json).
- C08: Partially Verified; status ok. [Saved control](reference-controls/C08-review.json).

What these controls mean:

- C04 is the clearest retrieval isolation: supplying the exact GMA article changes the evidence review to Verified for the substantive statements. It does not prove the normal search can find it or repair the per-claim speaker gate.
- C08 still misses the meaning of This is fake after VERA is supplied. Retrieval is therefore not its only defect.
- A07 remains Partially Verified, but its supported components change: the control rejects personal background and accepts the funds rationale, opposite to parts of the baseline. The label alone hides unstable reasoning. These runs differ in evidence pools and are not a pure repeatability experiment.
- B15 uses the June reference, which lacks the explicit year in its body. The baseline also found an August article containing 2026. The control therefore cannot be compared as an identical-evidence test; it illustrates how passage availability changes the result.
- C07 correctly receives no support from the supplied Spotify article for the September 17 event. Related celebrity coverage is not a substitute for that specific appearance.

## Search Findings in Plain Language

There are two clear failed cases with known, readable target articles absent from recorded retrieval: **C04 (DepEd)** and **C08 (VERA/Poquiz)**. This is a lower bound from checked references, not an estimate that only two of all 34 inputs had imperfect search. A09 also has a missing exact-rate reference and a thin direct extraction, so its search-versus-extraction contribution is not isolated.

A02, B15, C02 and C03 demonstrate the opposite situation: relevant articles reached the system, but later matching or selection failed. Searching more would not by itself repair these specific defects.

Current search code requests five candidates per publisher and extracts the first two. The language backup triggers on fewer than two total results, not on whether usable evidence was found. Therefore unrelated hits can suppress backup search, and a relevant lower-ranked result can be left unread. These are verified code risks, not proof that either caused every missed article.

## Next Fix Acceptance Tests

| Fix | Must improve | Must not regress |
|---|---|---|
| Context-preserving components and evidence decisions | B05 must not credit a different arrest; B12 must not split causes; C02/C03 must accept direct support without requiring every passage to repeat it | Keep genuine partial support when a real factual component is unsupported |
| Attribution resolution | A02 Robinhood/Robin with supporting identity context; B04 judges/ICC context; C06 explicit named speaker retained | B01 must not borrow Matibag statements from another investigation |
| Citation selection and qualifiers | B15 retain the explicit 2026 passage through the final check | A09 must not substitute another trading session; C07 must not substitute a 2022 interview |
| Targeted search recovery | Retrieve the known C04 and C08 target URLs automatically, then extract their relevant passages | Do not count manual URL injection as a retrieval pass or broaden the approved publisher policy silently |
| Coverage and routing | Retain A03 advocacy and C08 denial context; stop B07/B16 appropriately | Keep A05 quotations/bail and the passing B06/B09/B13 exclusions |
| Reliability | A03/A05 complete or return an explicit technical error with reproducible service diagnostics | Never turn a rate limit into a factual Not Found verdict |

## Evidence and Reproduction

- [Case inputs](cases.json), [expected behavior](expectations.json), [machine-readable assessment](assessment-matrix.json), [source/config baseline](baseline-manifest.json).
- [Observed stage data](observations.json). Each case below links its raw result and TRACE ID; historical captures are preserved separately.
- No percentage here should be described as real-world IRIS accuracy. Reference gaps, previously tuned cases, partial captures and rate-limited requests prevent that conclusion.

## Per-Case Record

### A01: Imaginary nine-dash-line ownership

**Passed**. Imaginary framing did not become a literal ownership verdict; no claims were submitted for evidence review. Pass is limited to this routing behavior.

Expected: Preserve imaginary/satirical framing; do not assert literal ownership or invent missing image context.

Observed: HTTP 200; 6.934 seconds; TRACE `8dd9cd74946e46259e2897b925dfa468`; capture complete.
[Saved response](current-baseline/A01.json) | [TRACE snapshot](current-trace-snapshots/A01.json)

- No delivered claims. Result/error: No Checkable Claims.

### A02: Padilla-Wamil hearing exchanges

**Failed**. The correct ABS-CBN article was retrieved and extracted (491 words), but the Robinhood Padilla speaker anchor rejected Robin Padilla. Claim 2 also contains a detached recruitment component. This is not a missing-search result.

Expected: Preserve full attributed questions and replies, BARMM/terrorism, AOM/funds, evaluation correction, agent names and classified answer. Merge repeated utterances.

Observed: HTTP 200; 137.236 seconds; TRACE `18ebdda0a7f847158d21b91db2ed7cd0`; capture partial.
[Saved response](current-baseline/A02.json) | [TRACE snapshot](current-trace-snapshots/A02.json)

- **Not Found**: Senator-judge Robinhood Padilla asked former state auditor Roderick Wamil if he had ever visited the Bangsamoro Autonomous Region in Muslim Mindanao (BARMM) and whether he was aware of the country's ongoing terrorism threats.
- **Not Found**: Padilla raised preliminary questions about the Audit Observation Memorandum, trying to establish ties to the confidential funds used by Vice President Sara Duterte for surveillance on potential New People's Army (NPA) recruitment.
- **Not Found**: "But you are the one handling the investigation regarding the confidential funds, is that correct?" Padilla asked Wamil.
- **Verified**: "It is not an investigation. It is an evaluation," the witness answered.
- **Not Found**: "Do you believe that confidential agents should identify themselves? State their real names," the senator furthered.
- **Verified**: "There are no provisions regarding that in the joint circular," Wamil said.
- **Not Found**: Padilla then asked Wamil to define "confidential," to which the auditor replied, "classified."

### A03: Kent Carpenter biography and killing

**Failed**. The extraction coverage ledger excludes UNESCO advocacy as evaluative, although advocacy is a checkable activity. The run then stops with review_rate_limited (HTTP 503); no final accuracy verdict is available. Summary and detailed death assertions remain separate.

Expected: Cover death, companion, investigation, police quote, 1975 work, written/oral testimony, tribunal ruling, Verde research, UNESCO advocacy and tributes. Exclude eulogy. Retain conflicting incident accounts and dates.

Observed: HTTP 503; 125.468 seconds; TRACE `41aee5e0d27648e6a55b185b032403bf`; capture partial.
[Saved response](current-baseline/A03.json) | [TRACE snapshot](current-trace-snapshots/A03.json)

- No delivered claims. Result/error: review_rate_limited.

### A04: Bea Borres reunion and co-parenting denial

**Passed**. Both reunion and the attributed co-parenting denial have direct ABS-CBN passages. The denial is labeled as attribution, not independent proof about private family arrangements.

Expected: Retain reunion and scope of attributed denial. Not co-parenting as a couple is narrower than no co-parenting at all.

Observed: HTTP 200; 50.278 seconds; TRACE `886e77c7a5564d74835eeb5856e15f75`; capture partial.
[Saved response](current-baseline/A04.json) | [TRACE snapshot](current-trace-snapshots/A04.json)

- **Verified**: Bea Borres and her ex, Meray Yamada, are back in the same frame.
- **Verified**: Bea Borres made it clear that their reunion doesn’t mean they’re co-parenting their daughter, Victoria Hope.

### A05: Padilla Senate position and Duterte bail

**Failed**. HTTP 503 review_rate_limited prevents a completed result. The saved extraction now includes both quoted statements and the bail fact; this improves coverage but does not prove their verdicts correct.

Expected: Retain Article 11 Section 2 attribution, impeachment statement, complete request to Senate with recipient, and bail amount/count/people. No opinion-to-fact conversion.

Observed: HTTP 503; 163.066 seconds; TRACE `6fcfba9d73154f37b88e9402f1a0c3be`; capture partial.
[Saved response](current-baseline/A05.json) | [TRACE snapshot](current-trace-snapshots/A05.json)

- No delivered claims. Result/error: review_rate_limited.

### A06: EDSA rehabilitation and Sonza criticism

**Failed**. The affected-area claim is Verified using December rehabilitation schedules, which establish where work began, not which sections later developed damage. The damage context was lost. Sonza attribution remains unconfirmed, not disproven.

Expected: Keep damage, locations, project start, estimated P1.2 billion, Sonza criticism and time-bounded no-response assertion. Do not conflate project budgets or invent as-of date.

Observed: HTTP 200; 149.681 seconds; TRACE `8827cc9333844183a09bd5a5bf9ecbfd`; capture partial.
[Saved response](current-baseline/A06.json) | [TRACE snapshot](current-trace-snapshots/A06.json)

- **Partially Verified**: Several sections of the road undergoing reblocking have developed potholes and peeling despite having been recently completed.
- **Verified**: Affected areas include several sections of the EDSA Busway and parts of Phase 1 of the road reblocking project that started on Christmas Eve of last year.
- **Verified**: The cost of the project is estimated to reach P1.2 billion.
- **Not Found**: Jay Sonza criticized the Department of Public Works and Highways (DPWH) under Secretary Vince Dizon.
- **Not Found**: Jay Sonza questioned why certain parts of EDSA have damaged so quickly despite the large funds allocated for the rehabilitation.
- **Not Found**: Dizon has not issued any statement regarding the criticisms and the report about the condition of some newly repaired sections of the main thoroughfare in Metro Manila.

### A07: Padilla medicines and terrorism

**Failed**. The entire assertion appears as one claim and its funds rationale appears again as a second claim. Correct ABS-CBN evidence supports several components; the rationale remains unconfirmed. Partial support itself is not the failure; duplicated coverage is.

Expected: Keep the entire assertion and separately assess background/exposure, medicines, terrorism and claimed funds rationale. Security rationale alone does not prove medicines rationale.

Observed: HTTP 200; 61.466 seconds; TRACE `b06b89ddb36246c29b9d111fc5241283`; capture partial.
[Saved response](current-baseline/A07.json) | [TRACE snapshot](current-trace-snapshots/A07.json)

- **Partially Verified**: Senator-judge Robin Padilla asks state auditor Roderick Wamil about his personal background, noting whether he understood the need for medicines in far-flung areas and the threat of terrorism in the country—issues cited as among the reasons for Vice President Sara Duterte’s use of confidential funds.
- **Not Found**: The need for medicines in far-flung areas and the threat of terrorism are cited as among the reasons for Vice President Sara Duterte’s use of confidential funds.

### A08: Samaniego video game interview

**Cannot yet judge**. All eight claims are Not Found. Existing related coverage does not establish the exact DZRH/program/date/quotation combination. Do not relax attribution merely to force a positive verdict; exact-event reference remains a gap.

Expected: Preserve speaker, DZRH Special on Saturday July 4, quotations, online-contacts argument, more than 20 games, ratings argument and hypothetical cinema analogy. Other interview dates/stations are not the same event.

Observed: HTTP 200; 101.333 seconds; TRACE `e803ed6ac434423b9ae2dc2a3c2f2fc4`; capture partial.
[Saved response](current-baseline/A08.json) | [TRACE snapshot](current-trace-snapshots/A08.json)

- **Not Found**: Art Samaniego Jr., a cybersecurity and technology expert, said that the rush to blame video games for school violence is not supported by science.
- **Not Found**: Art Samaniego Jr. cited research by the Oxford Internet Institute showing no direct link between violent video games and real-world crime or violence.
- **Not Found**: "I am playing Call of Duty, I never thought of shooting outside. Many studies have been done proving that there is no solid evidence saying that video games directly cause school violence or crime in real life," Art Samaniego Jr. said.
- **Not Found**: Art Samaniego Jr. said the real cause of the Tacloban school shooting was not GoreBox—the game the 14-year-old shooter allegedly played—but the people the child was communicating with online, and that extremist recruiters and online predators follow children across platforms regardless of which game or app they use.
- **Not Found**: "The real reason is not the game, but the people the child was talking to online. What we should do is not ban the game, but look at the overall issue," Art Samaniego Jr. said.
- **Not Found**: Art Samaniego Jr. warned that banning GoreBox specifically is futile since more than 20 similar games exist on mobile platforms alone, and more on PC and console—and children, he said, have no loyalty to specific platforms and will simply migrate to the next available option.
- **Not Found**: Art Samaniego Jr. said the real enforcement gap is not the existence of violent games but the failure to implement existing age ratings—GoreBox is an 18+ game that a 14-year-old was able to access—drawing a direct comparison to the MTRCB film rating system.
- **Not Found**: "It’s like with the MTRCB, there is a rating. If MTRCB has a film made by Vivamax and a 12-year-old watched it, are we going to shut down Vivamax? Or will we look at why they got into the cinema due to wrong implementation? That’s what lawmakers should think," Art Samaniego Jr. said.

### A09: Peso closing exchange rate

**Failed**. The partial verdict credits the direction of movement from an article about the previous session (62.625), while the asserted September 9 close is 62.513. Session/date context must stay attached. The known rate reference extracts only 43 words, an additional extraction limitation.

Expected: Preserve PHP62.513 per USD1, Wednesday September 9, and distinguish low level from day-on-day depreciation.

Observed: HTTP 200; 29.597 seconds; TRACE `69bbd986147d43989f5f9e4807c4c95d`; capture partial.
[Saved response](current-baseline/A09.json) | [TRACE snapshot](current-trace-snapshots/A09.json)

- **Partially Verified**: The exchange rate of the peso against the dollar remains down, closing at ₱62.513 = $1 this Wednesday, September 9.

### A10: Ten National Artists

**Passed**. The ABS-CBN Lifestyle article directly supports ten new National Artists and the award description. This confirms the expanded publisher section is usable in this run.

Expected: Retain announcement of ten artists and award description. Do not discard a documented announcement merely because recognition is forthcoming.

Observed: HTTP 200; 25.797 seconds; TRACE `1881304de2a5431e86b247c401395a6b`; capture partial.
[Saved response](current-baseline/A10.json) | [TRACE snapshot](current-trace-snapshots/A10.json)

- **Verified**: Ten exemplary Filipinos from various fields of the arts will be proclaimed as National Artists, the country’s highest national recognition for distinct and significant contributions to the arts and letters.

### B01: Perez death investigation / NBI Matibag

**Cannot yet judge**. Two Perez/mother claims have relevant Philstar passages. Matibag's case-specific announcement remains Not Found, correctly avoiding unrelated NBI investigations. Full-case pass requires a reference for the Matibag statement.

Expected: Keep reported death, investigation and named Matibag utterances tied to this death. Reporter credit is not a source condition. Reject unrelated NBI investigations.

Observed: HTTP 200; 72.616 seconds; TRACE `d00f406c0d0a43658f9152b6ee598be2`; capture partial.
[Saved response](current-baseline/B01.json) | [TRACE snapshot](current-trace-snapshots/B01.json)

- **Verified**: Ronn Tristan Perez is demanding clear answers regarding the tragic death of his mother.
- **Verified**: Ronn Tristan Perez's mother passed away just days after reportedly undergoing four cosmetic procedures at a clinic in San Juan City.
- **Not Found**: NBI Director Melvin Matibag said his agency has already begun the investigation.

### B02: Palace conviction threshold

**Passed**. Malacanang's hands-off position on the conviction vote threshold is directly supported by retrieved ABS-CBN and Philstar passages; the earlier attribution mismatch is not reproduced.

Expected: Verify the Palace statement on the conviction threshold; normalize Malacanang typography without weakening the specific assertion.

Observed: HTTP 200; 31.515 seconds; TRACE `33f4b9f1aef84f7a8f7d5fbd453b69df`; capture partial.
[Saved response](current-baseline/B02.json) | [TRACE snapshot](current-trace-snapshots/B02.json)

- **Verified**: The Malacañang stated that the president will not intervene regarding the issue of the necessary votes for the conviction in the impeachment trial of Vice President Sara Duterte.

### B03: Palace advice on confidential operations

**Passed**. Evidence supports Palace advice to DILG and that Remulla announced the asylum denial. The latter is an attributed announcement, not proof that the disputed denial actually occurred.

Expected: Keep the agency advice and Remulla reported plan with attribution. Distinguish announcement from completed operation.

Observed: HTTP 200; 56.327 seconds; TRACE `7abc3c29077545669728d6d32032624a`; capture partial.
[Saved response](current-baseline/B03.json) | [TRACE snapshot](current-trace-snapshots/B03.json)

- **Verified**: Malacañang advised the DILG to keep its legal operations confidential
- **Verified**: Interior Secretary Jonvic Remulla announced that Austria did not accept the asylum application of former presidential spokesperson Harry Roque

### B04: ICC second detention review

**Failed**. The expert-panel detention quotation is assigned a null speaker with role judges, then every article is rejected for missing speaker, including the relevant GMA and Philstar reports. Other court quotations were successfully reviewed.

Expected: Keep second review, detention decision and court reasons, pending fitness decision, and first appearance date. Preserve reporting time and no invented verdict on technical failure.

Observed: HTTP 200; 173.702 seconds; TRACE `9533b221447042b39829a9b503bcbe5d`; capture partial.
[Saved response](current-baseline/B04.json) | [TRACE snapshot](current-trace-snapshots/B04.json)

- **Verified**: Former president Rodrigo Duterte will remain in detention in The Hague after trial judges of the International Criminal Court (ICC) found “no notable change” in circumstances that would warrant his release.
- **Verified**: The ICC Trial Chamber III released the decision on Duterte’s second detention review hours after he appeared for the first time in person before the international tribunal.
- **Verified**: The Chamber finds that the prospect of the Accused facing a trial, and (in the event of a conviction), a lengthy prison sentence, has increased. There is, therefore, a likelihood of the Accused absconding and/or obstructing or endangering the investigation or the court proceedings.
- **Verified**: Owing to the Prosecution's submission of the Witness and Evidence Lists, (thereby disclosing the identities of the witnesses and the contents of their expected testimony), this increases the Accused's ability to interfere with witnesses, either directly or through his family or supporters in the Philippines.
- **Not Found**: Although the decision on Duterte’s fitness to stand trial is still pending, the judges also ruled that the expert panel’s reports “do not contain any new information that warrants a modification of [Duterte’s] detention.”
- **Verified**: Duterte has been detained at the ICC Detention Centre in The Hague since his arrest.
- **Not Found**: Duterte was last seen by the public during his initial appearance hearing on March 14, 2025.

### B05: Arrest after shooting ex-partner new companion

**Failed**. The reviewer explicitly recognizes a different victim/motive, but credits the detached component arrested using that different shooting. The resulting Partially Verified is unsafe cross-event support.

Expected: Keep victim relationship, online-taunt motive and arrest as one incident. Do not accept a generic arrest from another shooting.

Observed: HTTP 200; 37.531 seconds; TRACE `38ec7742fb634fa4bc90096702b5c4df`; capture partial.
[Saved response](current-baseline/B05.json) | [TRACE snapshot](current-trace-snapshots/B05.json)

- **Partially Verified**: Man who shot ex's new partner after getting upset with online taunts arrested.

### B06: Prediction about senator-judges motives

**Passed**. The political prediction/opinion produces no checkable claims and no search, consistent with the expected routing.

Expected: Treat predicted bias/public mood and hoped-for justice as commentary, not a documented voting decision.

Observed: HTTP 200; 7.299 seconds; TRACE `71fab88197744f36807abf7bf86e7b43`; capture complete.
[Saved response](current-baseline/B06.json) | [TRACE snapshot](current-trace-snapshots/B06.json)

- No delivered claims. Result/error: No Checkable Claims.

### B07: Vote wisely civic appeal

**Failed**. Generic vote-wisely advocacy becomes six claims and consumes roughly four minutes. One value-laden consequence statement is Verified using vote-buying commentary. Opinion agreement is not factual verification.

Expected: Under the stated news-verification scope, generic advocacy/hypothetical hiring analogies are not concrete reported events.

Observed: HTTP 200; 243.977 seconds; TRACE `99962408f55f470ab94002cf7e7a8de9`; capture partial.
[Saved response](current-baseline/B07.json) | [TRACE snapshot](current-trace-snapshots/B07.json)

- **Not Found**: One vote can influence the quality of education your children receive.
- **Not Found**: One vote can influence the opportunities available to workers.
- **Not Found**: One vote can influence the healthcare your family depends on.
- **Not Found**: One vote can influence the laws that shape your everyday life.
- **Verified**: Sometimes, the price of a wrong vote is paid not for months but for years.
- **Not Found**: The future we complain about tomorrow is often built by the choices we make today.

### B08: Solar boy nickname

**Cannot yet judge**. The unresolved nickname produces Not Found. No formal identity should be guessed. This is consistent with the accepted limitation, but cannot establish the underlying statement's truth.

Expected: Do not resolve the nickname by guessing a formal name. Evaluative anonymous hearsay must not gain an invented speaker.

Observed: HTTP 200; 18.626 seconds; TRACE `3b76a3338add41c8b39a88f30bcece13`; capture partial.
[Saved response](current-baseline/B08.json) | [TRACE snapshot](current-trace-snapshots/B08.json)

- **Not Found**: Solar boy's projects are said to be okay.

### B09: Rhetorical mugshot questions

**Passed**. Rhetorical mugshot commentary stops without invented factual claims or unnecessary search.

Expected: Do not invent an identified individual, detention event or missing photograph from this ambiguous rhetorical input.

Observed: HTTP 200; 6.146 seconds; TRACE `e5b24beae1b24c3593b5e1998123373f`; capture complete.
[Saved response](current-baseline/B09.json) | [TRACE snapshot](current-trace-snapshots/B09.json)

- No delivered claims. Result/error: No Checkable Claims.

### B10: Loren return speculation and imprisonment

**Passed**. The factual former-Speaker jail clause is retained and supported by the matching ABS-CBN Payatas report; the speculative political return is not presented as a verified event.

Expected: Separate speculation about future travel/motives from the reported former Speaker imprisonment in QC Payatas. Preserve the uncertainty.

Observed: HTTP 200; 36.689 seconds; TRACE `b42a2dea2ddc4413a577197826e6126e`; capture partial.
[Saved response](current-baseline/B10.json) | [TRACE snapshot](current-trace-snapshots/B10.json)

- **Verified**: the former House Speaker, the President’s own cousin, ended up in a QC jail in Payatas

### B11: BIR VAT on system loss

**Passed**. The BIR VAT removal fact is directly supported by the matching ABS-CBN report; congratulatory commentary is not turned into extra claims.

Expected: Check the BIR tax action separately from congratulations and political appraisal.

Observed: HTTP 200; 35.939 seconds; TRACE `9f4e7939d77e4fe9bc567910a3437efc`; capture partial.
[Saved response](current-baseline/B11.json) | [TRACE snapshot](current-trace-snapshots/B11.json)

- **Verified**: The BIR removed the VAT on system loss charge.

### B12: Loren defense commentary

**Failed**. The mixed essay loses checkable event/background details. Even a verbatim supported environmental-causes statement becomes Partially Verified after causes is split into an unsupported one-word component. De Lima's nearly seven years is also promoted to unqualified seven years.

Expected: Keep actual interview/reporting, advocacy references, attributed defenses, twice-impeached assertion and relevant historical factual statements. Do not turn analogies or criticism into established allegations.

Observed: HTTP 200; 190.972 seconds; TRACE `98c4141140444f96872a20992d656a6f`; capture partial.
[Saved response](current-baseline/B12.json) | [TRACE snapshot](current-trace-snapshots/B12.json)

- **Verified**: Tony La Viña said he has known Loren Legarda for a long time.
- **Partially Verified**: Tony La Viña pointed to Loren Legarda’s legislative record, particularly her years of championing environmental causes.
- **Verified**: Tony La Viña cited Loren Legarda’s environmental laws, including the Clean Air Act and Renewable Energy Act, among others, in an earlier Facebook post.
- **Verified**: Tony La Viña argued that the allegations against Loren Legarda have 'no basis.'
- **Verified**: Tony La Viña claimed that Loren Legarda and her son are 'victims of political persecution.'
- **Verified**: Leila de Lima was imprisoned by the Duterte regime for seven years.

### B13: Imagined Robin questions

**Passed**. Anticipated/imagined Padilla questions are not treated as something he actually said; the run returns no checkable claims.

Expected: Retain anticipated hypothetical framing and all three questions. Do not verify that Robin actually asked them.

Observed: HTTP 200; 5.081 seconds; TRACE `8b25eb2567d44fcca7f1abd95f31d753`; capture complete.
[Saved response](current-baseline/B13.json) | [TRACE snapshot](current-trace-snapshots/B13.json)

- No delivered claims. Result/error: No Checkable Claims.

### B14: Carpio detention and quorum quote

**Passed**. The Carpio quotation is supported verbatim by the Philstar report. This is a pass for attribution, not an independent legal ruling.

Expected: Check that Carpio made the complete statement. Do not substitute a legal ruling on its underlying correctness.

Observed: HTTP 200; 25.116 seconds; TRACE `cc285879231b430a9b319ddc7a827360`; capture partial.
[Saved response](current-baseline/B14.json) | [TRACE snapshot](current-trace-snapshots/B14.json)

- **Verified**: “A senator who is a detention prisoner cannot hold public office…Necessarily, he cannot be included in determining any quorum or majority vote,” former Supreme Court senior associate justice Antonio Carpio said.

### B15: Byeon Woo-seok fan meeting

**Failed**. An anonymous handsome opinion is extracted; an old Instagram photo report supports an unspecified current update. The correct fan-meeting article is found, but the date is downgraded because final selected passages omit 2026, even though event-identity evidence includes the explicit October 10, 2026 quote.

Expected: Retain Instagram action and specific tour, date including 2026, and venue. Treat different event/year/date as mismatch; exclude aesthetic praise.

Observed: HTTP 200; 62.76 seconds; TRACE `4a34a173550444c2a29a792726e0261f`; capture partial.
[Saved response](current-baseline/B15.json) | [TRACE snapshot](current-trace-snapshots/B15.json)

- **Verified**: South Korean actor Byeon Woo-seok posted a photo update on Instagram.
- **No Search Results**: "So handsome," commented one netizen.
- **Partially Verified**: Woo-seok is scheduled to go to the Philippines on October 10, 2026 for his "The Secret Library" fan meeting tour to be held at SM Mall of Asia Arena.

### B16: NASA galaxy composite image

**Failed**. The NASA-only post proceeds to three claims and search despite the expected Philippines scope restriction. Not Found does not explain that scope limitation.

Expected: Under the user-stated Philippine scope, route to out of scope, not false/invalid; do not spend news-verification work on unrelated astronomy.

Observed: HTTP 200; 62.153 seconds; TRACE `00fdc22a6aa7421f9624450e1ae977cf`; capture partial.
[Saved response](current-baseline/B16.json) | [TRACE snapshot](current-trace-snapshots/B16.json)

- **Not Found**: NASA’s Hubble Space Telescope showcased an image of spiral galaxy NGC 4258, featuring its arms created by a central supermassive black hole.
- **Not Found**: The space agency wrote on Tuesday: “In this composite view, NASA Chandra X-ray’s data (royal blue) show superheated shockwaves created by central black hole jets, along with Hubble's optical data (red, yellow, pale blue) and NASA Webb’s infrared view of dust filaments (orange).”
- **Not Found**: The galaxy NGC 4258 is located approximately 24 million light-years from Earth in the constellation Canes Venatici.

### C01: Baste subpoena

**Passed**. The GMA report explicitly states the subpoena and September 23 appearance date, alongside the unexplained-wealth trial context. An earlier ABS-CBN tentative-summons passage is not sufficient alone, but the later explicit GMA evidence supports the assertion.

Expected: Retain subpoena, trial relation, September 23 and unexplained-wealth allegation. Valid article/passage ownership is required.

Observed: HTTP 200; 62.517 seconds; TRACE `e1c3850081db4c70a0daf497bcc29447`; capture partial.
[Saved response](current-baseline/C01.json) | [TRACE snapshot](current-trace-snapshots/C01.json)

- **Verified**: Davao City Mayor Sebastian “Baste” Duterte has been subpoenaed to testify in the impeachment trial of his sister, Vice President Sara Duterte, on Sept. 23.
- **Verified**: The Senate impeachment court is examining allegations of unexplained wealth against Sara Duterte.

### C02: Zuckerberg DICT budget

**Failed**. Philstar's extracted opening sentence matches the entire claim verbatim. The final reviewer nevertheless rejects violence and child safety while acknowledging that same passage confirms both. This is a contradictory evidence judgment, not missing retrieval.

Expected: Retain 2027 budget deferral, DICT, proposed summons and Facebook child-safety/violence rationale.

Observed: HTTP 200; 32.178 seconds; TRACE `8e4cfa57d4be406d9ea9bf37684dd5c6`; capture partial.
[Saved response](current-baseline/C02.json) | [TRACE snapshot](current-trace-snapshots/C02.json)

- **Partially Verified**: Lawmakers have deferred approval of the proposed 2027 budget of the Department of Information and Communications Technology (DICT), in a bid to summon and force Meta CEO Mark Zuckerberg to address violence and child safety concerns on Facebook.

### C03: Eala and Wintour

**Failed**. The correct ABS-CBN article and full Wintour quote are present. The reviewer rejects I think it is great because only one of two passages contains it, inventing a requirement that every passage repeat the whole quote. One valid supporting passage should not be cancelled by another passage's omission.

Expected: Cover NYFW Michael Kors seating and complete Wintour US Open utterance. Do not mix related embedded entertainment stories into the evidence.

Observed: HTTP 200; 60.738 seconds; TRACE `39eb98c29f8242ff94853bb466039221`; capture partial.
[Saved response](current-baseline/C03.json) | [TRACE snapshot](current-trace-snapshots/C03.json)

- **Verified**: Filipina tennis star Alex Eala is spotted seated in the front row beside Vogue’s Anna Wintour at the Michael Kors fashion show during New York Fashion Week.
- **Partially Verified**: Anna Wintour said in an interview at the US Open: “We had the young Filipino star, you know, you could see even in such a young star how interested she is in fashion. How she wants to learn about it and follow it and I think it’s great.”

### C04: DepEd longer OJT

**Failed**. The known GMA 640-hour article is absent from recorded search/extraction, but direct extraction returns 906 words including the figures. IRIS credits only Angara's job title toward the proposal, yielding misleading partial support; older employability coverage substitutes for the current statement. The final He added claim also loses explicit speaker resolution.

Expected: Cover employer feedback, proposed 80-160 to 640 hour increase and same-employer hiring prospects. Preserve proposal rather than completed implementation.

Observed: HTTP 200; 77.406 seconds; TRACE `587bb27f53f3454d8a1016a72c514b24`; capture partial.
[Saved response](current-baseline/C04.json) | [TRACE snapshot](current-trace-snapshots/C04.json)

- **Verified**: The Department of Education (DepEd) says there is still work to be done, citing feedback from employers who find some senior high school graduates not yet sufficiently prepared for the workplace.
- **Partially Verified**: Education Secretary Sonny Angara said DepEd is looking to increase the amount of on-the-job training (OJT) for senior high school students to 640 hours, from the current 80 to 160 hours.
- **Not Found**: He added that longer OJT could also improve graduates’ chances of being hired by the same employers who trained them.

### C05: Rene Baterbonia UST

**Passed**. The matching ABS-CBN sports article is retrieved and directly supports the lack of prior UST connection and the reported family support. The earlier missing-source symptom is not reproduced.

Expected: Preserve no prior UST connection and family comfort with UST, without confusing Rene with his father.

Observed: HTTP 200; 44.618 seconds; TRACE `8fc91c9d45a240329eb182a787cec003`; capture partial.
[Saved response](current-baseline/C05.json) | [TRACE snapshot](current-trace-snapshots/C05.json)

- **Verified**: Rene Baterbonia was not, in any way, connected to University of Santo Tomas before his passing.
- **Verified**: Rene Baterbonia's bereaved family found solace with the España-based team as they cope with their loss.

### C06: Padilla plans and political warnings

**Failed**. The explicitly named Sen. Robinhood Padilla becomes a null speaker in attribution metadata, causing automatic speaker rejection. The final Padilla quotation also has politically_sensitive false despite the explicit official-speaker context. Exact-event reference evidence is still missing, so a positive verdict cannot yet be prescribed.

Expected: Retain no-future-election announcement, child/family rationale, endorsements and attributed quotations. Political warnings are per claim, including explicitly identified official speaker.

Observed: HTTP 200; 58.641 seconds; TRACE `911363999e7f46f0b3b510cd934e6143`; capture partial.
[Saved response](current-baseline/C06.json) | [TRACE snapshot](current-trace-snapshots/C06.json)

- **Not Found**: Sen. Robinhood Padilla announced on Friday, Sept. 18, that he has no plans of running in future elections, saying he wants to focus on raising his young children and living a quiet Islamic life.
- **Not Found**: Padilla endorsed several allies to run as Vice President Sara Duterte's running mate instead, including Alan Peter Cayetano, Imee Marcos, Bong Go, Ronald 'Bato' dela Rosa, Rodante Marcoleta, and Salvador Panelo.
- **Not Found**: Padilla said: "Halata naman po na hindi ako nababagay sa mundong ito," concluding with: "Revolutionaries do not sit on thrones; they tear them down."

### C07: Moira September 17 media appearance

**Failed**. The September 17 media appearance remains unconfirmed, but the follow-on healing statement receives partial support from a 2022 breakup interview. The post's event context is lost across claims. The known September 14 Spotify article is only a related reference, not proof of the September 17 appearance.

Expected: Keep September 17 QC appearance, October 4 concert, and healing remarks connected to that appearance. Older interviews are not proof of that event; supplied concert article gives only partial reference coverage.

Observed: HTTP 200; 53.897 seconds; TRACE `d3000e9a9cda4ea8b6f7200e3d369b1c`; capture partial.
[Saved response](current-baseline/C07.json) | [TRACE snapshot](current-trace-snapshots/C07.json)

- **Not Found**: Moira Dela Torre faced the media earlier today, Sept. 17, in Quezon City, to talk about her upcoming concert “Where It All Started,” set for Oct. 4.
- **Partially Verified**: Dela Torre opened up about her healing journey after a series of heartbreaks and controversies.

### C08: VERA Poquiz false attribution

**Failed**. This is fake is discarded as unclear instead of being linked to the preceding alleged quotation. The known VERA fact-check is absent from recorded retrieval, while direct extraction returns 530 words. Preserve the allegation and its denial without assuming either is true before review.

Expected: Distinguish circulating allegation from assertion that it is fake. The allegation must not become an endorsed fact. Retrieve actual fact-check article, never a search page.

Observed: HTTP 200; 29.127 seconds; TRACE `d8c6989b115443ae850f23213e23c55d`; capture partial.
[Saved response](current-baseline/C08.json) | [TRACE snapshot](current-trace-snapshots/C08.json)

- **Not Found**: At least two Facebook posts are claiming that retired Philippine Air Force Maj. Gen. Romeo Poquiz made a statement against President Ferdinand Marcos Jr. and his wife, First Lady Liza Araneta-Marcos.

## Beginner-Friendly Terms

- **Retrieval:** searching for candidate articles. Finding the same topic is not proof.
- **Extraction:** reading article text, or separating a post into claims. These are different steps.
- **Attribution:** checking who said something, where and when. Confirming a quote does not prove its underlying opinion.
- **Component:** a smaller factual part of a claim. It must keep enough context to identify the same event.
- **Entailment/evidence matching:** whether a passage actually supports that particular assertion.
- **False positive:** accepting evidence that does not justify a positive verdict.
- **False negative:** rejecting available evidence that does support the assertion.
- **Reference control:** a test where we supply an article on purpose to isolate later stages.
- **Rate limit:** a service refusing more work temporarily. It is a technical failure, not Not Found.
- **Held-out:** new cases not used while designing or fixing the system.

## Remaining User Decisions

No new broad policy decision is needed to fix the confirmed defects above. Keep the already approved nickname limitation, publisher sections and strict evidence requirements. Exact-event evidence is still needed for unresolved Samaniego and Matibag attributions and any uncaptured blind tests not represented by the saved inputs. Do not guess their labels.
