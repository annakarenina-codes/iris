# IRIS Ten-Case TRACE Evaluation

Prepared 2026-09-11. Retrospective pilot evaluation, not a certified accuracy score.

## Scope and labeling status
Observed data come from the local TRACE database and the ten-case audit_logs.docx mapping. Expected labels below are analyst proposals prepared AFTER observing failures. They need independent reviewer adjudication; this is a development set, not a held-out benchmark. No live verification or source re-fetch was performed. Backend code and databases were not modified.
There are 11 recorded runs for 10 cases. Case 8 uses its first chronological run; its repeat is reported separately, not substituted for a better result. HTTP completion is not semantic correctness. Partial capture limits per-stage conclusions. Cached outputs are explicitly labeled.

## Batch results
| Case | TRACE ID | Recorded time (Philippines) | HTTP | Status | Capture | Final claim count | Seconds |
|---|---|---|---|---|---|---:|---:|
| 1 | 1853a5aa61fe4badb1de3fbf18c581d6 | 2026-09-09T22:30:31+08:00 | 200 | completed | partial | 1 | 27.68 |
| 2 | fa41f52087f34af4a04dcff78f387a36 | 2026-09-09T22:39:11+08:00 | 200 | completed | partial | 6 | 46.29 |
| 3 | f73f6e000e924afe9d21ba4b47e2aa3b | 2026-09-09T22:57:59+08:00 | 503 | error | partial | 0 | 48.92 |
| 4 | 214b112b076e42c6a7645335108d3c0c | 2026-09-09T23:07:09+08:00 | 200 | completed | complete | 0 | 2.88 |
| 5 | ca9ac265af86450fa09a84ffec43755e | 2026-09-09T23:21:21+08:00 | 200 | completed | complete | 2 | 10.01 |
| 6 | 48f717ee56b3485a837bd63cb054d10d | 2026-09-09T23:36:08+08:00 | 200 | completed | complete | 0 | 6.39 |
| 7 | 9fe83e8c73cc45bd8c39589f619b7f38 | 2026-09-09T23:42:01+08:00 | 503 | error | partial | 0 | 19.45 |
| 8 | 1a0a6ff587e14e95a2a421032d4845ff | 2026-09-09T23:47:00+08:00 | 200 | completed | partial | 6 | 58.03 |
| 9 | 75e31974eb424e2c98736c038ea4e051 | 2026-09-09T23:57:40+08:00 | 200 | completed | complete | 0 | 3.60 |
| 10 | c34abc3719374011959edd76752ad559 | 2026-09-10T00:04:14+08:00 | 200 | completed | complete | 0 | 4.04 |

Operational completion: **8/10 (80%)**. Complete trace capture: **5/10 (50%)**.
These are operational measurements, NOT verdict accuracy. HTTP200 No Checkable Claims counts as operational completion but may fail eligibility evaluation.

| Accuracy metric | Result | Why |
|---|---|---|
| Extraction precision / recall / F1 | Pending adjudication | Match original spans to proposed labels; cached and failed runs need separate treatment. |
| Routing accuracy | Pending adjudication | Label all eligible and intentionally excluded segments; do not use model confidence as ground truth. |
| Retrieval success | Not yet measurable | Requires independently inspected known admissible sources per claim. |
| Article extraction success | Not yet measurable | Extraction counts do not establish that required passages survived. |
| Evidence precision | Not yet measurable | Recorded quotations/URLs are system outputs, not independently validated reference evidence. |
| Verdict agreement | Not yet measurable | Final reference verdicts remain unadjudicated. |

## Scoring rules
One-to-one semantic matching preserves speaker, recipient, action, negation, amount and date. Duplicate outputs are extra predictions. Optional granularity splits must be agreed before scoring; Case 7 components are not automatically four extraction targets. A failed request stays in completion statistics; downstream metrics are not reached rather than zero-valued successful judgments.
Precision = correct matched outputs / all outputs. Recall = matched expected claims / expected claims. F1 = 2PR/(P+R). Report numerator/denominator and N/A for empty denominators. Evidence precision uses claim-source pairs. Never infer falsehood from Not Found. Technical failure is not a factual verdict.

## Configuration limits
Per-run snapshots are preserved in observed_trace_records.json. The recorded commit identifies a checkout, not necessarily all uncommitted changes. TRACE snapshots say first use in process: restart after edits. OPENAI_MODEL=null is an unset environment setting, not proof no model ran. Cache policy was not controlled for these historical runs; do not claim a frozen fresh-run benchmark.

## Case 1

TRACE: `1853a5aa61fe4badb1de3fbf18c581d6`

### Original input
The Philippines now owns China according to DAILY TRIBUNE’s own imaginary 9-dash line.

### Expected extraction and routing (proposed)
| Label ID | Expected route | Assertion / required context |
|---|---|---|
| P01-C01 | Review ambiguity | Determine whether the imaginary nine-dash-line ownership assertion is satire or a literal assertion; do not infer intent from absurdity alone. |

Expected verdict: **pending source adjudication**, not preset to Verified. Supporting evidence must establish the particular assertion; partial coverage must identify unsupported components. Source unavailable/outside policy is distinct from contradiction.

### Observed behavior
Result: Not Found. Message: The evidence discusses protests and legal rulings but does not support the claim that the Philippines owns China.
Profiler route: proceed_to_verification; extraction status: ok; language: english.
| Output ID | Extracted claim | Verdict | Cache hit | Evidence links |
|---|---|---|---|---:|
| 1 | The Philippines now owns China according to DAILY TRIBUNE’s own imaginary 9-dash line. | Not Found | False | 0 |

### Recorded stages
| Stage | Execution | Duration ms | Domain outcome |
|---|---|---:|---|
| request.parse_validate | completed | 0.13730005593970418 | Not recorded |
| text.language | completed | 73.5947999637574 | Not recorded |
| text.translation | completed | 0.554199970792979 | Not recorded |
| text.profile_local | completed | 14.93620005203411 | ok |
| text.profile | completed | 15.56720002554357 | ok |
| text.opinion | completed | 0.49000000581145287 | Not recorded |
| text.political | completed | 5.06709999172017 | Not recorded |
| claims.extract | completed | 5914.033000008203 | ok |
| claims.attribution | completed | 0.0029999646358191967 | Not recorded |
| claims.quote_mark | completed | 0.005199981387704611 | Not recorded |
| event.retrieve | completed | 0.005700043402612209 | not_needed |
| claim.cache_read | completed | 4.127499996684492 | Not recorded |
| text.political | completed | 0.3220000071451068 | Not recorded |
| claim.political | completed | 0.5088000325486064 | Not recorded |
| retrieval.source_search | completed | 1578.5234000068158 | ok |
| retrieval.source_search | completed | 1584.4994999933988 | ok |
| retrieval.source_search | completed | 1589.8400000296533 | ok |
| retrieval.source_search | completed | 1608.03709999891 | ok |
| retrieval.source_search | completed | 1611.460399988573 | ok |
| retrieval.source_search | completed | 1611.4835999906063 | ok |
| retrieval.source_search | completed | 1617.8928000153974 | ok |
| retrieval.source_search | completed | 1636.018300021533 | ok |
| retrieval.queries | completed | 1649.7550999629311 | Not recorded |
| retrieval.article_extract | completed | 1409.1968000284396 | extracted |
| retrieval.article_extract | completed | 1829.7043000347912 | extracted |
| retrieval.article_extract | completed | 1964.636499993503 | extracted |
| retrieval.article_extract | completed | 2009.7229999955744 | extracted |
| retrieval.article_extract | completed | 2084.7841000068 | extracted |
| retrieval.article_extract | completed | 2264.9389000143856 | extracted |
| retrieval.article_extract | completed | 897.4494999856688 | extracted |
| retrieval.article_extract | completed | 697.6405000314116 | error |
| retrieval.article_extract | completed | 655.0394000369124 | error |
| retrieval.article_extract | completed | 823.0921000358649 | error |
| retrieval.article_extract | completed | 2924.9262000084855 | extracted |
| retrieval.article_extract | completed | 668.9744999748655 | error |
| retrieval.article_extract | completed | 3109.662200033199 | extracted |
| retrieval.article_extract | completed | 556.5575000364333 | error |
| retrieval.article_extract | completed | 1206.840300001204 | error |
| retrieval.article_extract | completed | 4277.254100015853 | extracted |
| retrieval.pool | completed | 7779.00189999491 | Not recorded |
| claim.retrieve | completed | 7803.079900040757 | Not recorded |
| retrieval.status | completed | 0.013000040780752897 | ok |
| model.semantic_load | completed | 9667.080299986992 | Not recorded |
| model.semantic_load | completed | 0.007599999662488699 | Not recorded |
| model.semantic_load | completed | 0.007800001185387373 | Not recorded |
| model.semantic_load | completed | 0.021000043489038944 | Not recorded |
| model.semantic_load | completed | 0.01090002479031682 | Not recorded |
| model.semantic_load | completed | 0.014299992471933365 | Not recorded |
| model.semantic_load | completed | 0.006699992809444666 | Not recorded |
| model.semantic_load | completed | 0.00589998671784997 | Not recorded |
| model.semantic_load | completed | 0.006399990525096655 | Not recorded |
| model.semantic_load | completed | 0.006799993570894003 | Not recorded |
| model.semantic_load | completed | 0.008400005754083395 | Not recorded |
| claim.semantic | completed | 11144.595599966124 | Not recorded |
| claim.fallback_ai | completed | 2450.3635999863036 | ok |
| claim.fallback | completed | 2467.2633000300266 | Not recorded |
| claim.evidence_gate | completed | 0.006699992809444666 | Not recorded |
| claim.attribution_gate | completed | 0.006799993570894003 | Not recorded |
| claim.attribution_gate | completed | 0.01379998866468668 | Not recorded |
| claim.attribution_gate | completed | 0.004399975296109915 | Not recorded |
| claim.attribution_gate | completed | 0.002900022082030773 | Not recorded |
| claim.attribution_gate | completed | 0.0031999661587178707 | Not recorded |
| claim.attribution_gate | completed | 0.009100011084228754 | Not recorded |
| claim.attribution_gate | completed | 0.007700000423938036 | Not recorded |
| claim.attribution_gate | completed | 0.006799993570894003 | Not recorded |
| claim.attribution_gate | completed | 0.0031999661587178707 | Not recorded |
| claim.attribution_gate | completed | 0.0026999623514711857 | Not recorded |
| claim.cache_write | completed | 9.292799979448318 | Not recorded |
| claim.process | completed | 21551.63329996867 | Not recorded |
| request.assemble | completed | 0.007800001185387373 | Not recorded |
| text.process | completed | 27572.25169998128 | Not recorded |

### Evidence review worksheet
System-recorded URLs and quotations below are candidates for human inspection, NOT gold references. Missing fields must not be invented.
| Claim | Candidate URL | Recorded passage | Human relationship / policy / access-date review |
|---|---|---|---|
| All remaining expected labels | Pending reference URL | Pending inspected verbatim passage | Pending |

