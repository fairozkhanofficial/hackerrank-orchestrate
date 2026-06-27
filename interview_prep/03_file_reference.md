# C. Every Major File and Its Purpose

## Pipeline core
| File | Purpose |
|---|---|
| `code/config.py` | Central config: model id, allowed vocabularies (issue types, object parts, claim statuses, risk flags, severities, clarity, consistency), path resolution, pricing, rate/retry constants, `load_api_keys()`, `load_prompt()`, `load_settings()`. |
| `code/schemas.py` | Typed dataclasses (`ImageFacts`, `ImageObservation`, `Decision`, `OutputRow`) with **defensive** `from_model_dict()` constructors and `snap_enum()` that coerces unknown model output to safe allowed values. `OutputRow.to_csv_dict()` serialises in exact 14-column order. |
| `code/ingest.py` | Loads claims/sample/history/evidence CSVs into `ClaimRecord`s. Reads only the 4 input columns (never gold). Parses `image_paths` (semicolon-split), resolves & existence-checks images. |
| `code/imaging.py` | `prepare_images()` downscales longest edge to 1280 px (Pillow), re-encodes JPEG q85, base64-encodes; records orig/sent bytes & dimensions. Falls back to original bytes if Pillow is absent. |
| `code/vision.py` | Stage 1. Builds the per-image response schema, calls `provider.vision_json()` with batched labelled images, re-keys results by `image_id`, returns `(facts, cross_image_consistency, usage)`. Single-image claims are forced `consistent`. |
| `code/sufficiency.py` | Stage 2 (deterministic). `evaluate(record, facts, consistency, consistency_blocks=True)` → `(met, reason, ids)`. The `consistency_blocks` flag is the A/B vs C switch. |
| `code/decide.py` | Stage 3. Builds the decision schema + prompt (findings, rules, sufficiency, consistency, history, optional injection note), calls `provider.text_json()`, returns `(Decision, usage)`. |
| `code/risk.py` | Stage 4 (deterministic). `detect_injection()` (trilingual regex) + `compute()` → `risk_flags`, with `manual_review_required` escalation. |
| `code/assemble.py` | Stage 5 (deterministic). `build_output_row(... cross_image_consistency, inconsistent_cap)` applies coherence rules, computes `valid_image`, returns `OutputRow`. `inconsistent_cap` is the Config D switch. |
| `code/orchestrator.py` | `process_claim()` wires stages + guaranteed fallback + quota-aware completeness; `process_dataset()` loops, resumes from the store, fires the per-claim checkpoint (`on_claim`). |
| `code/output_io.py` | `write_output_rows()` (QUOTE_ALL CSV, accepts OutputRow or dict) and `read_rows()`. |
| `code/main.py` | Entry point → `output.csv`. CLI: `--dataset`, `--variant`, `--consistency-soft` (Config C), `--out`, `--limit`, `--no-cache`, `--no-resume`, mock providers. Runs preflight, builds the shared cached multi-key provider, checkpoints per claim. |
| `code/preflight.py` | Startup validation: dataset files, images dir, and (unless mock) a non-empty `config/api_keys.txt`. Fails fast with a clear message. |
| `code/validate_dataset.py` | Standalone dataset sanity check. |

## Providers
| File | Purpose |
|---|---|
| `code/providers/base.py` | `LLMProvider` interface, `Usage`, `ProviderResult`, `QuotaExhausted`, robust `extract_json()`. |
| `code/providers/gemini.py` | Single-key Gemini 2.5 Flash over the REST API. Structured output via `responseSchema`, `thinkingBudget=0`, per-key throttle, retry honouring server `retryDelay`; in `failover` mode a quota 429 raises `QuotaExhausted` immediately. |
| `code/providers/gemini_multikey.py` | `KeyPool` + `MultiKeyGeminiProvider`: rotates across unbounded keys, marks a key exhausted on `QuotaExhausted`, retries on the next active key, propagates when all are exhausted. |
| `code/providers/mock.py` | Deterministic offline provider (no network), used for development and mock runs. |
| `code/providers/registry.py` | Builds one shared multi-key provider for both roles (or mock when no keys). |

## Utilities
| File | Purpose |
|---|---|
| `code/utils/cache.py` | `Cache` (disk, content-hash keyed) + `CachingProvider` wrapper; serves cache hits with `usage.cached=True` (no billing), counts live vs cached. |
| `code/utils/resume.py` | `ResultStore`: claim-level results keyed by `hash(inputs + variants + model_tag)`; `get()`/`put()`/`key()`. Enables skip-completed resume. |
| `code/utils/metrics.py` | `MetricsCollector`: per-call accounting (tokens, images, latency, cost), `save()`/`load()` for checkpointable cumulative metrics, `summary()`. |

## Prompts (`code/prompts/`)
| File | Purpose |
|---|---|
| `vision_system.txt` / `vision_system_b.txt` | Vision system prompts. `_b` adds conservative severity/issue calibration. Both contain the injection firewall and the cross-image-consistency instructions. |
| `decision_system.txt` / `decision_system_b.txt` | Decision system prompts. `_b` suppresses false `claim_mismatch` and adds the inconsistency rule. |
| `vision_user.txt` / `decision_user.txt` | User templates with placeholders (claim, findings, rules, sufficiency, consistency, history). |

## Evaluation (`code/evaluation/`)
| File | Purpose |
|---|---|
| `main.py` | Runs all configs (A/B/C/D) on the labelled sample, compares to gold, writes `evaluation_report.md` + per-config prediction CSVs + `metrics.json`. |
| `metrics.py` | Accuracy, macro-F1, per-column accuracy, confusion matrices, risk-flag Jaccard. |
| `evaluation_report.md` | Generated report: headline metrics, per-config detail, operational analysis. |

## Top-level
`AGENTS.md`, `problem_statement.md`, `README.md`, `code/README.md`,
`code/requirements.txt` (requests, Pillow), `.gitignore` (secrets + runtime
artifacts), `dataset/` (claims, sample, history, evidence, images).
