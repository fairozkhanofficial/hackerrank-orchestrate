# N. One-Page Architecture Summary

## Multi-Modal Evidence Review — at a glance

**Goal:** adjudicate damage claims (car/laptop/package). Images are the primary
source of truth; conversation is evidence; history/rules are context. Output: one
14-column CSV row per claim.

```
INGEST(det) ─► VISION(model) ─► SUFFICIENCY(det) ─► DECISION(model) ─► RISK(det) ─► ASSEMBLE(det) ─► output.csv
 inputs+        images →          good enough         verdict over       fraud/abuse    coherence +
 history+       ImageFacts +      to judge?            findings+rules+    flags +        valid_image +
 rules          consistency       (NEI rule)          history            review route   14-col schema
```

**Two model calls only** (vision, decision). **Three deterministic stages**
(sufficiency, risk, assemble) → reproducible, auditable, free, and a guard against
out-of-spec/contradictory rows.

| Layer | Type | Responsibility |
|---|---|---|
| Vision | model (multimodal) | per-image findings + cross-image consistency |
| Sufficiency | deterministic | is evidence good enough? → met/NEI |
| Decision | model (text) | claim_status, issue, part, severity, mismatch |
| Risk | deterministic | risk_flags + manual_review_required |
| Assemble | deterministic | coherence, valid_image, enum-snap, column order |

**Provider stack:** `CachingProvider → MultiKeyGeminiProvider → GeminiProvider (REST, Gemini 2.5 Flash)`.
Gives: response cache (free hits), unbounded multi-key failover, per-key throttle.
**Plus** a claim-level result store + per-claim checkpoint = **fully resumable,
idempotent runs** — a free-tier quota wall never loses or re-bills completed work.

## Output schema (fixed order)
`user_id, image_paths, user_claim, claim_object, evidence_standard_met,
evidence_standard_met_reason, risk_flags, issue_type, object_part, claim_status,
claim_status_justification, supporting_image_ids, valid_image, severity`

## Configurations (controlled experiment, one variable each)
| | prompts | consistency | claim_status acc | note |
|---|---|---|---|---|
| A | base | hard-block | 0.60 | baseline |
| B | `_b` | hard-block | 0.65 | calibrated |
| **C** | `_b` | **signal only** | **0.75** | **shipped** |
| D | `_b` | signal + "never supported" cap | 0.65 | ≡ B |

**Why C:** the consistency hard-block (B) forced 6 legitimate multi-view claims to
false NEI (signal is ~75% false-positive). C demotes consistency to a risk +
decision signal, recovering them (false NEI 6→2; best on 6/9 metrics). **Cost:**
false-approves the planted fraud `case_002` (still flagged for review); D proved a
cap can't fix that without re-breaking the 6 legit claims.

## Defenses
- **Injection:** system-prompt firewall + decision reinforcement + trilingual
  regex → flag + manual review (never obeyed).
- **Authenticity:** tampering/screenshot detection → `valid_image`, risk flags.
- **Fraud:** cross-image consistency + `claim_mismatch` + history risk → review.
- **Schema safety:** enum-snapping + coherence rules → no out-of-spec rows.

## Run it
- Selected config: `python code/main.py --variant _b --consistency-soft`
- Evaluate all configs: `python code/evaluation/main.py`
- Offline (no keys): add `--vision-provider mock --decision-provider mock`

## Headline honest caveats
n=20 (directional metrics) · C can false-approve genuine different-object sets
(flagged for review) · failover retires keys on recoverable per-minute limits
(resume makes it safe).