### Diagnosis and next regression
Ambiguity review required before assigning a single gold route. Related background is not automatically supporting or contradicting evidence.
Reviewer sign-off: pending. Matched expected IDs: pending. Correct / extra / missed outputs: pending. Final reference verdict and disagreement resolution: pending.
Retest the exact input after a scoped change; preserve the new TRACE ID, configuration and cache-hit flags. Require appropriate routing, preserved context, auditable evidence and no technical-failure verdict.

### Recorded excluded segments
| Text | Type | Reason |
|---|---|---|
| imaginary | opinion | Not recorded |

## Case 2

TRACE: `fa41f52087f34af4a04dcff78f387a36`

### Original input
'NAKARATING NA PO BA KAYO NG BARMM?' Senator-judge Robinhood Padilla asked former state auditor Roderick Wamil if he had ever visited the Bangsamoro Autonomous Region in Muslim Mindanao (BARMM) and whether he was aware of the country's ongoing terrorism threats. During his interjection, Padilla raised preliminary questions about the Audit Observation Memorandum, trying to establish ties to the confidential funds used by Vice President Sara Duterte for surveillance on potential New People's Army (NPA) recruitment. "Pero kayo po ang humahawak ng imbestigasyon patungkol sa confidential funds, tama po ba?" Padilla asked Wamil. "Hindi po siya imbestigasyon. Evaluation po," the witness answered. "Kayo po ba ay naniniwala na ang mga confidential agent ay dapat magpakilala? Sabihin ang kanilang totoong pangalan," the senator furthered. "Wala pong provisions as to that po sa joint circular," Wamil said. Padilla then asked Wamil to define "confidential," to which the auditor replied, "classified."

### Expected extraction and routing (proposed)
| Label ID | Expected route | Assertion / required context |
|---|---|---|
| P02-C01 | Verify attribution | Padilla asked Wamil about visiting BARMM and terrorism awareness; preserve both components. |
| P02-C02 | Verify attribution | Padilla raised the Audit Observation Memorandum and linked confidential funds to alleged NPA recruitment surveillance. |
| P02-C03 | Verify attribution | Padilla asked whether Wamil handled an investigation concerning confidential funds. |
| P02-C04 | Verify attribution | Wamil answered that it was an evaluation, not an investigation; retain the denial and the question context. |
| P02-C05 | Verify attribution | Padilla asked whether confidential agents must identify themselves and state their real names. |
| P02-C06 | Verify attribution | Wamil said the joint circular had no such provisions; resolve what such provisions refers to. |
| P02-C07 | Verify attribution | Padilla asked for the definition of confidential and Wamil answered classified. |

Expected verdict: **pending source adjudication**, not preset to Verified. Supporting evidence must establish the particular assertion; partial coverage must identify unsupported components. Source unavailable/outside policy is distinct from contradiction.

### Observed behavior
Result: Multiple Claims Checked. Message: IRIS checked 6 extracted claims individually.
Profiler route: verify_factual_claims_only; extraction status: ok; language: tagalog.
| Output ID | Extracted claim | Verdict | Cache hit | Evidence links |
|---|---|---|---|---:|
| 1 | Senator-judge Robinhood Padilla asked former state auditor Roderick Wamil if he had ever visited the Bangsamoro Autonomous Region in Muslim Mindanao (BARMM) and whether he was aware of the country's ongoing terrorism threats. | Verified | True | 2 |
| 2 | During his interjection, Padilla raised preliminary questions about the Audit Observation Memorandum, trying to establish ties to the confidential funds used by Vice President Sara Duterte for surveillance on potential New People's Army (NPA) recruitment. | Partially Verified | True | 3 |
| 3 | Evaluation po," the witness answered. | Not Found | False | 0 |
| 4 | Sabihin ang kanilang totoong pangalan," the senator furthered. | Not Found | False | 0 |
| 5 | Wala pong provisions as to that po sa joint circular," Wamil said. | Not Found | False | 0 |
| 6 | Padilla then asked Wamil to define "confidential," to which the auditor replied, "classified. | Not Found | True | 0 |

### Recorded stages
| Stage | Execution | Duration ms | Domain outcome |
|---|---|---:|---|
| request.parse_validate | completed | 0.16360002337023616 | Not recorded |
| text.language | completed | 84.50150000862777 | Not recorded |
| text.translation | completed | 508.7510000448674 | Not recorded |
| text.profile_local | completed | 23.241300019435585 | ok |
| text.profile_ai | completed | 5259.899500000756 | ok |
| text.profile_merge | completed | 0.06500002928078175 | ok |
| text.profile | completed | 5291.021700017154 | ok |
| text.opinion | completed | 0.5480999825522304 | Not recorded |
| text.political | completed | 5.765599955338985 | Not recorded |
| claims.extract | completed | 9604.279099963605 | ok |
| claims.attribution | completed | 0.0030999653972685337 | Not recorded |
| claims.attribution | completed | 0.00200001522898674 | Not recorded |
| claims.attribution | completed | 0.0015999539755284786 | Not recorded |
| claims.attribution | completed | 0.002100015990436077 | Not recorded |
| claims.attribution | completed | 0.001800013706088066 | Not recorded |
| claims.attribution | completed | 0.0015999539755284786 | Not recorded |
| claims.quote_mark | completed | 0.12849998893216252 | Not recorded |
| event.query | completed | 0.19300001440569758 | Not recorded |
| retrieval.source_search | completed | 1541.7407999630086 | ok |
| retrieval.source_search | completed | 1559.3568999902345 | ok |
| retrieval.source_search | completed | 1601.6894000349566 | ok |
| retrieval.source_search | completed | 1608.652000024449 | ok |
| retrieval.source_search | completed | 1622.025599994231 | ok |
| retrieval.source_search | completed | 1646.6107000014745 | ok |
| retrieval.source_search | completed | 1668.8262000097893 | ok |
| retrieval.source_search | completed | 1677.5010999990627 | ok |
| retrieval.queries | completed | 1693.9229000126943 | Not recorded |
| retrieval.article_extract | completed | 1035.9979000058956 | extracted |
| retrieval.article_extract | completed | 1086.605500022415 | extracted |
| retrieval.article_extract | completed | 1586.2700000288896 | extracted |
| retrieval.article_extract | completed | 1770.9437999874353 | extracted |
| retrieval.article_extract | completed | 1894.734600035008 | extracted |
| retrieval.article_extract | completed | 1938.23260004865 | extracted |
| retrieval.article_extract | completed | 568.6531999963336 | error |
| retrieval.article_extract | completed | 588.539500022307 | error |
| retrieval.article_extract | completed | 2487.3132000211626 | extracted |
| retrieval.article_extract | completed | 673.7003999878652 | error |
| retrieval.article_extract | completed | 659.5443999976851 | error |
| retrieval.article_extract | completed | 652.1159000112675 | error |
| retrieval.article_extract | completed | 602.9699000064284 | error |
| retrieval.article_extract | completed | 4007.77000002563 | extracted |
| retrieval.article_extract | completed | 3284.13810004713 | extracted |
| retrieval.article_extract | completed | 6819.814599992242 | extracted |
| retrieval.pool | completed | 9575.429300020915 | Not recorded |
| event.retrieve | completed | 9598.414700012654 | ok |
| claim.paraphrase_ai | completed | 2121.3059999863617 | ok |
| claim.paraphrase | completed | 2121.5266999788582 | ok |
| claim.cache_read | completed | 2.986099978443235 | Not recorded |
| claim.process | completed | 2127.418299962301 | cache_hit |
| claim.paraphrase_ai | completed | 2680.9008000418544 | ok |
| claim.paraphrase | completed | 2681.2495999620296 | ok |
| claim.cache_read | completed | 4.188899998553097 | Not recorded |
| claim.process | completed | 2691.056200012099 | cache_hit |
| claim.paraphrase_ai | completed | 1940.3319000266492 | ok |
| claim.paraphrase | completed | 1940.5016000382602 | ok |
| claim.cache_read | completed | 1.9060000195167959 | Not recorded |
| text.political | completed | 0.2686000079847872 | Not recorded |
| claim.political | completed | 0.5379000212997198 | Not recorded |
| claim.retrieve | completed | 0.02359994687139988 | Not recorded |
| retrieval.status | completed | 0.013299984857439995 | ok |
| model.semantic_load | completed | 0.010499963536858559 | Not recorded |
| model.semantic_load | completed | 0.006399990525096655 | Not recorded |
| model.semantic_load | completed | 0.006299989763647318 | Not recorded |
| model.semantic_load | completed | 0.007099995855242014 | Not recorded |
| model.semantic_load | completed | 0.005599984433501959 | Not recorded |
| model.semantic_load | completed | 0.006499991286545992 | Not recorded |
| model.semantic_load | completed | 0.006699992809444666 | Not recorded |
| model.semantic_load | completed | 0.006299989763647318 | Not recorded |
| model.semantic_load | completed | 0.006699992809444666 | Not recorded |
| model.semantic_load | completed | 0.006799993570894003 | Not recorded |
| model.semantic_load | completed | 0.007599999662488699 | Not recorded |
| claim.semantic | completed | 739.0639999648556 | Not recorded |
| claim.fallback_ai | completed | 2592.8775999927893 | ok |
| claim.fallback | completed | 2613.1793999811634 | Not recorded |
| claim.evidence_gate | completed | 0.005799985956400633 | Not recorded |
| claim.attribution_gate | completed | 0.00689999433234334 | Not recorded |
| claim.attribution_gate | completed | 0.00589998671784997 | Not recorded |
| claim.attribution_gate | completed | 0.006699992809444666 | Not recorded |
| claim.attribution_gate | completed | 0.004999979864805937 | Not recorded |
| claim.attribution_gate | completed | 0.003400025889277458 | Not recorded |
| claim.attribution_gate | completed | 0.0036999699659645557 | Not recorded |
| claim.attribution_gate | completed | 0.002500019036233425 | Not recorded |
| claim.attribution_gate | completed | 0.002800021320581436 | Not recorded |
| claim.attribution_gate | completed | 0.0036999699659645557 | Not recorded |
| claim.attribution_gate | completed | 0.0034999684430658817 | Not recorded |
| claim.cache_write | completed | 7.168200041633099 | Not recorded |
| claim.process | completed | 5444.795900024474 | Not recorded |
| claim.paraphrase_ai | completed | 1378.6046000313945 | ok |
| claim.paraphrase | completed | 1378.7851000088267 | ok |
| claim.cache_read | completed | 3.1780999852344394 | Not recorded |
| text.political | completed | 0.2761000068858266 | Not recorded |
| claim.political | completed | 0.44789997627958655 | Not recorded |
| claim.retrieve | completed | 0.019899976905435324 | Not recorded |
| retrieval.status | completed | 0.020300038158893585 | ok |
| model.semantic_load | completed | 0.008100003469735384 | Not recorded |
| model.semantic_load | completed | 0.006799993570894003 | Not recorded |
| model.semantic_load | completed | 0.006699992809444666 | Not recorded |
| model.semantic_load | completed | 0.007199996616691351 | Not recorded |
| model.semantic_load | completed | 0.006699992809444666 | Not recorded |
| model.semantic_load | completed | 0.007299997378140688 | Not recorded |
| model.semantic_load | completed | 0.00689999433234334 | Not recorded |
| model.semantic_load | completed | 0.005999987479299307 | Not recorded |
| model.semantic_load | completed | 0.006599992047995329 | Not recorded |
| model.semantic_load | completed | 0.006999995093792677 | Not recorded |
| model.semantic_load | completed | 0.007700000423938036 | Not recorded |
| claim.semantic | completed | 712.5263000489213 | Not recorded |
| claim.fallback_ai | completed | 1817.0606999774463 | ok |
| claim.fallback | completed | 1837.5130000058562 | Not recorded |
| claim.evidence_gate | completed | 0.005499983672052622 | Not recorded |
| claim.attribution_gate | completed | 0.00589998671784997 | Not recorded |
| claim.attribution_gate | completed | 0.008500006515532732 | Not recorded |
| claim.attribution_gate | completed | 0.002700020559132099 | Not recorded |
| claim.attribution_gate | completed | 0.002100015990436077 | Not recorded |
| claim.attribution_gate | completed | 0.00200001522898674 | Not recorded |
| claim.attribution_gate | completed | 0.002100015990436077 | Not recorded |
| claim.attribution_gate | completed | 0.003300025127828121 | Not recorded |
| claim.attribution_gate | completed | 0.005900044925510883 | Not recorded |
| claim.attribution_gate | completed | 0.00890000956133008 | Not recorded |
| claim.attribution_gate | completed | 0.004100031219422817 | Not recorded |
| claim.cache_write | completed | 7.886699982918799 | Not recorded |
| claim.process | completed | 4079.292699985672 | Not recorded |
| claim.paraphrase_ai | completed | 1139.3891000188887 | ok |
| claim.paraphrase | completed | 1139.56539996434 | ok |
| claim.cache_read | completed | 2.713399997446686 | Not recorded |
| text.political | completed | 0.28199999360367656 | Not recorded |
| claim.political | completed | 0.4792000399902463 | Not recorded |
| claim.retrieve | completed | 0.028999987989664078 | Not recorded |
| retrieval.status | completed | 0.01360004534944892 | ok |
| model.semantic_load | completed | 0.008000002708286047 | Not recorded |
| model.semantic_load | completed | 0.004900037311017513 | Not recorded |
| model.semantic_load | completed | 0.006399990525096655 | Not recorded |
| model.semantic_load | completed | 0.005999987479299307 | Not recorded |
| model.semantic_load | completed | 0.007599999662488699 | Not recorded |
| model.semantic_load | completed | 0.006400048732757568 | Not recorded |
| model.semantic_load | completed | 0.007800001185387373 | Not recorded |
| model.semantic_load | completed | 0.01209997572004795 | Not recorded |
| model.semantic_load | completed | 0.007099995855242014 | Not recorded |
| model.semantic_load | completed | 0.01160003012046218 | Not recorded |
| model.semantic_load | completed | 0.010000017937272787 | Not recorded |
| claim.semantic | completed | 1048.0693000135943 | Not recorded |
| claim.fallback_ai | completed | 1902.222000004258 | ok |
| claim.fallback | completed | 1925.5920999567024 | Not recorded |
| claim.evidence_gate | completed | 0.004800036549568176 | Not recorded |
| claim.attribution_gate | completed | 0.006799993570894003 | Not recorded |
| claim.attribution_gate | completed | 0.005999987479299307 | Not recorded |
| claim.attribution_gate | completed | 0.004500034265220165 | Not recorded |
| claim.attribution_gate | completed | 0.007099995855242014 | Not recorded |
| claim.attribution_gate | completed | 0.00790000194683671 | Not recorded |
| claim.attribution_gate | completed | 0.009199953638017178 | Not recorded |
| claim.attribution_gate | completed | 0.006099988240748644 | Not recorded |
| claim.attribution_gate | completed | 0.00790000194683671 | Not recorded |
| claim.attribution_gate | completed | 0.006299989763647318 | Not recorded |
| claim.attribution_gate | completed | 0.004099973011761904 | Not recorded |
| claim.cache_write | completed | 7.35169998370111 | Not recorded |
| claim.process | completed | 4278.3621000126 | Not recorded |
| claim.paraphrase_ai | completed | 2348.014899995178 | ok |
| claim.paraphrase | completed | 2348.21299999021 | ok |
| claim.cache_read | completed | 3.520799975376576 | Not recorded |
| claim.process | completed | 2354.934900009539 | cache_hit |
| request.assemble | completed | 0.008400005754083395 | Not recorded |
| text.process | completed | 46268.05820001755 | Not recorded |

