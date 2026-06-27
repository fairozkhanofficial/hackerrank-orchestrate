# A. System Architecture

## Problem in one sentence
Given a damage claim (a user message, a claimed object — car / laptop / package —
one or more submitted images, the user's claim history, and the category's
evidence requirements), produce a structured 14-column verdict where **the image
is the primary source of truth**, the conversation is supporting evidence, and
history/rules are context only.

## Design philosophy: a "balanced" two-call pipeline with deterministic glue
The model is used **only where judgement over pixels or language is required**.
Everything that can be made rule-based is made rule-based, so it is reproducible,
auditable, and free.

```
                 ┌───────────────────────────────────────────────────────┐
   inputs ─────► │  INGEST (deterministic)                                │
   claims.csv    │  load claim + images + history + evidence rules         │
   images/       └───────────────────────────────────────────────────────┘
                              │
                              ▼
                 ┌───────────────────────────────────────────────────────┐
                 │  STAGE 1 · VISION  (MODEL CALL · multimodal)           │
                 │  images → per-image structured findings (ImageFacts)   │
                 │  + a claim-level cross_image_consistency judgement      │
                 └───────────────────────────────────────────────────────┘
                              │ findings
                              ▼
                 ┌───────────────────────────────────────────────────────┐
                 │  STAGE 2 · SUFFICIENCY  (DETERMINISTIC · no call)      │
                 │  is the evidence good enough to judge? → met/reason     │
                 └───────────────────────────────────────────────────────┘
                              │ findings + sufficiency
                              ▼
                 ┌───────────────────────────────────────────────────────┐
                 │  STAGE 3 · DECISION  (MODEL CALL · text only)          │
                 │  findings + rules + history → claim_status/issue/…      │
                 └───────────────────────────────────────────────────────┘
                              │ decision
                              ▼
                 ┌───────────────────────────────────────────────────────┐
                 │  STAGE 4 · RISK  (DETERMINISTIC · no call)            │
                 │  history, tampering, injection, wrong-object → flags    │
                 └───────────────────────────────────────────────────────┘
                              │ decision + risk
                              ▼
                 ┌───────────────────────────────────────────────────────┐
                 │  STAGE 5 · ASSEMBLE  (DETERMINISTIC · no call)        │
                 │  coherence rules + valid_image → 14-column OutputRow    │
                 └───────────────────────────────────────────────────────┘
                              │
                              ▼  output.csv (one row per claim)
```

## Why two model calls, not one
- **Separation of perception and reasoning.** Call 1 answers "what is physically
  in these images?" Call 2 answers "given those facts and the rules, what is the
  verdict?" Mixing them in one prompt makes the model conflate what it *sees*
  with what it *concludes*, and makes failures hard to localise.
- **Images are sent once.** All of a claim's images go in the single vision call;
  the decision call is text-only over the extracted findings. This minimises the
  expensive (image) tokens.
- **Independent caching and debugging.** A vision result can be cached and reused
  by multiple decision configurations (that is exactly how Config C reused B's
  vision outputs at zero cost).

## Why deterministic layers around the model
- **Reproducibility.** Sufficiency, risk, and assemble produce identical output
  for identical findings — no temperature, no drift. Graders can re-run and get
  the same file.
- **Auditability.** Every NEI, every risk flag, every field-coherence decision is
  a rule you can point to, not a model whim.
- **Cost.** Three of the five stages cost nothing.
- **Safety net.** Assemble enforces field coherence (e.g., an unsupported claim
  can't carry a concrete severity), so the model can't emit a self-contradictory
  row.

## The provider layer (cross-cutting)
Both model calls go through one shared provider stack:
`CachingProvider → MultiKeyGeminiProvider → per-key GeminiProvider (REST)`.
This gives response caching, unbounded-key failover, per-key throttling, and —
combined with the claim-level result store — checkpointing and free resume.
See [05_infrastructure.md](05_infrastructure.md).

## Output contract (14 columns, fixed order)
`user_id, image_paths, user_claim, claim_object, evidence_standard_met,
evidence_standard_met_reason, risk_flags, issue_type, object_part, claim_status,
claim_status_justification, supporting_image_ids, valid_image, severity`

All enum fields are snapped to allowed vocabularies defensively in `schemas.py`,
so a malformed model response can never produce an out-of-spec row.
