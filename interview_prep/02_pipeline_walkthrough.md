# B. End-to-End Pipeline Walkthrough  &  D. Why Each Stage Exists

## End-to-end, one claim at a time

1. **Ingest** (`ingest.py`) reads four input columns only — `user_id`,
   `image_paths`, `user_claim`, `claim_object` — and never the gold columns, so
   the pipeline cannot "see" labels. It resolves image paths against the dataset
   root, joins the user's history (`user_history.csv`) and the category's
   evidence rules (`evidence_requirements.csv`).

2. **Imaging** (`imaging.py`) downscales each image's longest edge to 1280 px
   (Pillow) and re-encodes to JPEG q85, then base64-encodes it. A 46.9 MP test
   image becomes ~176 KB. This keeps image tokens and request size sane.

3. **Stage 1 — Vision** (`vision.py`, MODEL CALL): all of the claim's prepared
   images go in one multimodal request. Each image is preceded by an
   `[image_id: …]` label so findings tie back to the right image. The model
   returns, per image: `object_present`, `object_matches_claim`,
   `claimed_part_visible`, `clarity`, `observations[]` (issue_type / object_part /
   severity), `tampering_signs`, `screenshot_signs`, `in_image_text_present`,
   `in_image_instruction_present`; and one **claim-level**
   `cross_image_consistency` (consistent / inconsistent / unknown). Responses are
   re-keyed by `image_id` so reordering or dropouts are handled.

4. **Stage 2 — Sufficiency** (`sufficiency.py`, DETERMINISTIC): evidence is
   "met" when at least one image has `object_present` AND `claimed_part_visible`
   AND `clarity == clear`. In Config A/B an `inconsistent` set hard-blocks to
   not-met; in Config C it does not (see [07](07_cross_image_consistency.md)).
   Returns `(met, reason, assessable_ids)`.

5. **Stage 3 — Decision** (`decide.py`, MODEL CALL, text only): the extracted
   findings (JSON), the evidence rules, the sufficiency result, the cross-image
   consistency value, and a history summary are formatted into a prompt. The
   model returns `claim_status`, `issue_type`, `object_part`, `severity`,
   `supporting_image_ids[]`, `claim_mismatch`, `justification`.

6. **Stage 4 — Risk** (`risk.py`, DETERMINISTIC): computes `risk_flags` from
   history (reject ratio, prior flags), clarity issues, tampering/screenshot,
   in-image instructions, conversation injection (trilingual regex), wrong-object
   / wrong-part, and decision `claim_mismatch`. Escalates
   `manual_review_required` on the dangerous combinations.

7. **Stage 5 — Assemble** (`assemble.py`, DETERMINISTIC): applies coherence
   rules (not-met → NEI; supported-but-unknown-issue → NEI; NEI clears
   issue/severity/supporting; issue=none → severity=none), computes `valid_image`
   from the findings, and returns the 14-column `OutputRow`.

8. **Orchestration** (`orchestrator.py`) wires the five stages, adds a guaranteed
   schema-valid fallback row on any error, marks a claim *incomplete* only on
   quota exhaustion (so it is retried later, never persisted half-done), and
   fires the per-claim checkpoint.

## D. Why each stage exists

### Vision stage — "what is physically there?"
The contest's core rule is **images are the primary truth**. The only way to honour
that is a dedicated perception step that converts pixels into typed facts before
any judgement happens. Keeping it separate means: (a) the decision can't override
what the image shows with what the user *says*; (b) the same perception is reused
across decision variants; (c) authenticity signals (tampering, screenshot,
in-image text) are captured at the source.

### Sufficiency stage — "is the evidence good enough to judge?"
Deliberately deterministic and model-free so the "we can't tell" boundary is a
fixed, auditable rule rather than a model mood. It implements the contest's
`not_enough_information` semantics: if no image clearly shows the claimed part,
we must not pretend to adjudicate. It also feeds the decision (`standard_met`) so
the model is told, up front, whether the evidence even supports a verdict.

### Decision stage — "given the facts and rules, what's the verdict?"
This is the genuine reasoning step: reconcile the visual findings with the user's
claim and the category rules to produce `claim_status` and the damage
descriptors. It is text-only because all the visual information it needs has
already been distilled into findings — sending images again would waste tokens
and re-introduce perception/decision entanglement.

### Risk stage — "what should a human double-check?"
Fraud and abuse signals (history of rejections, tampering, screenshots,
prompt-injection attempts, wrong object/part, claim mismatch) are
**policy**, not perception or reasoning, so they belong in deterministic rules
that fire consistently and can be audited. This stage also routes the dangerous
cases to `manual_review_required`.

### Assemble stage — "make the row coherent and in-spec"
A model can emit locally-sensible but globally-inconsistent fields (e.g.
"not enough information" yet a concrete severity). Assemble enforces a small set
of coherence invariants, computes `valid_image` from authenticity findings, snaps
everything to the allowed vocabularies, and guarantees the exact 14-column order.
It is the last line of defence for schema and logical validity.