### Evidence review worksheet
System-recorded URLs and quotations below are candidates for human inspection, NOT gold references. Missing fields must not be invented.
| Claim | Candidate URL | Recorded passage | Human relationship / policy / access-date review |
|---|---|---|---|
| 1 | https://www.abs-cbn.com/news/nation/2026/8/5/padilla-tests-auditor-on-knowledge-of-terrorism-security-threats-1501 | No component passage recorded | Pending independent inspection |
| 1 | https://newsinfo.inquirer.net/2277977/ovp-secret-funds-may-have-helped-stop-rebel-attacks-padilla | No component passage recorded | Pending independent inspection |
| 2 | https://www.abs-cbn.com/news/nation/2026/8/5/padilla-tests-auditor-on-knowledge-of-terrorism-security-threats-1501 | No component passage recorded | Pending independent inspection |
| 2 | https://newsinfo.inquirer.net/2277977/ovp-secret-funds-may-have-helped-stop-rebel-attacks-padilla | No component passage recorded | Pending independent inspection |
| 2 | https://www.gmanetwork.com/news/topstories/nation/997341/sara-duterte-camp-sought-exemption-from-confi-fund-audit-rules-coa-witness/story/ | No component passage recorded | Pending independent inspection |
| All remaining expected labels | Pending reference URL | Pending inspected verbatim passage | Pending |

### Diagnosis and next regression
Audit flags truncated quotations and lost exchange context. A fragment cannot receive full extraction credit merely because a few original words remain.
Reviewer sign-off: pending. Matched expected IDs: pending. Correct / extra / missed outputs: pending. Final reference verdict and disagreement resolution: pending.
Retest the exact input after a scoped change; preserve the new TRACE ID, configuration and cache-hit flags. Require appropriate routing, preserved context, auditable evidence and no technical-failure verdict.

### Recorded excluded segments
| Text | Type | Reason |
|---|---|---|
| 'NAKARATING NA PO BA KAYO NG BARMM?' | unclear | ['low_classifier_confidence'] |
| "Pero kayo po ang humahawak ng imbestigasyon patungkol sa confidential funds, tama po ba?" Padilla asked Wamil. | unclear | [] |
| "Hindi po siya imbestigasyon. | unclear | ['low_classifier_confidence'] |
| "Kayo po ba ay naniniwala na ang mga confidential agent ay dapat magpakilala? | unclear | ['low_classifier_confidence'] |

## Case 3

TRACE: `f73f6e000e924afe9d21ba4b47e2aa3b`

### Original input
His work helped defend the Philippines. American marine biologist Dr. Kent Carpenter, whose scientific testimony supported the Philippines in its landmark 2016 South China Sea arbitration case against China, was shot and killed during a home invasion in Negros Oriental province in the Central Visayas region of the Philippines. Police said three unidentified men forcibly entered Carpenter's home in Barangay Ajong, Sibulan, on the night of July 12. One of the intruders allegedly shot the 73-year-old scientist in the head, killing him. His 34-year-old companion was also injured. The suspects remain at large, and investigators are reviewing CCTV footage, interviewing witnesses, and pursuing leads. Police Brigadier General Romano Cardiño condemned the killing as a "senseless act of violence" and vowed to bring those responsible to justice. Carpenter was widely respected in the scientific community for his decades of work in the Philippines. He first began studying the country's marine ecosystems in 1975 and became one of the world's leading experts on Philippine marine biodiversity. Beyond his scientific achievements, Carpenter also played a significant role in one of the Philippines' biggest international legal victories. During the South China Sea arbitration initiated by the Philippines in 2013, he submitted expert written evidence documenting the environmental damage caused by China's island reclamation and destructive fishing practices in the West Philippine Sea. He also delivered oral testimony during the 2015 merits hearing. The tribunal's 2016 ruling overwhelmingly favored the Philippines and found no legal basis for China's sweeping "nine-dash line" claims. Carpenter also conducted extensive research in the Verde Island Passage, often called the "center of the center" of global marine shore fish biodiversity, and was a strong advocate for having the area recognized as a UNESCO World Heritage Site. His death has prompted tributes from Silliman University, the University of the Philippines Marine Science Institute, conservation groups, and fellow scientists. Many remembered him not only as a world-class researcher, but also as a generous mentor who spent five decades helping Filipinos better understand and protect their country's extraordinary marine ecosystems. His life reminds us that science can shape history just as much as politics or diplomacy—and that the people behind those contributions are often remembered long after the headlines fade.

### Expected extraction and routing (proposed)
| Label ID | Expected route | Assertion / required context |
|---|---|---|
| P03-C01 | Verify factual assertion | Carpenter supplied written evidence and oral testimony supporting the Philippine arbitration case; preserve 2013 initiation, 2015 hearing and 2016 ruling as different dates. |
| P03-C02 | Verify factual assertion | Carpenter was killed in a home invasion in Ajong, Sibulan, Negros Oriental on July 12; retain alleged perpetrator details as allegations. |
| P03-C03 | Verify factual assertion | His 34-year-old companion was injured. |
| P03-C04 | Verify factual assertion | The suspects and investigation had the reported status at the time of publication. |
| P03-C05 | Verify factual assertion | Carpenter began studying Philippine marine ecosystems in 1975. |
| P03-C06 | Verify factual assertion | The 2016 tribunal ruling rejected the nine-dash-line legal claim. |
| P03-C07 | Verify factual assertion | Carpenter researched the Verde Island Passage. |
| P03-C08 | Verify factual assertion | Carpenter advocated UNESCO recognition for that area. |
| P03-C09 | Verify factual assertion | Named institutions and groups issued tributes. |
| P03-C10 | Verify attribution | Cardino condemned the killing and promised accountability. |

Expected verdict: **pending source adjudication**, not preset to Verified. Supporting evidence must establish the particular assertion; partial coverage must identify unsupported components. Source unavailable/outside policy is distinct from contradiction.

### Observed behavior
Result: None. Message: IRIS could not complete the evidence review. Please retry; no verdict was issued for this claim.
Profiler route: not recorded; extraction status: not recorded; language: not recorded.
| Output ID | Extracted claim | Verdict | Cache hit | Evidence links |
|---|---|---|---|---:|
| - | No final claim list captured; inspect stage outputs for pre-error extraction. | - | - | - |

