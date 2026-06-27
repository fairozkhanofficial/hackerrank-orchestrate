# Evaluation Report: Multi-Modal Evidence Review

- Generated: 2026-06-19T22:30:40+05:30
- Model: gemini-2.5-flash (vision + decision)
- Sample claims evaluated: 20
- Architecture: balanced 2-call (vision extraction, then decision); evidence sufficiency, risk flags, and coherence are deterministic

## 1. Headline metrics

| Config | claim_status acc | claim_status macro-F1 | issue_type acc | issue_type macro-F1 | evidence_met acc | risk Jaccard |
|---|---|---|---|---|---|---|
| A_current | 0.60 | 0.52 | 0.25 | 0.24 | 0.65 | 0.62 |
| B_calibrated | 0.65 | 0.61 | 0.30 | 0.27 | 0.70 | 0.62 |
| C_consistency | 0.75 | 0.66 | 0.45 | 0.44 | 0.90 | 0.62 |
| D_consistency_cap | 0.65 | 0.61 | 0.30 | 0.27 | 0.90 | 0.62 |

Recommended configuration: **C_consistency** (highest claim_status macro-F1, tie broken by overall column accuracy).

## 2. Config A_current

Per-column accuracy (graded columns):

| column | accuracy |
|---|---|
| evidence_standard_met | 0.65 |
| issue_type | 0.25 |
| object_part | 0.35 |
| claim_status | 0.60 |
| supporting_image_ids | 0.60 |
| valid_image | 0.85 |
| severity | 0.20 |

claim_status confusion (rows = gold, cols = predicted):

| gold \ pred | contradicted | not_enough_information | supported |
|---|---|---|---|
| contradicted | 1 | 3 | 1 |
| not_enough_information | 0 | 3 | 0 |
| supported | 0 | 4 | 8 |

issue_type confusion (rows = gold, cols = predicted):

| gold \ pred | broken_part | crack | crushed_packaging | dent | glass_shatter | none | scratch | stain | torn_packaging | unknown | water_damage |
|---|---|---|---|---|---|---|---|---|---|---|---|
| broken_part | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 3 | 0 |
| crack | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 1 | 0 |
| crushed_packaging | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dent | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| glass_shatter | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| none | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 | 0 |
| scratch | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| stain | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| torn_packaging | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| unknown | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 2 | 0 |
| water_damage | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |

risk_flags: mean Jaccard 0.62, exact-set match 0.45

## 2. Config B_calibrated

Per-column accuracy (graded columns):

| column | accuracy |
|---|---|
| evidence_standard_met | 0.70 |
| issue_type | 0.30 |
| object_part | 0.35 |
| claim_status | 0.65 |
| supporting_image_ids | 0.65 |
| valid_image | 0.80 |
| severity | 0.30 |

claim_status confusion (rows = gold, cols = predicted):

| gold \ pred | contradicted | not_enough_information | supported |
|---|---|---|---|
| contradicted | 2 | 2 | 1 |
| not_enough_information | 0 | 3 | 0 |
| supported | 0 | 4 | 8 |

issue_type confusion (rows = gold, cols = predicted):

| gold \ pred | broken_part | crack | crushed_packaging | dent | glass_shatter | none | scratch | stain | torn_packaging | unknown | water_damage |
|---|---|---|---|---|---|---|---|---|---|---|---|
| broken_part | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 2 | 0 |
| crack | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 1 | 0 |
| crushed_packaging | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dent | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| glass_shatter | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| none | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 | 0 |
| scratch | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| stain | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| torn_packaging | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| unknown | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 2 | 0 |
| water_damage | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |

risk_flags: mean Jaccard 0.62, exact-set match 0.45

## 2. Config C_consistency

Per-column accuracy (graded columns):

| column | accuracy |
|---|---|
| evidence_standard_met | 0.90 |
| issue_type | 0.45 |
| object_part | 0.65 |
| claim_status | 0.75 |
| supporting_image_ids | 0.85 |
| valid_image | 0.80 |
| severity | 0.30 |

claim_status confusion (rows = gold, cols = predicted):

| gold \ pred | contradicted | not_enough_information | supported |
|---|---|---|---|
| contradicted | 2 | 1 | 2 |
| not_enough_information | 0 | 2 | 1 |
| supported | 0 | 1 | 11 |

issue_type confusion (rows = gold, cols = predicted):

| gold \ pred | broken_part | crack | crushed_packaging | dent | glass_shatter | none | scratch | stain | torn_packaging | unknown | water_damage |
|---|---|---|---|---|---|---|---|---|---|---|---|
| broken_part | 1 | 0 | 0 | 0 | 1 | 0 | 2 | 0 | 0 | 0 | 0 |
| crack | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 1 | 0 |
| crushed_packaging | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dent | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| glass_shatter | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| none | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 | 0 |
| scratch | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| stain | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| torn_packaging | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| unknown | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 2 | 0 |
| water_damage | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |

risk_flags: mean Jaccard 0.62, exact-set match 0.45

## 2. Config D_consistency_cap

Per-column accuracy (graded columns):

| column | accuracy |
|---|---|
| evidence_standard_met | 0.90 |
| issue_type | 0.30 |
| object_part | 0.65 |
| claim_status | 0.65 |
| supporting_image_ids | 0.65 |
| valid_image | 0.80 |
| severity | 0.30 |

claim_status confusion (rows = gold, cols = predicted):

| gold \ pred | contradicted | not_enough_information | supported |
|---|---|---|---|
| contradicted | 2 | 2 | 1 |
| not_enough_information | 0 | 3 | 0 |
| supported | 0 | 4 | 8 |

issue_type confusion (rows = gold, cols = predicted):

| gold \ pred | broken_part | crack | crushed_packaging | dent | glass_shatter | none | scratch | stain | torn_packaging | unknown | water_damage |
|---|---|---|---|---|---|---|---|---|---|---|---|
| broken_part | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 2 | 0 |
| crack | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 1 | 0 |
| crushed_packaging | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dent | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| glass_shatter | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| none | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 | 0 |
| scratch | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| stain | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| torn_packaging | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| unknown | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 2 | 0 |
| water_damage | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |

risk_flags: mean Jaccard 0.62, exact-set match 0.45

## 3. Operational analysis

Measured on the sample run (live = real API calls, cached = served from disk):

| Config | total calls | live | cached | input tok | output tok | images | live latency (s) | billable cost (USD) |
|---|---|---|---|---|---|---|---|---|
| A_current | 40 | 0 | 0 | 45203 | 8069 | 29 | 141.12 | 0.03373 |
| B_calibrated | 40 | 0 | 0 | 52941 | 8045 | 29 | 138.08 | 0.03599 |
| C_consistency | 40 | 0 | 0 | 52913 | 8031 | 29 | 16.08 | 0.00500 |
| D_consistency_cap | 40 | 0 | 0 | 52913 | 8031 | 29 | 0 | 0.00000 |


Pricing assumption: gemini-2.5-flash at {'input': 0.3, 'output': 2.5} USD per 1M tokens.

### Rate limits, batching, caching, retry

- Throttle: client-side spacing at 6 requests/minute to stay under the Gemini free-tier RPM limit.
- Batching: all of a claim's images go in a single vision request; the decision call is text-only over the extracted findings, so images are sent once per claim.
- Caching: every model response is cached on disk keyed by a hash of the full request, so re-runs and the second configuration cost no new calls; the shared vision calls are reused across configs A and B.
- Retry: up to 5 attempts with exponential backoff and jitter on 429 and 5xx responses.
- Resumability: because results are cached, an interrupted run resumes for free.
