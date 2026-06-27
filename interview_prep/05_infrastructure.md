# H. Caching, Checkpointing, Resume, Failover, Multi-Key Architecture

These five mechanisms exist for one reason: the model runs on a **free-tier
quota** that can vanish mid-run, and a hackathon submission must never lose
completed work or re-spend on it.

## Provider stack
```
CachingProvider  →  MultiKeyGeminiProvider  →  per-key GeminiProvider (REST)
   (response cache)     (key rotation)            (one HTTP client per key)
```
One shared instance serves both the vision and decision roles, so key state is
tracked globally.

## 1. Response cache (`utils/cache.py`)
- Every model response is cached on disk, keyed by
  `hash(stage, model, system_prompt, user_text, image_signature, schema, temperature)`.
- A cache hit returns the stored result with `usage.cached=True` → **no tokens
  billed**, counted separately as a cache hit.
- Because the key is the full request content, **identical calls never re-hit the
  API**, and changing a prompt automatically invalidates only the affected
  entries.
- This is why Config C reused **all** of B's vision calls and B's *consistent*-
  claim decisions for free, paying only for the 8 *inconsistent*-claim decisions
  whose prompt changed.

## 2. Claim-level result store / resume (`utils/resume.py`)
- After a claim **completes**, its full output row is written to
  `results/<dataset_or_config>/<hash>.json`, keyed by
  `hash(user_id, image_paths, user_claim, claim_object, vision_variant,
  decision_variant, model_tag)`.
- On any later run, a claim whose key is already in the store is **loaded and
  skipped** — never reprocessed, never re-billed.
- The key includes the `model_tag` (and, in `main.py`, the consistency mode
  `csoft`/`chard`) so a soft run and a hard run never resume each other's rows,
  and mock results never poison a real run.
- Content-keyed: if an input claim is revised, its hash changes and it
  recomputes automatically.

## 3. Checkpointing (`on_claim` hook + `MetricsCollector.save/load`)
- `process_dataset` fires an `on_claim(rows, metrics)` callback **after every
  claim** (resumed or freshly processed).
- The callback rewrites the predictions CSV snapshot and saves the metrics state
  (`metrics_state.json`).
- So an interruption at claim *k* loses nothing: the *k* completed claims are in
  the result store, the CSV reflects them, and the cumulative metrics survive.
- Verified offline: stop at 5, resume to 10 → exactly 5 resumed (not rerun),
  metrics cumulative.

## 4. Multi-key failover (`providers/gemini_multikey.py`)
- `load_api_keys()` reads `config/api_keys.txt` (one per line, blanks/`#`
  ignored) plus any env key, de-duplicated → an **unbounded** key list, no code
  change to add keys.
- `KeyPool` holds the keys + an `exhausted` set; `current()` returns the first
  active key.
- `_with_failover(call)` runs the call on the current key; on `QuotaExhausted`
  it marks that key exhausted, switches to the next active key, and retries the
  **same** request. When all keys are exhausted it raises `QuotaExhausted`, the
  orchestrator returns a schema-valid fallback row marked **incomplete** (not
  persisted), and the run is resumable later.

## 5. Quota-aware completeness (`orchestrator.py`)
- `process_claim` returns `(row, complete)`. `complete=False` **only** on quota
  exhaustion → the claim is not stored and a later run retries it from cache.
- Any other outcome (success, or a non-quota error → fallback) is `complete=True`
  → persisted and never reprocessed.

## How they combine: a fully resumable, idempotent run
1. Completed claims are skipped (result store).
2. Repeated identical model calls are free (response cache).
3. Progress is durable after every claim (checkpoint).
4. A dead key is replaced instantly (failover).
5. A fully-exhausted run stops safely and continues for free later (quota-aware
   completeness + cache).

## Known flaw to disclose (important)
The failover **permanently retires a key on *any* `RESOURCE_EXHAUSTED` 429**,
conflating a recoverable **per-minute** limit with a terminal **daily** limit; it
never inspects `retryDelay`, and the throttle (`_last_call`) is per-key so
switching keys resets the rate window and can burst past the intended 6 RPM. In
the real `output.csv` run this was not the primary cause (the keys were genuinely
out of *daily* budget), but it is a real latent bug. Fix direction (not
implemented): parse the `RESOURCE_EXHAUSTED` subtype / `retryDelay`, only
permanently retire on daily limits, and back off-and-retry the same key on
per-minute limits; share one global throttle across keys; round-robin instead of
always-first to balance per-key daily usage.