### Recorded stages
| Stage | Execution | Duration ms | Domain outcome |
|---|---|---:|---|
| request.parse_validate | completed | 0.18649996491149068 | Not recorded |
| text.language | completed | 61.23729998944327 | Not recorded |
| text.translation | completed | 3.0181999900378287 | Not recorded |
| text.profile_local | completed | 26.820499973837286 | ok |
| text.profile_ai | completed | 11470.229800033849 | ok |
| text.profile_merge | completed | 0.0733000342734158 | ok |
| text.profile | completed | 11515.653200040106 | ok |
| text.opinion | completed | 0.8369000279344618 | Not recorded |
| text.political | completed | 7.548100023996085 | Not recorded |
| claims.extract | completed | 17144.37789999647 | ok |
| claims.attribution | completed | 0.007299997378140688 | Not recorded |
| claims.attribution | completed | 0.008200004231184721 | Not recorded |
| claims.attribution | completed | 0.01309998333454132 | Not recorded |
| claims.attribution | completed | 0.005199981387704611 | Not recorded |
| claims.attribution | completed | 0.15279999934136868 | Not recorded |
| claims.attribution | completed | 0.005699985194951296 | Not recorded |
| claims.attribution | completed | 0.00500003807246685 | Not recorded |
| claims.attribution | completed | 0.01409999094903469 | Not recorded |
| claims.attribution | completed | 0.15390000771731138 | Not recorded |
| claims.attribution | completed | 0.009500014130026102 | Not recorded |
| claims.quote_mark | completed | 1.4400999643839896 | Not recorded |
| event.query | completed | 2.646799955982715 | Not recorded |
| retrieval.source_search | completed | 1835.56039998075 | ok |
| retrieval.source_search | completed | 1840.4670000309125 | ok |
| retrieval.source_search | completed | 1829.7060999902897 | ok |
| retrieval.source_search | completed | 1837.8477000514977 | ok |
| retrieval.source_search | completed | 1888.7528000050224 | ok |
| retrieval.source_search | completed | 1884.4107000040822 | ok |
| retrieval.source_search | completed | 1890.0042000459507 | ok |
| retrieval.source_search | completed | 1884.778500010725 | ok |
| retrieval.queries | completed | 1902.5511000072584 | Not recorded |
| retrieval.article_extract | completed | 996.7027000384405 | extracted |
| retrieval.article_extract | completed | 1068.1147000286728 | extracted |
| retrieval.article_extract | completed | 1823.6113000311889 | extracted |
| retrieval.article_extract | completed | 2268.494700023439 | extracted |
| retrieval.article_extract | completed | 2306.2118999660015 | extracted |
| retrieval.article_extract | completed | 2358.777799992822 | extracted |
| retrieval.article_extract | completed | 2852.587500005029 | extracted |
| retrieval.article_extract | completed | 2897.0166000071913 | extracted |
| retrieval.article_extract | completed | 1079.7784999595024 | error |
| retrieval.article_extract | completed | 736.6174999624491 | error |
| retrieval.article_extract | completed | 880.6790999951772 | error |
| retrieval.article_extract | completed | 866.2912999861874 | error |
| retrieval.article_extract | completed | 2256.197799986694 | extracted |
| retrieval.article_extract | completed | 607.3979000211693 | error |
| retrieval.article_extract | completed | 580.2860999829136 | error |
| retrieval.article_extract | completed | 2754.1699999710545 | extracted |
| retrieval.pool | completed | 5749.45929995738 | Not recorded |
| event.retrieve | completed | 5774.170099990442 | ok |
| claim.cache_read | completed | 4.553799983114004 | Not recorded |
| claim.process | completed | 9.415699983946979 | cache_hit |
| claim.paraphrase_ai | completed | 3745.316600019578 | ok |
| claim.paraphrase | completed | 3745.5270000500605 | ok |
| claim.cache_read | completed | 3.3254000009037554 | Not recorded |
| text.political | completed | 0.37650001468136907 | Not recorded |
| claim.political | completed | 0.5990999634377658 | Not recorded |
| claim.retrieve | completed | 0.026499968953430653 | Not recorded |
| retrieval.status | completed | 0.01639995025470853 | ok |
| model.semantic_load | completed | 0.008800008799880743 | Not recorded |
| model.semantic_load | completed | 0.00879995059221983 | Not recorded |
| model.semantic_load | completed | 0.005799985956400633 | Not recorded |
| model.semantic_load | completed | 0.007100054062902927 | Not recorded |
| model.semantic_load | completed | 0.005999987479299307 | Not recorded |
| model.semantic_load | completed | 0.008500006515532732 | Not recorded |
| model.semantic_load | completed | 0.008300004992634058 | Not recorded |
| model.semantic_load | completed | 0.009399955160915852 | Not recorded |
| model.semantic_load | completed | 0.012000033166259527 | Not recorded |
| model.semantic_load | completed | 0.007499998901039362 | Not recorded |
| model.semantic_load | completed | 0.00790000194683671 | Not recorded |
| claim.semantic | completed | 1068.0396999814548 | Not recorded |
| claim.fallback_ai | completed | 1852.4379000300542 | ok |
| claim.fallback | completed | 1868.873200030066 | Not recorded |
| claim.attribution_gate | completed | 0.004199973773211241 | Not recorded |
| claim.evidence_gate | completed | 1.1679999879561365 | Not recorded |
| claim.attribution_gate | completed | 0.006199989002197981 | Not recorded |
| claim.attribution_gate | completed | 0.004299974534660578 | Not recorded |
| claim.attribution_gate | completed | 0.008100003469735384 | Not recorded |
| claim.attribution_gate | completed | 0.004599976819008589 | Not recorded |
| claim.attribution_gate | completed | 0.006699992809444666 | Not recorded |
| claim.attribution_gate | completed | 0.005499983672052622 | Not recorded |
| claim.attribution_gate | completed | 0.003300025127828121 | Not recorded |
| claim.attribution_gate | completed | 0.005599984433501959 | Not recorded |
| claim.attribution_gate | completed | 0.006600050255656242 | Not recorded |
| claim.attribution_gate | completed | 0.006699992809444666 | Not recorded |
| claim.cache_write | completed | 10.352799959946424 | Not recorded |
| claim.process | completed | 6829.475999984425 | Not recorded |
| claim.cache_read | completed | 3.84780002059415 | Not recorded |
| claim.process | completed | 6.7066000192426145 | cache_hit |
| claim.cache_read | completed | 5.759699968621135 | Not recorded |
| claim.process | completed | 8.860300004016608 | cache_hit |
| claim.paraphrase_ai | completed | 2349.1791000124067 | ok |
| claim.paraphrase | completed | 2349.3937999592163 | ok |
| claim.cache_read | completed | 3.0129000078886747 | Not recorded |
| text.political | completed | 0.6011999794282019 | Not recorded |
| claim.political | completed | 0.8970000199042261 | Not recorded |
| claim.retrieve | completed | 0.02080004196614027 | Not recorded |
| retrieval.status | completed | 0.013699987903237343 | ok |
| model.semantic_load | completed | 0.008300004992634058 | Not recorded |
| model.semantic_load | completed | 0.005300040356814861 | Not recorded |
| model.semantic_load | completed | 0.00689999433234334 | Not recorded |
| model.semantic_load | completed | 0.006799993570894003 | Not recorded |
| model.semantic_load | completed | 0.01079996582120657 | Not recorded |
| model.semantic_load | completed | 0.005599984433501959 | Not recorded |
| model.semantic_load | completed | 0.005600042641162872 | Not recorded |
| model.semantic_load | completed | 0.007499998901039362 | Not recorded |
| model.semantic_load | completed | 0.007500057108700275 | Not recorded |
| model.semantic_load | completed | 0.006099988240748644 | Not recorded |
| model.semantic_load | completed | 0.006399990525096655 | Not recorded |
| claim.semantic | completed | 843.3713999693282 | Not recorded |
| claim.fallback_ai | completed | 1648.8428000011481 | ok |
| claim.fallback | completed | 1662.8136000363156 | Not recorded |
| claim.evidence_gate | completed | 0.005500041879713535 | Not recorded |
| claim.attribution_gate | completed | 1.5033000381663442 | Not recorded |
| claim.attribution_gate | completed | 0.478199974168092 | Not recorded |
| claim.attribution_gate | completed | 0.5301999626681209 | Not recorded |
| claim.attribution_gate | completed | 0.7551999879069626 | Not recorded |
| claim.attribution_gate | completed | 0.7876000017859042 | Not recorded |
| claim.attribution_gate | completed | 0.3010999644175172 | Not recorded |
| claim.attribution_gate | completed | 0.5582000012509525 | Not recorded |
| claim.attribution_gate | completed | 0.4264999879524112 | Not recorded |
| claim.attribution_gate | completed | 0.4430999979376793 | Not recorded |
| claim.attribution_gate | completed | 0.2794000320136547 | Not recorded |
| claim.component_ai | completed | 2083.7910000118427 | Not recorded |
| claim.component_review | completed | 2390.670399996452 | error |
| claim.process | error | 7378.00160003826 | Not recorded |
| text.process | error | 48914.342000032775 | Not recorded |

### Evidence review worksheet
System-recorded URLs and quotations below are candidates for human inspection, NOT gold references. Missing fields must not be invented.
| Claim | Candidate URL | Recorded passage | Human relationship / policy / access-date review |
|---|---|---|---|
| All remaining expected labels | Pending reference URL | Pending inspected verbatim passage | Pending |

### Diagnosis and next regression
HTTP503 is a processing failure. Zero final claims is not evidence that zero claims were extracted before the error. Ignore evaluative tribute language as separate factual claims.
Reviewer sign-off: pending. Matched expected IDs: pending. Correct / extra / missed outputs: pending. Final reference verdict and disagreement resolution: pending.
Retest the exact input after a scoped change; preserve the new TRACE ID, configuration and cache-hit flags. Require appropriate routing, preserved context, auditable evidence and no technical-failure verdict.


## Case 4

TRACE: `214b112b076e42c6a7645335108d3c0c`

### Original input
Bea Borres and her ex, Meray Yamada, are back in the same frame, but Bea made it clear that their reunion doesn’t mean they’re co-parenting their daughter, Victoria Hope

### Expected extraction and routing (proposed)
| Label ID | Expected route | Assertion / required context |
|---|---|---|
| P04-C01 | Verify factual assertion | Bea Borres and Meray Yamada appeared together again; establish what reunion refers to. |
| P04-C02 | Verify attribution | Bea stated the reunion did not mean they were co-parenting Victoria Hope; do not infer actual parenting arrangements from the denial alone. |

Expected verdict: **pending source adjudication**, not preset to Verified. Supporting evidence must establish the particular assertion; partial coverage must identify unsupported components. Source unavailable/outside policy is distinct from contradiction.

### Observed behavior
Result: No Checkable Claims. Message: IRIS did not find factual claims that can be checked against approved sources.
Profiler route: stop_no_checkable_claims; extraction status: not_run_content_profiler; language: english.
| Output ID | Extracted claim | Verdict | Cache hit | Evidence links |
|---|---|---|---|---:|
| - | No final claim list captured; inspect stage outputs for pre-error extraction. | - | - | - |

### Recorded stages
| Stage | Execution | Duration ms | Domain outcome |
|---|---|---:|---|
| request.parse_validate | completed | 0.13780000153928995 | Not recorded |
| text.language | completed | 3.942799987271428 | Not recorded |
| text.translation | completed | 0.3360999980941415 | Not recorded |
| text.profile_local | completed | 2.3909000447019935 | ok |
| text.profile_ai | completed | 2860.7717999839224 | ok |
| text.profile_merge | completed | 0.03220001235604286 | ok |
| text.profile | completed | 2865.934000001289 | ok |
| text.opinion | completed | 0.21719996584579349 | Not recorded |
| text.political | completed | 0.7493000011891127 | Not recorded |
| text.process | completed | 2875.709000043571 | Not recorded |

