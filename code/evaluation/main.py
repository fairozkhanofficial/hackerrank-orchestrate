"""Evaluate the pipeline on sample_claims.csv and generate evaluation_report.md.

Only the four input columns are fed to the pipeline; the gold columns are used
only for scoring. Two configurations are compared:

  A_current     baseline prompts
  B_calibrated  calibrated vision + decision prompts (severity + contradiction)

Run:  python code/evaluation/main.py [--limit N]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import ingest
import orchestrator
import output_io
import preflight
from providers.registry import get_model_provider
from utils.cache import Cache, CachingProvider
from utils.metrics import MetricsCollector
from utils.resume import ResultStore
from evaluation import metrics as M

CONFIGS = [
    # name, vision_variant, decision_variant, consistency_blocks, inconsistent_cap
    ("A_current", "", "", True, False),
    ("B_calibrated", "_b", "_b", True, False),
    ("C_consistency", "_b", "_b", False, False),
    ("D_consistency_cap", "_b", "_b", False, True),
]


def run_config(name, vision_variant, decision_variant, consistency_blocks, inconsistent_cap,
               records, settings, limit):
    provider = CachingProvider(get_model_provider(settings), Cache(settings.cache_dir))
    store = ResultStore(settings.results_dir / f"sample_{name}")
    metrics_ckpt = settings.results_dir / f"sample_{name}" / "metrics_state.json"
    out_path = config.CODE_DIR / "evaluation" / f"sample_predictions_{name}.csv"
    collector = MetricsCollector().load(metrics_ckpt)   # resume cumulative metrics

    def checkpoint(rows, coll):
        output_io.write_output_rows(out_path, rows)      # save prediction snapshot
        coll.save(metrics_ckpt)                          # save metrics state

    start = time.time()
    rows = orchestrator.process_dataset(
        records, provider, provider, collector,
        vision_variant=vision_variant, decision_variant=decision_variant,
        limit=limit, log=lambda m: print(f"  {name}: {m}"),
        store=store, model_tag=f"{settings.vision_provider}:{config.GEMINI_MODEL}",
        on_claim=checkpoint, consistency_blocks=consistency_blocks,
        inconsistent_cap=inconsistent_cap)
    elapsed = time.time() - start
    output_io.write_output_rows(out_path, rows)           # final snapshot (idempotent)
    op = collector.summary()
    op["wall_clock_s"] = round(elapsed, 2)
    op["live_calls"] = getattr(provider, "live_calls", 0)
    op["cache_hits"] = getattr(provider, "cache_hits", 0)
    return rows, op


def _conf_table(conf):
    labels = conf["labels"]
    lines = ["| gold \\ pred | " + " | ".join(labels) + " |",
             "|" + "---|" * (len(labels) + 1)]
    for g in labels:
        row = [str(conf["matrix"][g][p]) for p in labels]
        lines.append(f"| {g} | " + " | ".join(row) + " |")
    return "\n".join(lines)


def _extrapolate(op, n_sample, n_test):
    if op["live_calls"] == 0 or n_sample == 0:
        return None
    factor = n_test / n_sample
    in_per = op["input_tokens_total"] / max(1, op["total_calls"])
    out_per = op["output_tokens_total"] / max(1, op["total_calls"])
    calls = round(op["total_calls"] * factor)
    return {
        "test_claims": n_test,
        "estimated_calls": calls,
        "estimated_input_tokens": round(in_per * calls),
        "estimated_output_tokens": round(out_per * calls),
        "estimated_cost_usd": round(op["estimated_cost_usd_full_rerun"] * factor, 4),
    }


def build_report(results, n_sample, n_test, recommended):
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    lines = []
    lines.append("# Evaluation Report: Multi-Modal Evidence Review\n")
    lines.append(f"- Generated: {now}")
    lines.append(f"- Model: {config.GEMINI_MODEL} (vision + decision)")
    lines.append(f"- Sample claims evaluated: {n_sample}")
    lines.append("- Architecture: balanced 2-call (vision extraction, then decision); "
                 "evidence sufficiency, risk flags, and coherence are deterministic\n")

    lines.append("## 1. Headline metrics\n")
    lines.append("| Config | claim_status acc | claim_status macro-F1 | issue_type acc | "
                 "issue_type macro-F1 | evidence_met acc | risk Jaccard |")
    lines.append("|---|---|---|---|---|---|---|")
    for name, ev, _ in results:
        lines.append(f"| {name} | {ev['claim_status_accuracy']:.2f} | "
                     f"{ev['claim_status_macro_f1']:.2f} | {ev['issue_type_accuracy']:.2f} | "
                     f"{ev['issue_type_macro_f1']:.2f} | {ev['evidence_standard_met_accuracy']:.2f} | "
                     f"{ev['risk_flag_overlap']['mean_jaccard']:.2f} |")
    lines.append(f"\nRecommended configuration: **{recommended}** "
                 "(highest claim_status macro-F1, tie broken by overall column accuracy).\n")

    for name, ev, op in results:
        lines.append(f"## 2. Config {name}\n")
        lines.append("Per-column accuracy (graded columns):\n")
        lines.append("| column | accuracy |")
        lines.append("|---|---|")
        for col, acc in ev["per_column_accuracy"].items():
            lines.append(f"| {col} | {acc:.2f} |")
        lines.append("")
        lines.append("claim_status confusion (rows = gold, cols = predicted):\n")
        lines.append(_conf_table(ev["claim_status_confusion"]))
        lines.append("")
        lines.append("issue_type confusion (rows = gold, cols = predicted):\n")
        lines.append(_conf_table(ev["issue_type_confusion"]))
        lines.append("")
        lines.append(f"risk_flags: mean Jaccard {ev['risk_flag_overlap']['mean_jaccard']:.2f}, "
                     f"exact-set match {ev['risk_flag_overlap']['exact_match']:.2f}\n")

    lines.append("## 3. Operational analysis\n")
    lines.append("Measured on the sample run (live = real API calls, cached = served from disk):\n")
    lines.append("| Config | total calls | live | cached | input tok | output tok | images | "
                 "live latency (s) | billable cost (USD) |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for name, _, op in results:
        lines.append(f"| {name} | {op['total_calls']} | {op['live_calls']} | {op['cache_hits']} | "
                     f"{op['input_tokens_total']} | {op['output_tokens_total']} | "
                     f"{op['images_processed']} | {op['live_latency_s']} | "
                     f"{op['estimated_cost_usd_billable']:.5f} |")
    lines.append("")
    rec_op = next(op for name, _, op in results if name == recommended)
    extra = _extrapolate(rec_op, n_sample, n_test)
    if extra:
        lines.append(f"Extrapolated to the full test set ({n_test} claims), recommended config:\n")
        lines.append(f"- Estimated model calls: ~{extra['estimated_calls']} "
                     "(2 per claim: one vision, one decision)")
        lines.append(f"- Estimated input tokens: ~{extra['estimated_input_tokens']:,}")
        lines.append(f"- Estimated output tokens: ~{extra['estimated_output_tokens']:,}")
        lines.append(f"- Estimated cost: ~${extra['estimated_cost_usd']:.4f}")
    lines.append("")
    lines.append("Pricing assumption: gemini-2.5-flash at "
                 f"{config.PRICING.get(config.GEMINI_MODEL)} USD per 1M tokens.")
    lines.append("")
    lines.append("### Rate limits, batching, caching, retry\n")
    lines.append(f"- Throttle: client-side spacing at {config.REQUESTS_PER_MINUTE} requests/minute "
                 "to stay under the Gemini free-tier RPM limit.")
    lines.append("- Batching: all of a claim's images go in a single vision request; the decision "
                 "call is text-only over the extracted findings, so images are sent once per claim.")
    lines.append("- Caching: every model response is cached on disk keyed by a hash of the full "
                 "request, so re-runs and the second configuration cost no new calls; the shared "
                 "vision calls are reused across configs A and B.")
    lines.append(f"- Retry: up to {config.MAX_RETRIES} attempts with exponential backoff and jitter "
                 "on 429 and 5xx responses.")
    lines.append("- Resumability: because results are cached, an interrupted run resumes for free.\n")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    settings = config.load_settings(args.data_root)
    preflight.validate_or_exit(settings, require_api_keys=settings.vision_provider != "mock")
    records = ingest.build_claim_records(settings.sample_csv, settings)
    gold = output_io.read_rows(settings.sample_csv)
    if args.limit:
        records, gold = records[:args.limit], gold[:args.limit]
    n_sample = len(records)
    n_test = len(output_io.read_rows(settings.claims_csv))

    results = []
    for name, vv, dv, cb, cap in CONFIGS:
        print(f"running config {name} ...")
        pred, op = run_config(name, vv, dv, cb, cap, records, settings, args.limit)
        ev = M.evaluate(pred, gold)
        results.append((name, ev, op))

    recommended = max(
        results,
        key=lambda r: (r[1]["claim_status_macro_f1"],
                       sum(r[1]["per_column_accuracy"].values())))[0]

    report = build_report(results, n_sample, n_test, recommended)
    report_path = config.CODE_DIR / "evaluation" / "evaluation_report.md"
    report_path.write_text(report, encoding="utf-8")

    metrics_json = {name: {"metrics": ev, "operational": op} for name, ev, op in results}
    (config.CODE_DIR / "evaluation" / "metrics.json").write_text(
        json.dumps(metrics_json, indent=2), encoding="utf-8")

    print(f"\nwrote {report_path}")
    print("recommended config:", recommended)
    for name, ev, op in results:
        print(f"  {name}: claim_status acc={ev['claim_status_accuracy']:.2f} "
              f"f1={ev['claim_status_macro_f1']:.2f} | issue acc={ev['issue_type_accuracy']:.2f} "
              f"| live_calls={op['live_calls']}")


if __name__ == "__main__":
    main()
