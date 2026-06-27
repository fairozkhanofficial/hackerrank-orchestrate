"""Per-claim orchestration: the six stages wired together with metrics, a
guaranteed fallback, quota-aware failure handling, and claim-level resume.

process_claim returns (row_dict, complete). complete is False only when the run
ran out of API quota for that claim, so the claim is not persisted and a later
run reprocesses it; every other outcome (success or a non-quota error) is
persisted and never reprocessed.
"""

from __future__ import annotations

import assemble
import decide
import imaging
import risk
import schemas
import sufficiency
import vision
from providers.base import QuotaExhausted


def fallback_row(record, reason):
    """A safe, schema-valid row used when a claim cannot be processed."""
    return schemas.OutputRow(
        user_id=record.user_id,
        image_paths=record.image_paths_raw,
        user_claim=record.user_claim,
        claim_object=record.claim_object,
        evidence_standard_met=False,
        evidence_standard_met_reason=reason,
        risk_flags=["manual_review_required"],
        issue_type="unknown",
        object_part="unknown",
        claim_status="not_enough_information",
        claim_status_justification=reason,
        supporting_image_ids=[],
        valid_image=False,
        severity="unknown",
    )


def process_claim(record, vision_provider, decision_provider, metrics,
                  vision_variant="", decision_variant="", consistency_blocks=True,
                  inconsistent_cap=False):
    try:
        prepared = imaging.prepare_images(record.images)
        facts, consistency, vusage = vision.run_vision(
            vision_provider, record, prepared, variant=vision_variant)
        metrics.add("vision", vusage)

        suf = sufficiency.evaluate(record, facts, consistency, consistency_blocks=consistency_blocks)
        injection = risk.detect_injection(record.user_claim)
        decision, dusage = decide.run_decision(
            decision_provider, record, facts, suf[0], suf[1],
            variant=decision_variant, injection_detected=injection,
            cross_image_consistency=consistency)
        metrics.add("decision", dusage)

        risk_flags = risk.compute(record, facts, decision, suf[0], consistency)
        row = assemble.build_output_row(record, facts, suf, decision, risk_flags,
                                        cross_image_consistency=consistency,
                                        inconsistent_cap=inconsistent_cap)
        return row.to_csv_dict(), True
    except QuotaExhausted as exc:
        # Not completed: leave it for a later run to retry from cache.
        return fallback_row(record, f"quota exhausted: {exc}"[:200]).to_csv_dict(), False
    except Exception as exc:
        return fallback_row(record, f"processing error: {type(exc).__name__}: {exc}"[:200]).to_csv_dict(), True


def process_dataset(records, vision_provider, decision_provider, metrics,
                    vision_variant="", decision_variant="", limit=None, log=None,
                    store=None, model_tag="", on_claim=None, consistency_blocks=True,
                    inconsistent_cap=False):
    items = records[:limit] if limit else records
    rows = []
    resumed = 0
    for index, record in enumerate(items, 1):
        key = store.key(record, vision_variant, decision_variant, model_tag) if store else None
        cached = store.get(key) if store is not None else None
        if cached is not None:
            rows.append(cached)
            resumed += 1
            if log:
                log(f"[{index}/{len(items)}] {record.user_id} {record.claim_object} -> resumed")
        else:
            row, complete = process_claim(
                record, vision_provider, decision_provider, metrics,
                vision_variant=vision_variant, decision_variant=decision_variant,
                consistency_blocks=consistency_blocks, inconsistent_cap=inconsistent_cap)
            if store is not None and complete:
                store.put(key, row)
            rows.append(row)
            if log:
                log(f"[{index}/{len(items)}] {record.user_id} {record.claim_object} "
                    f"-> {row['claim_status']} ({row['issue_type']}/{row['severity']})"
                    + ("" if complete else " [incomplete: quota]"))
        # Persist progress after every claim (prediction snapshot + metrics state).
        if on_claim is not None:
            on_claim(rows, metrics)
    if log and resumed:
        log(f"resumed {resumed} completed claim(s) from the result store")
    return rows