### Evidence review worksheet
System-recorded URLs and quotations below are candidates for human inspection, NOT gold references. Missing fields must not be invented.
| Claim | Candidate URL | Recorded passage | Human relationship / policy / access-date review |
|---|---|---|---|
| All remaining expected labels | Pending reference URL | Pending inspected verbatim passage | Pending |

### Diagnosis and next regression
No Checkable Claims conflicts with the proposed eligibility labels. Confirm scope policy before adjudicating celebrity-news examples.
Reviewer sign-off: pending. Matched expected IDs: pending. Correct / extra / missed outputs: pending. Final reference verdict and disagreement resolution: pending.
Retest the exact input after a scoped change; preserve the new TRACE ID, configuration and cache-hit flags. Require appropriate routing, preserved context, auditable evidence and no technical-failure verdict.

### Recorded excluded segments
| Text | Type | Reason |
|---|---|---|
| Bea Borres and her ex, Meray Yamada, are back in the same frame, but Bea made it clear that their reunion doesn’t mean they’re co-parenting their daughter, Victoria Hope | unclear | ['low_classifier_confidence'] |

## Case 5

TRACE: `ca9ac265af86450fa09a84ffec43755e`

### Original input
Senator-Judge Robin Padilla became emotional as he sought clarification on the Senate’s position regarding the grave threats case against Vice President Sara Duterte. In his manifestation on Monday, Padilla pointed out that Duterte, as a sitting Vice President, is an impeachable officer under the 1987 Constitution. “Ako po ay binalot ng mga karimarimarim na balita nitong nakaraang araw. Ang isang sitting vice president po ay isang impeachable officer. Ito po ay tahasang nakalagay sa 1987 Constitution, Article 11, Section 2,” Padilla said. He noted that impeachment is the constitutional mechanism for holding impeachable officers politically accountable and removing them from office over impeachable offenses. Padilla then asked Senate President Win Gatchalian about the chamber’s position on the developments involving Duterte. “Ginoong Pangulo, ang minorya ay nagtatanong. Ano po ang posisyon ng Senado dito?… Ano ba naman itong nangyayaring ito sa atin, Ginoong Pangulo, kailangan po natin malinawan ito dahil nahahati po ang ating mga kababayan sa nangyayaring ito. Hindi po ito nakakatulong sa atin,” he said. Duterte posted ₱360,000 bail on Saturday for three counts of grave threats involving President Ferdinand Marcos Jr., First Lady Liza Araneta-Marcos and former House Speaker Martin Romualdez.

### Expected extraction and routing (proposed)
| Label ID | Expected route | Assertion / required context |
|---|---|---|
| P05-C01 | Verify attribution | Padilla said the sitting Vice President is an impeachable officer, citing the constitutional provision; merge repeated direct quote/paraphrase. |
| P05-C02 | Verify attribution | Padilla described impeachment as a mechanism for accountability and removal. |
| P05-C03 | Verify attribution | Padilla asked Gatchalian/the Senate to clarify its position; preserve named recipient. |
| P05-C04 | Verify factual assertion | Duterte posted PHP360,000 bail on Saturday for three grave-threat counts involving the three named people. |

Expected verdict: **pending source adjudication**, not preset to Verified. Supporting evidence must establish the particular assertion; partial coverage must identify unsupported components. Source unavailable/outside policy is distinct from contradiction.

### Observed behavior
Result: Multiple Claims Checked. Message: IRIS checked 2 extracted claims individually.
Profiler route: verify_factual_claims_only; extraction status: ok; language: tagalog.
| Output ID | Extracted claim | Verdict | Cache hit | Evidence links |
|---|---|---|---|---:|
| 1 | Padilla pointed out that Duterte, as a sitting Vice President, is an impeachable officer under the 1987 Constitution. | Verified | True | 1 |
| 2 | Padilla asked Senate President Win Gatchalian about the chamber’s position on the developments involving Duterte. | Partially Verified | True | 1 |

### Recorded stages
| Stage | Execution | Duration ms | Domain outcome |
|---|---|---:|---|
| request.parse_validate | completed | 0.27899997076019645 | Not recorded |
| text.language | completed | 12.238399998750538 | Not recorded |
| text.translation | completed | 491.41650000819936 | Not recorded |
| text.profile_local | completed | 14.838100003544241 | ok |
| text.profile_ai | completed | 3496.366199979093 | ok |
| text.profile_merge | completed | 0.06740004755556583 | ok |
| text.profile | completed | 3522.500500024762 | ok |
| text.opinion | completed | 0.6094000418670475 | Not recorded |
| text.political | completed | 3.747600014321506 | Not recorded |
| claims.extract | completed | 5922.669799998403 | ok |
| claims.attribution | completed | 0.15580002218484879 | Not recorded |
| claims.attribution | completed | 0.06769999163225293 | Not recorded |
| claims.quote_mark | completed | 0.014299992471933365 | Not recorded |
| event.retrieve | completed | 0.02400000812485814 | not_needed |
| claim.cache_read | completed | 2.7688999543897808 | Not recorded |
| claim.process | completed | 5.3746000048704445 | cache_hit |
| claim.cache_read | completed | 2.382099977694452 | Not recorded |
| claim.process | completed | 5.469400028232485 | cache_hit |
| request.assemble | completed | 0.017700018361210823 | Not recorded |
| text.process | completed | 9994.604899955448 | Not recorded |

### Evidence review worksheet
System-recorded URLs and quotations below are candidates for human inspection, NOT gold references. Missing fields must not be invented.
| Claim | Candidate URL | Recorded passage | Human relationship / policy / access-date review |
|---|---|---|---|
| 1 | https://newsinfo.inquirer.net/2300646/padilla-why-not-extend-presidential-immunity-from-suit-to-vp-duterte | Padilla said that while there is nothing in the 1987 Constitution stating that the vice president is immune from suit, there is also no provision stating otherwise. | Pending independent inspection |
| 2 | https://newsinfo.inquirer.net/2300646/padilla-why-not-extend-presidential-immunity-from-suit-to-vp-duterte | Padilla then appealed to the Senate to clarify the upper chamber’s position on the matter. | Pending independent inspection |
| All remaining expected labels | Pending reference URL | Pending inspected verbatim passage | Pending |

### Diagnosis and next regression
Two outputs do not cover all four proposed assertions. Bail is a separate factual claim; quoted restatements should not inflate the denominator. Emotional framing need not become another claim.
Reviewer sign-off: pending. Matched expected IDs: pending. Correct / extra / missed outputs: pending. Final reference verdict and disagreement resolution: pending.
Retest the exact input after a scoped change; preserve the new TRACE ID, configuration and cache-hit flags. Require appropriate routing, preserved context, auditable evidence and no technical-failure verdict.

### Recorded excluded segments
| Text | Type | Reason |
|---|---|---|
| Senator-Judge Robin Padilla became emotional as he sought clarification on the Senate’s position regarding the grave threats case against Vice President Sara Duterte. | unclear | [] |
| “Ako po ay binalot ng mga karimarimarim na balita nitong nakaraang araw. | unclear | [] |
| Ang isang sitting vice president po ay isang impeachable officer. | unclear | ['low_classifier_confidence'] |
| Ito po ay tahasang nakalagay sa 1987 Constitution, Article 11, Section 2,” Padilla said. | unclear | [] |
| He noted that impeachment is the constitutional mechanism for holding impeachable officers politically accountable and removing them from office over impeachable offenses. | unclear | [] |
| “Ginoong Pangulo, ang minorya ay nagtatanong. | unclear | [] |
| Ano po ang posisyon ng Senado dito?… Ano ba naman itong nangyayaring ito sa atin, Ginoong Pangulo, kailangan po natin malinawan ito dahil nahahati po ang ating mga kababayan sa nangyayaring ito. | unclear | ['low_classifier_confidence'] |
| Hindi po ito nakakatulong sa atin,” he said. | unclear | ['low_classifier_confidence'] |
| Duterte posted ₱360,000 bail on Saturday for three counts of grave threats involving President Ferdinand Marcos Jr., First Lady Liza Araneta-Marcos and former House Speaker Martin Romualdez. | unclear | [] |

## Case 6

TRACE: `48f717ee56b3485a837bd63cb054d10d`

### Original input
"ANG GALING NI SEC. VINCE" Muling nabuksan ang usapin sa kalidad ng EDSA rehabilitation project matapos maiulat na ilang bahagi ng kalsadang isinailalim sa road reblocking ay nagkaroon na agad ng mga lubak at pagkabakbak sa kabila ng kamakailang pagkakagawa nito. Batay sa ulat ng 24 Oras, kabilang sa mga apektadong lugar ang ilang seksyon ng EDSA Busway at mga bahagi ng Phase 1 ng road reblocking project na sinimulan noong bisperas ng Pasko noong nakaraang taon. Tinatayang aabot sa P1.2 bilyon ang halaga ng naturang proyekto. Dahil dito, binatikos ni veteran broadcaster Jay Sonza ang Department of Public Works and Highways (DPWH) sa ilalim ni Secretary Vince Dizon. Sa kanyang social media post, kinuwestiyon niya kung bakit nagkaroon agad ng sira ang ilang bahagi ng EDSA sa kabila ng malaking pondong inilaan para sa rehabilitasyon. Sa ngayon, wala pang inilalabas na pahayag si Dizon kaugnay sa mga batikos at sa ulat hinggil sa kondisyon ng ilang bagong inayos na bahagi ng pangunahing lansangan sa Metro Manila.

### Expected extraction and routing (proposed)
| Label ID | Expected route | Assertion / required context |
|---|---|---|
| P06-C01 | Verify factual assertion | Recently reblocked EDSA sections developed potholes and surface damage. |
| P06-C02 | Verify attribution | 24 Oras reported affected EDSA Busway/Phase 1 locations and the Christmas Eve project start. |
| P06-C03 | Verify factual assertion | The project estimated cost was PHP1.2 billion; preserve estimate, not actual expenditure. |
| P06-C04 | Verify attribution | Jay Sonza criticized DPWH under Dizon and questioned rapid road damage despite funding; merge repeated description. |
| P06-C05 | Verify factual assertion | No response from Dizon had been issued as of the report; time-bound absence claim requires cautious evidence review. |

Expected verdict: **pending source adjudication**, not preset to Verified. Supporting evidence must establish the particular assertion; partial coverage must identify unsupported components. Source unavailable/outside policy is distinct from contradiction.

### Observed behavior
Result: No Checkable Claims. Message: IRIS did not find factual claims that can be checked against sources.
Profiler route: verify_factual_claims_only; extraction status: empty_ai_result; language: tagalog.
| Output ID | Extracted claim | Verdict | Cache hit | Evidence links |
|---|---|---|---|---:|
| - | No final claim list captured; inspect stage outputs for pre-error extraction. | - | - | - |

