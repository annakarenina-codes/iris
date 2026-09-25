# IRIS held-out batch 1: scores

Posts run: 25 · commit(s): bef8070

| Measure | Result |
|---|---|
| Claim accuracy (correct / judged) | 35/54 (65%) |
| False positives (of judged claims) | 3/54 (6%) |
| False positives among Verified/Partially Verified verdicts | 3/22 (14%) |
| False negatives (of judged claims) | 5/54 (9%) |
| Wrong verification level | 5/54 (9%) |
| Technical failures (claims) | 0/54 (0%) |
| OCR misreads (claims) | 6/54 (11%) |
| Cannot judge (excluded above) | 0 |
| Routing correct (posts) | 21/25 (84%) |
| Checkable statements IRIS missed | 0 |
| False-claim posts with any false positive | 1/4 (25%) |
| Requests that failed (HTTP not 200) | 0 |
| Response time median / max | 51s / 238s |
| Requests over 120s (Android limit) | 2 |

## By category

| Category | Posts | Claim accuracy | False positives |
|---|---|---|---|
| false_claim | 4 | 0/7 (0%) | 1 |
| filipino | 5 | 5/6 (83%) | 0 |
| news | 8 | 9/11 (82%) | 0 |
| opinion_satire | 4 | 17/19 (89%) | 2 |
| quote | 4 | 4/11 (36%) | 0 |

## Reading the pictures

| Image posts compared | 4 |
|---|---|
| Words of the recorded statement that survived OCR, median | 62% |
| Worst | 30% |

## By input

| Input | Posts | Claim accuracy | False positives |
|---|---|---|---|
| image | 4 | 0/7 (0%) | 1 |
| text | 21 | 35/47 (74%) | 2 |

Development cases are excluded by design. Scores describe this batch only, on the commits listed, with the verdict cache bypassed.
