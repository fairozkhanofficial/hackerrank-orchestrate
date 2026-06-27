"""Run accounting: model calls, tokens, images, latency, and estimated cost.

Cost is charged only for live (non-cached) calls, since cache hits cost nothing.
Token totals are reported both overall and billable so the operational analysis
in evaluation_report.md is honest about what a fresh run would actually cost.
"""

from __future__ import annotations

import json
from pathlib import Path

import config


class MetricsCollector:
    def __init__(self):
        self.records = []

    def save(self, path):
        """Persist the accounting state so metrics survive an interrupted run."""
        Path(path).write_text(json.dumps({"records": self.records}, ensure_ascii=False),
                              encoding="utf-8")

    def load(self, path):
        """Restore accounting state from a checkpoint, if present (cumulative)."""
        p = Path(path)
        if p.is_file():
            self.records = json.loads(p.read_text(encoding="utf-8")).get("records", [])
        return self

    def add(self, stage, usage):
        if usage is None:
            return
        self.records.append({
            "stage": stage,
            "model": usage.model,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "images": usage.image_count,
            "latency_s": usage.latency_s,
            "cached": usage.cached,
        })

    def _cost(self, records):
        total = 0.0
        for record in records:
            price = config.PRICING.get(record["model"])
            if not price:
                continue
            total += record["input_tokens"] / 1e6 * price["input"]
            total += record["output_tokens"] / 1e6 * price["output"]
        return total

    def summary(self):
        live = [r for r in self.records if not r["cached"]]
        by_stage = {}
        for record in self.records:
            by_stage[record["stage"]] = by_stage.get(record["stage"], 0) + 1
        return {
            "total_calls": len(self.records),
            "live_calls": len(live),
            "cached_calls": len(self.records) - len(live),
            "calls_by_stage": by_stage,
            "input_tokens_total": sum(r["input_tokens"] for r in self.records),
            "output_tokens_total": sum(r["output_tokens"] for r in self.records),
            "input_tokens_billable": sum(r["input_tokens"] for r in live),
            "output_tokens_billable": sum(r["output_tokens"] for r in live),
            "images_processed": sum(r["images"] for r in self.records),
            "live_latency_s": round(sum(r["latency_s"] for r in live), 2),
            "estimated_cost_usd_billable": round(self._cost(live), 6),
            "estimated_cost_usd_full_rerun": round(self._cost(self.records), 6),
        }