### Recorded stages
| Stage | Execution | Duration ms | Domain outcome |
|---|---|---:|---|
| request.parse_validate | completed | 0.20239996956661344 | Not recorded |
| text.language | completed | 13.874399999622256 | Not recorded |
| text.translation | completed | 515.0825000018813 | Not recorded |
| text.profile_local | completed | 8.297999971546233 | ok |
| text.profile_ai | completed | 3955.463799997233 | ok |
| text.profile_merge | completed | 0.05530001362785697 | ok |
| text.profile | completed | 3972.2369000082836 | ok |
| text.opinion | completed | 0.27540000155568123 | Not recorded |
| text.political | completed | 2.4314000038430095 | Not recorded |
| claims.extract | completed | 1879.082900006324 | empty_ai_result |
| text.process | completed | 6390.366600011475 | Not recorded |

### Evidence review worksheet
System-recorded URLs and quotations below are candidates for human inspection, NOT gold references. Missing fields must not be invented.
| Claim | Candidate URL | Recorded passage | Human relationship / policy / access-date review |
|---|---|---|---|
| All remaining expected labels | Pending reference URL | Pending inspected verbatim passage | Pending |

### Diagnosis and next regression
Quotation/abbreviation boundaries and original-to-translated alignment need review. Empty usable extraction is not proof the input contains no facts.
Reviewer sign-off: pending. Matched expected IDs: pending. Correct / extra / missed outputs: pending. Final reference verdict and disagreement resolution: pending.
Retest the exact input after a scoped change; preserve the new TRACE ID, configuration and cache-hit flags. Require appropriate routing, preserved context, auditable evidence and no technical-failure verdict.

### Recorded excluded segments
| Text | Type | Reason |
|---|---|---|
| VINCE" Muling nabuksan ang usapin sa kalidad ng EDSA rehabilitation project matapos maiulat na ilang bahagi ng kalsadang isinailalim sa road reblocking ay nagkaroon na agad ng mga lubak at pagkabakbak sa kabila ng kamakailang pagkakagawa nito. | unclear | ['low_classifier_confidence'] |
| Batay sa ulat ng 24 Oras, kabilang sa mga apektadong lugar ang ilang seksyon ng EDSA Busway at mga bahagi ng Phase 1 ng road reblocking project na sinimulan noong bisperas ng Pasko noong nakaraang taon. | unclear | ['low_classifier_confidence'] |
| Tinatayang aabot sa P1.2 bilyon ang halaga ng naturang proyekto. | unclear | ['low_classifier_confidence'] |
| Dahil dito, binatikos ni veteran broadcaster Jay Sonza ang Department of Public Works and Highways (DPWH) sa ilalim ni Secretary Vince Dizon. | unclear | [] |
| Sa kanyang social media post, kinuwestiyon niya kung bakit nagkaroon agad ng sira ang ilang bahagi ng EDSA sa kabila ng malaking pondong inilaan para sa rehabilitasyon. | unclear | [] |
| Sa ngayon, wala pang inilalabas na pahayag si Dizon kaugnay sa mga batikos at sa ulat hinggil sa kondisyon ng ilang bagong inayos na bahagi ng pangunahing lansangan sa Metro Manila. | unclear | ['low_classifier_confidence'] |
| THE GREATNESS OF SEC. | uncheckable | Not recorded |

## Case 7

TRACE: `9fe83e8c73cc45bd8c39589f619b7f38`

### Original input
Senator-judge Robin Padilla asks state auditor Roderick Wamil about his personal background, noting whether he understood the need for medicines in far-flung areas and the threat of terrorism in the country—issues cited as among the reasons for Vice President Sara Duterte’s use of confidential funds.

### Expected extraction and routing (proposed)
| Label ID | Expected route | Assertion / required context |
|---|---|---|
| P07-C01 | Verify attribution | Padilla questioned Wamil about his personal background. |
| P07-C02 | Verify attribution | The questioning included the need for medicines in remote areas. |
| P07-C03 | Verify attribution | The questioning included terrorism threats. |
| P07-C04 | Verify attribution | These issues were cited as reasons for confidential-fund use; do not convert a cited rationale into proof of actual fund use. |

Expected verdict: **pending source adjudication**, not preset to Verified. Supporting evidence must establish the particular assertion; partial coverage must identify unsupported components. Source unavailable/outside policy is distinct from contradiction.

### Observed behavior
Result: None. Message: IRIS could not complete the evidence review. Please retry; no verdict was issued for this claim.
Profiler route: not recorded; extraction status: not recorded; language: not recorded.
| Output ID | Extracted claim | Verdict | Cache hit | Evidence links |
|---|---|---|---|---:|
| - | No final claim list captured; inspect stage outputs for pre-error extraction. | - | - | - |

### Recorded stages
| Stage | Execution | Duration ms | Domain outcome |
|---|---|---:|---|
| request.parse_validate | completed | 0.1284000463783741 | Not recorded |
| text.language | completed | 1.9609000300988555 | Not recorded |
| text.translation | completed | 0.43289997847750783 | Not recorded |
| text.profile_local | completed | 3.4838999854400754 | ok |
| text.profile | completed | 4.355999990366399 | ok |
| text.opinion | completed | 0.13970001600682735 | Not recorded |
| text.political | completed | 1.09779997728765 | Not recorded |
| claims.extract | completed | 4290.121599973645 | ok |
| claims.attribution | completed | 0.062700011767447 | Not recorded |
| claims.quote_mark | completed | 0.003600027412176132 | Not recorded |
| event.retrieve | completed | 0.016200006939470768 | not_needed |
| claim.cache_read | completed | 2.448699960950762 | Not recorded |
| text.political | completed | 1.0460999910719693 | Not recorded |
| claim.political | completed | 1.7477000365033746 | Not recorded |
| retrieval.source_search | completed | 1759.1007000301033 | ok |
| retrieval.source_search | completed | 1791.5410000132397 | ok |
| retrieval.source_search | completed | 1779.5796999707818 | ok |
| retrieval.source_search | completed | 1842.043599986937 | ok |
| retrieval.source_search | completed | 1838.6478000320494 | ok |
| retrieval.source_search | completed | 1866.5288999909535 | ok |
| retrieval.source_search | completed | 1861.0209000180475 | ok |
| retrieval.source_search | completed | 1924.9853999936022 | ok |
| retrieval.queries | completed | 1933.7342000217177 | Not recorded |
| retrieval.article_extract | completed | 799.7821999597363 | extracted |
| retrieval.article_extract | completed | 1191.1532999947667 | extracted |
| retrieval.article_extract | completed | 1336.0194999841042 | extracted |
| retrieval.article_extract | completed | 1710.3134999633767 | extracted |
| retrieval.article_extract | completed | 1823.7098000245169 | extracted |
| retrieval.article_extract | completed | 1872.375299979467 | extracted |
| retrieval.article_extract | completed | 667.9276999784634 | error |
| retrieval.article_extract | completed | 704.2870000004768 | error |
| retrieval.article_extract | completed | 609.4710000324994 | error |
| retrieval.article_extract | completed | 699.5908999815583 | error |
| retrieval.article_extract | completed | 2856.2515000230633 | extracted |
| retrieval.article_extract | completed | 2923.1837999541312 | extracted |
| retrieval.article_extract | completed | 2184.731500048656 | extracted |
| retrieval.article_extract | completed | 571.994999947492 | error |
| retrieval.article_extract | completed | 1848.4757000114769 | extracted |
| retrieval.article_extract | completed | 5062.724500021432 | error |
| retrieval.pool | completed | 9030.332299997099 | Not recorded |
| claim.retrieve | completed | 9058.47150000045 | Not recorded |
| retrieval.status | completed | 0.02540001878514886 | ok |
| model.semantic_load | completed | 0.04800001624971628 | Not recorded |
| model.semantic_load | completed | 0.009300012607127428 | Not recorded |
| model.semantic_load | completed | 0.00600004568696022 | Not recorded |
| model.semantic_load | completed | 0.006299989763647318 | Not recorded |
| model.semantic_load | completed | 0.008200004231184721 | Not recorded |
| model.semantic_load | completed | 0.00689999433234334 | Not recorded |
| model.semantic_load | completed | 0.006699992809444666 | Not recorded |
| model.semantic_load | completed | 0.010200019460171461 | Not recorded |
| model.semantic_load | completed | 0.01009996049106121 | Not recorded |
| model.semantic_load | completed | 0.006700051017105579 | Not recorded |
| model.semantic_load | completed | 0.009400013368576765 | Not recorded |
| claim.semantic | completed | 1094.0866000019014 | Not recorded |
| claim.fallback_ai | completed | 2214.368099987041 | ok |
| claim.fallback | completed | 2236.486900015734 | Not recorded |
| claim.attribution_gate | completed | 0.4515000036917627 | Not recorded |
| claim.attribution_gate | completed | 0.4712999798357487 | Not recorded |
| claim.attribution_gate | completed | 0.4039999912492931 | Not recorded |
| claim.attribution_gate | completed | 0.6679000216536224 | Not recorded |
| claim.attribution_gate | completed | 2.3919999948702753 | Not recorded |
| claim.attribution_gate | completed | 0.46360003761947155 | Not recorded |
| claim.evidence_gate | completed | 15.85009996779263 | Not recorded |
| claim.attribution_gate | completed | 3.085100033786148 | Not recorded |
| claim.attribution_gate | completed | 1.3765000039711595 | Not recorded |
| claim.attribution_gate | completed | 0.41829998372122645 | Not recorded |
| claim.attribution_gate | completed | 0.9078000439330935 | Not recorded |
| claim.attribution_gate | completed | 0.5979000125080347 | Not recorded |
| claim.attribution_gate | completed | 0.9439000277779996 | Not recorded |
| claim.attribution_gate | completed | 1.5199999907054007 | Not recorded |
| claim.attribution_gate | completed | 0.9972000261768699 | Not recorded |
| claim.attribution_gate | completed | 0.5764999659731984 | Not recorded |
| claim.attribution_gate | completed | 0.5026999861001968 | Not recorded |
| claim.component_ai | completed | 2198.8849999615923 | Not recorded |
| claim.component_review | completed | 2561.5461000124924 | error |
| claim.process | error | 15138.781299989205 | Not recorded |
| text.process | error | 19448.49989999784 | Not recorded |

### Evidence review worksheet
System-recorded URLs and quotations below are candidates for human inspection, NOT gold references. Missing fields must not be invented.
| Claim | Candidate URL | Recorded passage | Human relationship / policy / access-date review |
|---|---|---|---|
| All remaining expected labels | Pending reference URL | Pending inspected verbatim passage | Pending |

### Diagnosis and next regression
Four components may remain one displayed compound claim; evaluate component coverage separately from the number of UI cards. Processing error is not Not Found.
Reviewer sign-off: pending. Matched expected IDs: pending. Correct / extra / missed outputs: pending. Final reference verdict and disagreement resolution: pending.
Retest the exact input after a scoped change; preserve the new TRACE ID, configuration and cache-hit flags. Require appropriate routing, preserved context, auditable evidence and no technical-failure verdict.


## Case 8

TRACE: `1a0a6ff587e14e95a2a421032d4845ff`

