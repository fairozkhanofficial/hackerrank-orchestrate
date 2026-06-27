# J. Cross-Image Consistency Logic

## What it is
When a claim has multiple images, an attacker could submit photos of **different
objects** (e.g. a close-up of one car and a full view of a *different* car) to
manufacture evidence. To catch this, the **vision stage** returns a claim-level
`cross_image_consistency` judgement:

- `consistent` — the images plausibly show one and the same object.
- `inconsistent` — two or more images appear to show different objects.
- `unknown` — not enough shared context to tell.

The model is instructed to judge this from **colour, object type, distinctive
features, where the damage sits, and overall object identity**. A single-image
claim is forced to `consistent` (it cannot conflict with itself).

## How it flows through the pipeline
1. **Vision** emits the value (`vision.py`).
2. **Sufficiency** — *config-dependent*:
   - A/B (`consistency_blocks=True`): `inconsistent` **hard-blocks** evidence
     sufficiency → not-met → assemble forces `not_enough_information`.
   - C (`consistency_blocks=False`): it does **not** block; the decision is free
     to judge, but is told the value.
3. **Decision** always receives the value as context; the `_b` decision prompt
   says to prefer `not_enough_information` when inconsistent unless a single image
   alone fully supports the claim.
4. **Risk** always raises `claim_mismatch` + `manual_review_required` on
   `inconsistent`, regardless of config.

So in **every** config, an inconsistent set is flagged and routed to human
review. The configs differ only in whether it also *deterministically forces*
the verdict to NEI.

## The key empirical finding (this is the crux of the whole project)
The cross-image consistency signal, as produced by the vision model, is **noisy
— roughly a 75% false-positive rate on multi-image claims.** On the sample it
fired `inconsistent` on 8 multi-image claims, but only ~1–2 were genuinely
different objects (`case_002`, arguably `case_018`); the other ~6
(`case_003/005/007/010/016/020`) were *legitimate* multi-view shots of the same
object that the model mislabelled.

Consequences:
- **In A/B** the hard-block turned those ~6 legitimate claims into false NEI —
  the single largest source of lost accuracy (and it cascaded issue/part/severity
  to `unknown`).
- **In C** removing the block recovered those ~6, but `case_002` (genuine fraud)
  then got false-approved because the only deterministic guard was gone.
- **In D** the "inconsistent → never supported" cap fixed `case_002` but
  re-broke the ~6 legitimate claims (it can't tell them apart), so D collapsed to
  B.

## Why this matters for the design narrative
It's a clean illustration of a real ML-systems lesson: **a deterministic safety
rule is only as good as the signal it gates on.** The consistency *idea* is
sound (and still runs as a risk flag in C), but the *signal* is too unreliable to
drive a hard verdict change without also penalising legitimate users. The honest
conclusion is that the correct fix is a *better signal* (a more reliable
same-object check at the vision level), not a cleverer rule on top of a noisy
one.

## What we shipped
Config C: keep the consistency check as a **risk + decision signal** (so genuine
fraud is still flagged for human review and the decision is informed), but do not
let it **hard-block** evidence and punish legitimate multi-view claims. We
accepted the measured cost (one planted fraud case can slip to "supported"
instead of "NEI") in exchange for recovering six legitimate claims and large
gains across issue/part/evidence.
