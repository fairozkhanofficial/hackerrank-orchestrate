# Interview Preparation Package — Multi-Modal Evidence Review

This folder is a complete preparation kit for defending the HackerRank Orchestrate
submission in an AI-judge / technical interview. It is documentation only — it
changes no project code and reproduces no predictions.

## Reading order

| File | Covers | When to read |
|---|---|---|
| [11_architecture_one_pager.md](11_architecture_one_pager.md) | One-page summary (N) | Read first / last-minute |
| [10_cheat_sheet_30min.md](10_cheat_sheet_30min.md) | 30-minute cram sheet (M) | Right before the interview |
| [01_system_architecture.md](01_system_architecture.md) | System architecture (A) | Foundation |
| [02_pipeline_walkthrough.md](02_pipeline_walkthrough.md) | End-to-end walkthrough + why each stage (B, D) | Foundation |
| [03_file_reference.md](03_file_reference.md) | Every major file and its purpose (C) | Reference |
| [04_configs_and_selection.md](04_configs_and_selection.md) | Config A/B/C/D, why C, sample results (E, F, G) | Core story |
| [05_infrastructure.md](05_infrastructure.md) | Caching, checkpoint, resume, failover, multikey (H) | Core story |
| [06_security_injection.md](06_security_injection.md) | Prompt-injection protection (I) | Deep dive |
| [07_cross_image_consistency.md](07_cross_image_consistency.md) | Cross-image consistency logic (J) | Deep dive |
| [08_hidden_test_risks.md](08_hidden_test_risks.md) | Hidden-test risks (K) | Deep dive |
| [09_top100_questions.md](09_top100_questions.md) | Top 100 judge Q&A, short + detailed (L) | Practice |
| [12_submission_defense.md](12_submission_defense.md) | Strengths / weaknesses / tradeoffs / future (O) | Defense |

## The 30-second pitch

> A two-call, vision-first pipeline that adjudicates damage claims. Call 1 (a
> vision model) extracts structured findings from the submitted images — the
> images are the primary source of truth. A deterministic sufficiency layer then
> decides whether the evidence is good enough to judge. Call 2 (text-only) makes
> the claim decision over those findings. Three more deterministic layers —
> risk, coherence/assemble — never call the model, so the verdict, risk flags,
> and output schema stay reproducible and auditable. Everything runs behind a
> caching, checkpointing, resumable, multi-key-failover provider so a free-tier
> quota wall never loses work. We compared four configurations on the labelled
> sample and shipped **Config C** (claim_status accuracy 0.75, macro-F1 0.66).

## Honest framing for the interview

Three things to own proactively, because a good judge will find them:

1. **Config C's one real weakness** — it can false-approve a genuinely
   mismatched-object image set (the planted `case_002` identity-fraud case). We
   measured this, understood why, and chose it deliberately. See
   [04](04_configs_and_selection.md) and [12](12_submission_defense.md).
2. **Small sample (n=20).** All metrics are directional, not statistically
   robust. We avoided overfitting by limiting tuning to one measured pass.
3. **A known provider flaw** — the multi-key failover permanently retires a key
   on any quota 429, conflating recoverable per-minute limits with terminal
   daily limits. See [05](05_infrastructure.md) and [08](08_hidden_test_risks.md).
