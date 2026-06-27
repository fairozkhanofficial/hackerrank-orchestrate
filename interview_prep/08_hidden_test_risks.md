# K. Hidden-Test Risks

These are the failure modes most likely to cost points on the unseen test set,
with honest confidence levels and the mitigation that exists today.

| # | Risk | Why it's likely | Mitigation in place | Confidence it bites |
|---|---|---|---|---|
| 1 | **Identity-fraud false approval** (different-object image sets → `supported`) | Dataset deliberately added the revised `case_002`; Config C false-approves it | Still flagged `claim_mismatch` + `manual_review_required` (just not forced to NEI) | High that the category is tested; Medium that it costs raw accuracy |
| 2 | **Over-/under-calibrated severity** | severity acc only 0.30; model anchors to "high" | `_b` calibration prompt; enum-snapping keeps it valid | High |
| 3 | **issue_type over-escalation** (crack→glass_shatter, stain→water_damage) | issue acc 0.45 | `_b` conservative-classification prompt | Medium-High |
| 4 | **Weak object_part on packages/laptops** | part acc 0.65; non-car parts are harder | none beyond the prompt | Medium |
| 5 | **Contradiction recall** (catches ~2 of 5) | contradicted recall 0.40 across all configs | decision prompt severity-exaggeration rule | Medium-High |
| 6 | **Novel/multilingual injection** slips the regex | regex is pattern-based | model firewall + in-image-text flag backstop | Low-Medium |
| 7 | **Vision hallucination** (invents damage → false approval, e.g. `case_008`) | small but present | valid_image + risk flags partially catch | Medium |
| 8 | **Quota/runtime** (88 fresh calls, per-key daily caps) | free tier is small | checkpoint + resume + multi-key failover | High operationally |
| 9 | **Provider key-retirement flaw** (RPM conflated with daily) | latent bug | resume makes it safe, just slow | Low for correctness, Medium for completion speed |
| 10 | **Small-sample overfit** (n=20) | every metric is ~1–2 claims | limited tuning to one measured pass per change | Medium |

## The three to bring up first, unprompted
1. **Config C's identity-fraud false approval** — measured, understood, chosen
   deliberately; D proved the alternative (a hard cap) re-breaks legitimate
   claims. (See [04](04_configs_and_selection.md), [07](07_cross_image_consistency.md).)
2. **Calibration of severity/issue** — the weakest remaining columns; the honest
   ceiling of a 2-call prompt approach without fine-tuning.
3. **n=20** — all results are directional; we resisted overfitting.

## Risks we structurally avoid
- **Schema violations**: impossible — `schemas.py` snaps every enum and assemble
  fixes the 14-column order, so a malformed model response can't produce an
  out-of-spec row.
- **Self-contradictory rows**: assemble's coherence rules prevent e.g. "NEI with
  a concrete severity".
- **Silently dropped claims**: a guaranteed fallback row is emitted on any error;
  quota failures are retried, not lost.
- **Label leakage**: ingest reads only the 4 input columns, never gold.
