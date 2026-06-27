# M. 30-Minute Interview Cheat Sheet

Read top to bottom once. Memorise the **bold** lines.

## Minute 0–5 · The pitch + numbers
- **Vision-first, two-call pipeline + deterministic glue.** Images = primary truth.
- **Stages:** Ingest → Vision (model) → Sufficiency (det.) → Decision (model) → Risk (det.) → Assemble (det.) → 14-col CSV.
- **Only 2 of 5 stages call the model.** The rest are reproducible, auditable, free.
- **Shipped Config C: claim_status acc 0.75, macro-F1 0.66** (best of A/B/C/D).
- A 0.60 / B 0.65 / **C 0.75** / D 0.65. C also best: issue 0.45, evidence 0.90, object_part 0.65.

## Minute 5–10 · Why each stage
- **Vision** — pixels → typed facts; image can't be overridden by user words.
- **Sufficiency** (det.) — "good enough to judge?"; deterministic NEI boundary.
- **Decision** (text-only) — verdict over findings+rules+history; images sent once.
- **Risk** (det.) — fraud/abuse flags + `manual_review_required`; policy = rules.
- **Assemble** (det.) — coherence rules, `valid_image`, enum-snap, 14-col order.

## Minute 10–15 · The config story (the heart of it)
- A→B: **prompt calibration** (conservative severity/issue, fewer false claim_mismatch).
- B→C: **one flag** — stop letting cross-image inconsistency *hard-block* sufficiency.
- C→D: add "**inconsistent → never supported**" cap → **D collapses to B**.
- **Why C:** the consistency signal is ~75% false-positive on multi-image claims; the hard-block (B) turned **6 legitimate claims into false NEI**. C recovers them (false NEI 6→2).
- **C's cost:** false-approves the planted identity-fraud `case_002` (still flagged for review). D proved a cap can't fix it without re-breaking the 6 legit claims → **a rule is only as good as its signal.**

## Minute 15–20 · Infrastructure (say "never loses work")
- **Cache** (call-level, content-hash) + **Result store** (claim-level, skip completed).
- **Checkpoint** after every claim (CSV + metrics). **Multi-key failover** (unbounded keys, rotate on 429). **Quota-aware:** quota failures = incomplete = retried, never persisted half-done.
- **Idempotent + resumable**: re-run skips done claims, re-calls nothing.
- **Known flaw (own it):** failover retires a key on *any* RESOURCE_EXHAUSTED — conflates per-minute (recoverable) with daily (terminal). Not the cause of the 19/44 stop (that was genuine daily exhaustion).

## Minute 20–25 · Security + consistency
- **Injection: 3 layers** — system-prompt firewall (text-in-evidence ≠ instruction), decision reinforcement, **trilingual regex** (English/Hinglish/Spanish) → flag + manual review.
- In-image "approve" stickers → flagged (`in_image_instruction_present`), never obeyed.
- **Consistency** = same-object check (colour/type/features/damage location/identity); runs as a **risk + decision signal** in C (still catches fraud for human review), just doesn't hard-block.

## Minute 25–30 · Tradeoffs + own the weaknesses
- **Biggest tradeoff:** recall vs fraud-safety on multi-image claims → chose recall (C), review-flag as net.
- **Weakest columns:** severity 0.30, contradiction recall 0.40 — prompt-only ceiling.
- **n=20** → all numbers directional; we limited tuning to one measured change, stopped at D (no Config E).
- **If grader punishes false approvals → ship B/D** (one-flag switch).
- **Future:** reliable same-object signal, fix failover RPM/daily split, more data for calibration.

## Three things to say UNPROMPTED
1. "Config C false-approves the planted fraud case — we measured it, chose it deliberately, and D proved the alternative re-breaks legit claims."
2. "n=20, so the numbers are directional; we avoided overfitting."
3. "There's a real failover bug — retires keys on recoverable per-minute limits; resume makes it safe but slow."

## If you blank, say this
> "Images are primary truth, so I separate perception (one vision call) from
> reasoning (one text call) and wrap them in deterministic, auditable layers for
> sufficiency, risk, and coherence. I picked the shipped config with a controlled
> four-way experiment, and the whole thing is resumable so a free-tier quota wall
> never loses work."