### Original input
'NAGLALARO AKO NG CALL OF DUTY, HINDI KO NAISIP KAILANMAN NA MAMARIL SA LABAS' The rush to blame video games for school violence is not supported by science, a cybersecurity and technology expert said Saturday, pushing back against calls to ban video games in the wake of a shooting incident involving a minor in Tacloban City. Cybersecurity and technology expert Art Samaniego Jr. made the argument in an interview on DZRH News program "Special on Saturday" on July 4, citing research by the Oxford Internet Institute showing no direct link between violent video games and real-world crime or violence. "Naglalaro ako ng Call of Duty, hindi ko naisip kailanman na mamaril sa labas. Maraming pag-aaral ang ginawa na nagpapatunay na walang matibay na ebidensya na nagsasabing ang video game ay may direktang dahilan sa school violence o crime in real life," Samaniego said. He said the real cause of the Tacloban school shooting was not GoreBox—the game the 14-year-old shooter allegedly played—but the people the child was communicating with online, and that extremist recruiters and online predators follow children across platforms regardless of which game or app they use. "Ang tunay na dahilan nun hindi 'yung laro, kundi 'yung mga taong nakakausap nung bata online. Ang dapat nating gawin hindi i-ban 'yung game, kundi tingnan ang kabuuang isyu," Samaniego said. He warned that banning GoreBox specifically is futile since more than 20 similar games exist on mobile platforms alone, and more on PC and console—and children, he said, have no loyalty to specific platforms and will simply migrate to the next available option. Samaniego said the real enforcement gap is not the existence of violent games but the failure to implement existing age ratings—GoreBox is an 18+ game that a 14-year-old was able to access—drawing a direct comparison to the MTRCB film rating system. "Para 'yang sa MTRCB, merong rating. Kung sa MTRCB may ginawang pelikula ang Vivamax tapos may nakapanood na 12-year-old, ipapasara ba natin ang Vivamax? O titingnan natin bakit siya nakapasok sa sinehan dahil mali ang implementation? Ganun lang 'yun dapat ang isipin ng mga lawmakers," Samaniego said.

### Expected extraction and routing (proposed)
| Label ID | Expected route | Assertion / required context |
|---|---|---|
| P08-C01 | Verify attribution | Samaniego made the science/video-game argument during the stated DZRH program and date; verify attribution independently of scientific truth. |
| P08-C02 | Verify attribution | He used his own Call of Duty experience as an example; do not present anecdote as causal evidence. |
| P08-C03 | Verify attribution | He attributed the shooting to online contacts rather than GoreBox and warned about predators across platforms. |
| P08-C04 | Verify attribution | He said over 20 similar mobile games existed and warned that bans would prompt migration. |
| P08-C05 | Verify attribution | He described the failure to enforce age ratings, including the reported age mismatch. |
| P08-C06 | Verify attribution | He made the MTRCB/Vivamax analogy; preserve it as a hypothetical argument, not an actual incident. |

Expected verdict: **pending source adjudication**, not preset to Verified. Supporting evidence must establish the particular assertion; partial coverage must identify unsupported components. Source unavailable/outside policy is distinct from contradiction.

### Observed behavior
Result: Multiple Claims Checked. Message: IRIS checked 6 extracted claims individually.
Profiler route: not recorded; extraction status: not recorded; language: not recorded.
| Output ID | Extracted claim | Verdict | Cache hit | Evidence links |
|---|---|---|---|---:|
| - | No final claim list captured; inspect stage outputs for pre-error extraction. | - | - | - |

Audit-document observation: all six final claims were reported as Not Found. The first TRACE run has partial capture and no complete final claim payload; do not substitute an intermediate semantic or fallback verdict for the final result.

### Recorded stages
| Stage | Execution | Duration ms | Domain outcome |
|---|---|---:|---|
| request.parse_validate | completed | 0.14640000881627202 | Not recorded |
| text.language | completed | 6.87599997036159 | Not recorded |
| text.translation | completed | 908.8287999620661 | Not recorded |
| text.profile_local | completed | 19.75539996055886 | ok |
| text.profile_ai | completed | 4017.5146000110544 | ok |
| text.profile_merge | completed | 0.07040001219138503 | ok |
| text.profile | completed | 4055.239299952518 | ok |
| text.opinion | completed | 0.6737999501638114 | Not recorded |
| text.political | completed | 6.561300018802285 | Not recorded |
| claims.extract | completed | 17521.00219996646 | ok |
| claims.attribution | completed | 0.19839999731630087 | Not recorded |
| claims.attribution | completed | 0.39900001138448715 | Not recorded |
| claims.attribution | completed | 0.21839997498318553 | Not recorded |
| claims.attribution | completed | 0.2919000107795 | Not recorded |
| claims.attribution | completed | 0.3668999997898936 | Not recorded |
| claims.attribution | completed | 0.1900999923236668 | Not recorded |
| claims.quote_mark | completed | 0.01680001150816679 | Not recorded |
| event.query | completed | 1.853100024163723 | Not recorded |
| retrieval.source_search | completed | 1638.4567000204697 | ok |
| retrieval.source_search | completed | 1677.4232999887317 | ok |
| retrieval.source_search | completed | 1702.214399992954 | ok |
| retrieval.source_search | completed | 1701.2058999971487 | ok |
| retrieval.source_search | completed | 1713.0955000175163 | ok |
| retrieval.source_search | completed | 1715.3130999649875 | ok |
| retrieval.source_search | completed | 1749.0772000164725 | ok |
| retrieval.source_search | completed | 1745.5650999909267 | ok |
| retrieval.queries | completed | 1757.6578999869525 | Not recorded |
| retrieval.article_extract | completed | 804.1046999860555 | extracted |
| retrieval.article_extract | completed | 853.0360999866389 | error |
| retrieval.article_extract | completed | 1325.202200037893 | extracted |
| retrieval.article_extract | completed | 1402.9005999909714 | extracted |
| retrieval.article_extract | completed | 1485.4414999717847 | extracted |
| retrieval.article_extract | completed | 1574.4352999608964 | extracted |
| retrieval.article_extract | completed | 633.42729996657 | error |
| retrieval.article_extract | completed | 606.0292999609374 | error |
| retrieval.article_extract | completed | 666.9628000236116 | error |
| retrieval.article_extract | completed | 623.8940000184812 | error |
| retrieval.article_extract | completed | 587.9777000518516 | error |
| retrieval.article_extract | completed | 576.4040999929421 | error |
| retrieval.article_extract | completed | 2875.5088999751024 | extracted |
| retrieval.article_extract | completed | 2905.8053999906406 | extracted |
| retrieval.article_extract | completed | 2159.0771000483073 | extracted |
| retrieval.article_extract | completed | 2843.8574000028893 | extracted |
| retrieval.pool | completed | 5479.657699994277 | Not recorded |
| event.retrieve | completed | 5507.566800049972 | ok |
| claim.paraphrase_ai | completed | 1799.9847000464797 | ok |
| claim.paraphrase | completed | 1800.218699965626 | ok |
| claim.cache_read | completed | 1.6482999781146646 | Not recorded |
| text.political | completed | 0.729300023522228 | Not recorded |
| claim.political | completed | 0.9467999916523695 | Not recorded |
| claim.retrieve | completed | 0.01899997005239129 | Not recorded |
| retrieval.status | completed | 0.011500029359012842 | ok |
| model.semantic_load | completed | 0.008300004992634058 | Not recorded |
| model.semantic_load | completed | 0.007099995855242014 | Not recorded |
| model.semantic_load | completed | 0.012200034689158201 | Not recorded |
| model.semantic_load | completed | 0.006999995093792677 | Not recorded |
| model.semantic_load | completed | 0.006199989002197981 | Not recorded |
| model.semantic_load | completed | 0.007299997378140688 | Not recorded |
| model.semantic_load | completed | 0.005699985194951296 | Not recorded |
| model.semantic_load | completed | 0.006100046448409557 | Not recorded |
| model.semantic_load | completed | 0.006500049494206905 | Not recorded |
| model.semantic_load | completed | 0.006299989763647318 | Not recorded |
| claim.semantic | completed | 732.9995000036433 | Not recorded |
| claim.fallback_ai | completed | 2158.648099983111 | ok |
| claim.fallback | completed | 2178.832000005059 | Not recorded |
| claim.attribution_gate | completed | 2.354099997319281 | Not recorded |
| claim.evidence_gate | completed | 5.700999987311661 | Not recorded |
| claim.attribution_gate | completed | 1.2769000022672117 | Not recorded |
| claim.attribution_gate | completed | 2.0096999942325056 | Not recorded |
| claim.attribution_gate | completed | 2.4581000325269997 | Not recorded |
| claim.attribution_gate | completed | 5.432099977042526 | Not recorded |
| claim.attribution_gate | completed | 0.9073999826796353 | Not recorded |
| claim.attribution_gate | completed | 0.6399999838322401 | Not recorded |
| claim.attribution_gate | completed | 3.102899994701147 | Not recorded |
| claim.attribution_gate | completed | 1.6781000304035842 | Not recorded |
| claim.attribution_gate | completed | 0.6173999863676727 | Not recorded |
| claim.attribution_gate | completed | 1.9878000020980835 | Not recorded |
| claim.attribution_gate | completed | 2.6011999580077827 | Not recorded |
| claim.attribution_gate | completed | 2.6186000322923064 | Not recorded |
| claim.attribution_gate | completed | 3.195400000549853 | Not recorded |
| claim.attribution_gate | completed | 0.8978000259958208 | Not recorded |
| claim.attribution_gate | completed | 0.3279999946244061 | Not recorded |
| claim.attribution_gate | completed | 3.2137000234797597 | Not recorded |
| claim.attribution_gate | completed | 1.1442999821156263 | Not recorded |
| claim.attribution_gate | completed | 0.367300002835691 | Not recorded |
| claim.cache_write | completed | 7.8443000093102455 | Not recorded |
| claim.process | completed | 4930.7137000141665 | Not recorded |
| claim.paraphrase_ai | completed | 2041.0817000083625 | ok |
| claim.paraphrase | completed | 2041.3232000428252 | ok |
| claim.cache_read | completed | 2.7725999825634062 | Not recorded |
| text.political | completed | 0.9949000086635351 | Not recorded |
| claim.political | completed | 1.653800019994378 | Not recorded |
| claim.retrieve | completed | 0.046200002543628216 | Not recorded |
| retrieval.status | completed | 0.017300015315413475 | ok |
| model.semantic_load | completed | 0.009200011845678091 | Not recorded |
| model.semantic_load | completed | 0.008400005754083395 | Not recorded |
| model.semantic_load | completed | 0.009899958968162537 | Not recorded |
| model.semantic_load | completed | 0.007599999662488699 | Not recorded |
| model.semantic_load | completed | 0.006099988240748644 | Not recorded |
| model.semantic_load | completed | 0.006400048732757568 | Not recorded |
| model.semantic_load | completed | 0.008599949069321156 | Not recorded |
| model.semantic_load | completed | 0.009200011845678091 | Not recorded |
| model.semantic_load | completed | 0.008000002708286047 | Not recorded |
| model.semantic_load | completed | 0.006599992047995329 | Not recorded |
| claim.semantic | completed | 829.5849999994971 | Not recorded |
| claim.fallback_ai | completed | 1487.051700009033 | ok |
| claim.fallback | completed | 1503.8787000230514 | Not recorded |
| claim.evidence_gate | completed | 0.006199989002197981 | Not recorded |
| claim.attribution_gate | completed | 1.392900012433529 | Not recorded |
| claim.attribution_gate | completed | 1.576300011947751 | Not recorded |
| claim.attribution_gate | completed | 1.6536999610252678 | Not recorded |
| claim.attribution_gate | completed | 3.6604999913834035 | Not recorded |
| claim.attribution_gate | completed | 0.6097000441513956 | Not recorded |
| claim.attribution_gate | completed | 0.3082000184804201 | Not recorded |
| claim.attribution_gate | completed | 2.359099977184087 | Not recorded |
| claim.attribution_gate | completed | 1.0585000272840261 | Not recorded |
| claim.attribution_gate | completed | 0.42039999971166253 | Not recorded |
| claim.attribution_gate | completed | 1.2485000188462436 | Not recorded |
| claim.attribution_gate | completed | 1.6582999960519373 | Not recorded |
| claim.attribution_gate | completed | 1.8986999639309943 | Not recorded |
| claim.attribution_gate | completed | 3.122999973129481 | Not recorded |
| claim.attribution_gate | completed | 0.6354000070132315 | Not recorded |
| claim.attribution_gate | completed | 0.3142000059597194 | Not recorded |
| claim.attribution_gate | completed | 2.081100014038384 | Not recorded |
| claim.attribution_gate | completed | 1.0390999959781766 | Not recorded |
| claim.attribution_gate | completed | 0.39549998473376036 | Not recorded |
| claim.cache_write | completed | 7.437499996740371 | Not recorded |
| claim.process | completed | 4586.747900000773 | Not recorded |
| claim.paraphrase_ai | completed | 2081.547199981287 | ok |
| claim.paraphrase | completed | 2081.7944000009447 | ok |
| claim.cache_read | completed | 2.521499991416931 | Not recorded |
| text.political | completed | 0.9191000135615468 | Not recorded |
| claim.political | completed | 1.279400021303445 | Not recorded |
| claim.retrieve | completed | 0.03470003139227629 | Not recorded |
| retrieval.status | completed | 0.012199976481497288 | ok |
| model.semantic_load | completed | 0.012399978004395962 | Not recorded |
| model.semantic_load | completed | 0.00990001717582345 | Not recorded |
| model.semantic_load | completed | 0.009700015652924776 | Not recorded |
| model.semantic_load | completed | 0.010499963536858559 | Not recorded |
| model.semantic_load | completed | 0.00790000194683671 | Not recorded |
| model.semantic_load | completed | 0.009400013368576765 | Not recorded |
| model.semantic_load | completed | 0.012999982573091984 | Not recorded |
| model.semantic_load | completed | 0.008300004992634058 | Not recorded |
| model.semantic_load | completed | 0.008100003469735384 | Not recorded |
| model.semantic_load | completed | 0.01160003012046218 | Not recorded |
| claim.semantic | completed | 1090.8544000121765 | Not recorded |
| claim.fallback_ai | completed | 2698.2042999588884 | ok |
| claim.fallback | completed | 2721.5692999889143 | Not recorded |
| claim.attribution_gate | completed | 2.2834999836049974 | Not recorded |
| claim.attribution_gate | completed | 1.4315000153146684 | Not recorded |
| claim.evidence_gate | completed | 14.504700026009232 | Not recorded |

