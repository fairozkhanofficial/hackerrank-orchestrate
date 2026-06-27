"""Entry point: run the pipeline over a claims CSV and write output.csv.

Examples:
  python code/main.py                          # claims.csv -> output.csv (Gemini)
  python code/main.py --variant _b --consistency-soft   # Config C (selected)
  python code/main.py --dataset sample         # run on the sample inputs
  python code/main.py --vision-provider mock --decision-provider mock
  python code/main.py --limit 5 --no-cache
"""

from __future__ import annotations

import argparse
import json
import time

import config
import ingest
import orchestrator
import output_io
import preflight
from providers.registry import get_model_provider
from utils.cache import Cache, CachingProvider
from utils.metrics import MetricsCollector
from utils.resume import ResultStore


def build_provider(settings, use_cache=True, model=None):
    """One shared backend for both roles, wrapped once in the response cache."""
    provider = get_model_provider(settings, model=model)
    if use_cache:
        provider = CachingProvider(provider, Cache(settings.cache_dir))
    return provider


def parse_args():
    parser = argparse.ArgumentParser(description="Multi-modal evidence review pipeline")
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--dataset", choices=["claims", "sample"], default="claims")
    parser.add_argument("--out", default=None)
    parser.add_argument("--vision-provider", default=None)
    parser.add_argument("--decision-provider", default=None)
    parser.add_argument("--variant", default="", help="prompt variant suffix, e.g. _b")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--no-resume", action="store_true", help="ignore the claim result store")
    parser.add_argument("--consistency-soft", action="store_true",
                        help="Config C: cross-image inconsistency does not hard-block evidence "
                             "sufficiency (stays a risk and decision signal)")
    parser.add_argument("--model", default=None,
                        help="Gemini model override (e.g. gemini-2.5-flash-lite)")
    return parser.parse_args()


def main():
    args = parse_args()
    settings = config.load_settings(args.data_root, args.out)
    if args.vision_provider:
        settings.vision_provider = args.vision_provider
    if args.decision_provider:
        settings.decision_provider = args.decision_provider

    using_mock = settings.vision_provider == "mock"
    preflight.validate_or_exit(settings, require_api_keys=not using_mock)

    csv_path = settings.claims_csv if args.dataset == "claims" else settings.sample_csv
    records = ingest.build_claim_records(csv_path, settings)
    provider = build_provider(settings, use_cache=not args.no_cache, model=args.model)
    store = None if args.no_resume else ResultStore(settings.results_dir / args.dataset)

    metrics = MetricsCollector()
    checkpoint = None
    if store is not None:
        metrics_ckpt = settings.results_dir / args.dataset / "metrics_state.json"
        metrics.load(metrics_ckpt)

        def checkpoint(rows, coll):
            output_io.write_output_rows(settings.output_csv, rows)
            coll.save(metrics_ckpt)

    consistency_blocks = not args.consistency_soft
    # The result-store tag includes the consistency mode so a soft (Config C) run
    # and a hard run on the same dataset never resume each other's rows.
    mode = "csoft" if args.consistency_soft else "chard"
    model_tag = f"{settings.vision_provider}:{config.GEMINI_MODEL}:{mode}"

    start = time.time()
    rows = orchestrator.process_dataset(
        records, provider, provider, metrics,
        vision_variant=args.variant, decision_variant=args.variant,
        limit=args.limit, log=print, store=store, model_tag=model_tag,
        on_claim=checkpoint, consistency_blocks=consistency_blocks)
    elapsed = time.time() - start

    output_io.write_output_rows(settings.output_csv, rows)
    summary = metrics.summary()
    summary["wall_clock_s"] = round(elapsed, 2)
    summary["live_provider_calls"] = getattr(provider, "live_calls", 0)
    summary["cache_hits"] = getattr(provider, "cache_hits", 0)
    inner = getattr(provider, "inner", None)
    if inner is not None and hasattr(inner, "pool"):
        summary["key_pool"] = inner.pool.status()
        summary["key_switches"] = inner.key_switches
        if hasattr(inner.pool, "_strikes"):
            summary["key_strikes"] = {f"...{k[-4:]}": v
                                       for k, v in inner.pool._strikes.items()}

    print(f"\nwrote {len(rows)} rows to {settings.output_csv}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
