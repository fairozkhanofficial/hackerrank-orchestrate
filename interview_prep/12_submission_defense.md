# O. Submission Defense Document

A candid strengths / weaknesses / tradeoffs / future-work statement. The goal is
to demonstrate that we understand our own system better than the judge does.

## Strengths

1. **Principled architecture.** Perception, sufficiency, reasoning, risk, and
   coherence are five isolated stages; only two call the model. This yields
   reproducibility (temp 0 + deterministic glue), auditability (every NEI/flag is
   a rule), low cost (3/5 stages free), and a clean surface for experimentation.

2. **Images as primary truth, enforced.** A dedicated vision stage extracts typed
   facts before any judgement, and the decision prompt ranks visual findings above
   user claims — so a false narrative can't silently flip a verdict.

3. **Evidence-driven config selection.** We ran a controlled four-way experiment
   (A/B/C/D), changing one variable at a time, and shipped the winner (C, 0.75
   claim_status) by an objective, reproducible rule (top macro-F1).

4. **Production-shaped reliability.** Response cache + claim-level result store +
   per-claim checkpoint + multi-key failover = idempotent, resumable runs. A
   free-tier quota wall costs time, not work. Startup validation fails fast;
   secrets are gitignored; a guaranteed fallback row means no claim is ever
   dropped.

5. **Schema and coherence guarantees.** Enum-snapping plus assemble's coherence
   rules make an out-of-spec or self-contradictory row structurally impossible.

6. **Security taken seriously.** Three-layer prompt-injection defense and
   authenticity (tampering/screenshot) detection, all routing uncertain or
   adversarial cases to human review.

7. **Intellectual honesty.** We caught and corrected a quota-contaminated
   comparison, proved D≡B from the data, and stopped tuning before overfitting.

## Weaknesses

1. **Identity-fraud false approval (Config C).** A genuinely different-object
   image set (the planted `case_002`) can be marked `supported` instead of NEI.
   It is still flagged `claim_mismatch` + `manual_review_required`, but the
   automated verdict is wrong. *Measured, understood, chosen deliberately.*

2. **Severity calibration (0.30) and contradiction recall (0.40).** The honest
   ceiling of a prompt-only approach without fine-tuning or labelled calibration
   data; both columns remain weak.

3. **Noisy consistency signal.** ~75% false-positive on multi-image claims — the
   root cause behind both B's false NEI and C's fraud slip. The *idea* is sound;
   the *signal* is unreliable.

4. **Provider quota handling.** Failover permanently retires a key on any
   RESOURCE_EXHAUSTED, conflating recoverable per-minute with terminal daily
   limits; the throttle is per-key so key-switching can burst. Safe (resume) but
   suboptimal — it slows completion and the real `output.csv` run stopped at
   19/44 on daily exhaustion.

5. **Small evaluation sample (n=20).** All metrics are directional; absolute
   numbers aren't statistically robust.

6. **object_part on non-cars (0.65).** Package/laptop part localisation is weaker
   than car parts.

## Tradeoffs (and why we chose as we did)

| Tradeoff | Options | Choice & rationale |
|---|---|---|
| Recall vs fraud-safety on multi-image | hard-block (B) vs signal-only (C) | **C** — recover 6 legit claims; keep fraud flagged for review; plain-accuracy scoring favours C. Switchable via one flag if grading punishes false approvals. |
| Model vs deterministic policy | model decides everything vs rules | **Rules** for sufficiency/risk/coherence — reproducible, auditable, free, schema-safe. |
| One call vs two | cheaper single prompt vs separation | **Two** — separation of perception/reasoning, images sent once, cacheable/reusable vision. |
| Prompt calibration vs fine-tuning | tune prompts vs train | **Prompts** — no data/time/repro budget for fine-tuning; keeps auditability. |
| Tune more vs stop | chase the sample vs stop at D | **Stop** — n=20 overfit risk; next gain needs a better signal, not another rule. |

## Future improvements (prioritised)

1. **Reliable same-object signal** (replace the noisy consistency flag): an
   explicit "are these the same physical object? cite shared identifiers" vision
   step, or cross-image embedding similarity. Then a hard rule on a *trustworthy*
   signal gives both fraud-safety and recall — resolving the C-vs-B tension.
2. **Fix the failover quota logic:** parse `RESOURCE_EXHAUSTED` subtype /
   `retryDelay`; back-off-and-retry the same key on per-minute limits; retire only
   on daily; share one global throttle; round-robin keys to balance daily usage.
3. **Severity/issue calibration:** gather human-labelled severity anchors; add a
   small calibration head or few-shot exemplars; consider light fine-tuning.
4. **Contradiction recall:** strengthen the severity-exaggeration and
   "claimed-but-absent" detection in the decision prompt/logic.
5. **Scale-out:** swap disk cache/store for Redis/object storage; parallelise
   across keys/workers; add monitoring and a real human-review queue (the risk
   flags already feed it).
6. **Larger labelled eval:** make deltas significant; per-category breakdowns;
   paired significance tests for config choice.

## The closing statement
> This is a reproducible, auditable, vision-first adjudication pipeline. We used
> the model only where judgement over pixels or language is required, made
> everything else deterministic, chose the shipped configuration with a clean
> controlled experiment, and engineered the run to survive a free-tier quota wall
> without losing work. We can point to exactly where it is strong, exactly where
> it is weak, why we made each tradeoff, and what we would build next — and the
> single most important next step (a reliable same-object signal) is already
> identified.