### Evidence review worksheet
System-recorded URLs and quotations below are candidates for human inspection, NOT gold references. Missing fields must not be invented.
| Claim | Candidate URL | Recorded passage | Human relationship / policy / access-date review |
|---|---|---|---|
| All remaining expected labels | Pending reference URL | Pending inspected verbatim passage | Pending |

### Diagnosis and next regression
Six outputs are not proof of six correct extractions or verdicts. Attribution-source availability must be checked; evidence outside the allowlist cannot count as a missed approved-source retrieval.
Reviewer sign-off: pending. Matched expected IDs: pending. Correct / extra / missed outputs: pending. Final reference verdict and disagreement resolution: pending.
Retest the exact input after a scoped change; preserve the new TRACE ID, configuration and cache-hit flags. Require appropriate routing, preserved context, auditable evidence and no technical-failure verdict.


## Case 9

TRACE: `75e31974eb424e2c98736c038ea4e051`

### Original input
Nananatili pa ring bagsak ang palitan ng piso kontra dolyar matapos magsara sa ₱62.513 = $1 ngayong Miyerkules, Setyembre 9.

### Expected extraction and routing (proposed)
| Label ID | Expected route | Assertion / required context |
|---|---|---|
| P09-C01 | Verify factual assertion | The peso closed at PHP62.513 per USD1 on the date in the complete logged input; distinguish closing, intraday, official reference and retail rates. Treat bagsak as framing. |

Expected verdict: **pending source adjudication**, not preset to Verified. Supporting evidence must establish the particular assertion; partial coverage must identify unsupported components. Source unavailable/outside policy is distinct from contradiction.

### Observed behavior
Result: No Checkable Claims. Message: IRIS did not find factual claims that can be checked against approved sources.
Profiler route: stop_no_checkable_claims; extraction status: not_run_content_profiler; language: tagalog.
| Output ID | Extracted claim | Verdict | Cache hit | Evidence links |
|---|---|---|---|---:|
| - | No final claim list captured; inspect stage outputs for pre-error extraction. | - | - | - |

### Recorded stages
| Stage | Execution | Duration ms | Domain outcome |
|---|---|---:|---|
| request.parse_validate | completed | 0.2601000014692545 | Not recorded |
| text.language | completed | 1.6626999713480473 | Not recorded |
| text.translation | completed | 767.6097999792546 | Not recorded |
| text.profile_local | completed | 2.6376000023446977 | ok |
| text.profile_ai | completed | 2813.559200032614 | ok |
| text.profile_merge | completed | 0.05000003147870302 | ok |
| text.profile | completed | 2819.2260999931023 | ok |
| text.opinion | completed | 0.09549997048452497 | Not recorded |
| text.political | completed | 0.7559999939985573 | Not recorded |
| text.process | completed | 3593.2669999892823 | Not recorded |

### Evidence review worksheet
System-recorded URLs and quotations below are candidates for human inspection, NOT gold references. Missing fields must not be invented.
| Claim | Candidate URL | Recorded passage | Human relationship / policy / access-date review |
|---|---|---|---|
| All remaining expected labels | Pending reference URL | Pending inspected verbatim passage | Pending |

### Diagnosis and next regression
The full logged input controls the date and currency denominator, not the truncated heading in the audit document. Profiler exclusion blocks retrieval.
Reviewer sign-off: pending. Matched expected IDs: pending. Correct / extra / missed outputs: pending. Final reference verdict and disagreement resolution: pending.
Retest the exact input after a scoped change; preserve the new TRACE ID, configuration and cache-hit flags. Require appropriate routing, preserved context, auditable evidence and no technical-failure verdict.

### Recorded excluded segments
| Text | Type | Reason |
|---|---|---|
| Nananatili pa ring bagsak ang palitan ng piso kontra dolyar matapos magsara sa ₱62.513 = $1 ngayong Miyerkules, Setyembre 9. | unclear | ['low_classifier_confidence'] |

## Case 10

TRACE: `c34abc3719374011959edd76752ad559`

### Original input
Ten exemplary Filipinos from various fields of the arts will be proclaimed as National Artists, the country’s highest national recognition for distinct and significant contributions to the arts and letters.

### Expected extraction and routing (proposed)
| Label ID | Expected route | Assertion / required context |
|---|---|---|
| P10-C01 | Verify factual assertion | An announcement identified ten forthcoming National Artists; distinguish announced recognition from a ceremony already completed. Exclude exemplary as evaluation. |

Expected verdict: **pending source adjudication**, not preset to Verified. Supporting evidence must establish the particular assertion; partial coverage must identify unsupported components. Source unavailable/outside policy is distinct from contradiction.

### Observed behavior
Result: No Checkable Claims. Message: IRIS did not find factual claims that can be checked against approved sources.
Profiler route: stop_no_checkable_claims; extraction status: not_run_content_profiler; language: english.
| Output ID | Extracted claim | Verdict | Cache hit | Evidence links |
|---|---|---|---|---:|
| - | No final claim list captured; inspect stage outputs for pre-error extraction. | - | - | - |

### Recorded stages
| Stage | Execution | Duration ms | Domain outcome |
|---|---|---:|---|
| request.parse_validate | completed | 0.10529998689889908 | Not recorded |
| text.language | completed | 1.0940000065602362 | Not recorded |
| text.translation | completed | 0.360500009264797 | Not recorded |
| text.profile_local | completed | 2.7546000201255083 | ok |
| text.profile_ai | completed | 4023.650399991311 | ok |
| text.profile_merge | completed | 0.0323000131174922 | ok |
| text.profile | completed | 4029.275899985805 | ok |
| text.opinion | completed | 0.15029998030513525 | Not recorded |
| text.political | completed | 0.9468999924138188 | Not recorded |
| text.process | completed | 4036.004099994898 | Not recorded |

### Evidence review worksheet
System-recorded URLs and quotations below are candidates for human inspection, NOT gold references. Missing fields must not be invented.
| Claim | Candidate URL | Recorded passage | Human relationship / policy / access-date review |
|---|---|---|---|
| All remaining expected labels | Pending reference URL | Pending inspected verbatim passage | Pending |

### Diagnosis and next regression
Announcement eligibility and source-path coverage are separate. A /news search restriction may miss /lifestyle, but cannot explain a profiler stop before search.
Reviewer sign-off: pending. Matched expected IDs: pending. Correct / extra / missed outputs: pending. Final reference verdict and disagreement resolution: pending.
Retest the exact input after a scoped change; preserve the new TRACE ID, configuration and cache-hit flags. Require appropriate routing, preserved context, auditable evidence and no technical-failure verdict.

### Recorded excluded segments
| Text | Type | Reason |
|---|---|---|
| Ten exemplary Filipinos from various fields of the arts will be proclaimed as National Artists, the country’s highest national recognition for distinct and significant contributions to the arts and letters. | unclear | ['low_classifier_confidence'] |

## Repeat run and interpretation
Case 8 repeat: `2871b496bb5a4b5bbe7835cd1a1cfe44`; completed; capture partial; HTTP 200; 6 final claims; 25.94 seconds. It is excluded from the ten-case denominator. Do not interpret faster repetition as optimization without accounting for cache use.

## Next evaluation batch
1. Have two reviewers adjudicate the proposed labels and granularity, resolving disagreements.
2. Inspect and timestamp reference sources; classify support, partial support, contradiction and background separately.
3. Freeze commit plus dirty-worktree snapshot, source paths, model settings and cache policy.
4. Rerun these ten as development regressions; keep 20-30 independently selected unseen examples separate for pilot generalization.
5. Report stage-specific fractions, a verdict confusion matrix, completion rate, capture rate and regressions. Do not average stage percentages into a single accuracy score.
