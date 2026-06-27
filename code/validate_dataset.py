"""Pre-flight dataset validation.

Checks structural invariants across sample_claims.csv and claims.csv before any
model calls are made: image paths resolve, image_ids extract cleanly, every
claim_object is in range, every user joins to history, and at least one evidence
rule applies. Prints a report and exits non-zero if any hard failure is found, so
it can gate a run in CI or before a paid pipeline run.
"""

from __future__ import annotations

import re
import sys
from collections import Counter

import config
import ingest

IMAGE_ID_PATTERN = re.compile(r"^img_\d+$")


def validate_file(name, csv_path, settings):
    records = ingest.build_claim_records(csv_path, settings)

    missing_paths = []          # (row, image_id, rel_path)
    id_anomalies = []           # (row, image_id, reason)
    bad_objects = []            # (row, user_id, claim_object)
    empty_fields = []           # (row, user_id, field)
    history_misses = []         # (row, user_id)
    no_rules = []               # (row, user_id, claim_object)
    dup_image_ids = []          # (row, user_id, [ids])
    no_images = []              # (row, user_id)

    for record in records:
        row = record.row_index

        if record.claim_object not in config.CLAIM_OBJECTS:
            bad_objects.append((row, record.user_id, record.claim_object))

        for field_name in ("user_id", "user_claim", "image_paths_raw"):
            if not getattr(record, field_name):
                empty_fields.append((row, record.user_id, field_name))

        if not record.images:
            no_images.append((row, record.user_id))

        for img in record.images:
            if not img.exists:
                missing_paths.append((row, img.image_id, img.rel_path))
            if "." in img.image_id or not IMAGE_ID_PATTERN.match(img.image_id):
                id_anomalies.append((row, img.image_id, img.rel_path))

        ids = record.image_ids
        duplicates = [i for i, c in Counter(ids).items() if c > 1]
        if duplicates:
            dup_image_ids.append((row, record.user_id, duplicates))

        if record.history is None:
            history_misses.append((row, record.user_id))

        if not record.evidence_rules:
            no_rules.append((row, record.user_id, record.claim_object))

    # Duplicate claim records: identical across all four input fields.
    keys = [(r.user_id, r.image_paths_raw, r.user_claim, r.claim_object) for r in records]
    dup_records = [k for k, c in Counter(keys).items() if c > 1]

    total_images = sum(len(r.images) for r in records)
    repeated_users = sorted(u for u, c in Counter(r.user_id for r in records).items() if c > 1)

    print(f"\n===== {name} ({len(records)} rows, {total_images} image refs) =====")
    _line("1. image paths resolve", not missing_paths, f"{len(missing_paths)} missing", missing_paths)
    _line("2. image_id extraction (img_N, no extension)", not id_anomalies,
          f"{len(id_anomalies)} anomalies", id_anomalies)
    _line("3. claim_object in {car,laptop,package}", not bad_objects,
          f"{len(bad_objects)} invalid", bad_objects)
    _line("4. user_id joins to user_history.csv", not history_misses,
          f"{len(history_misses)} unmatched", history_misses)
    _line("5. at least one evidence rule applies", not no_rules,
          f"{len(no_rules)} with no rule", no_rules)

    print("  reports:")
    _line("   invalid rows (empty required fields / no images)",
          not (empty_fields or no_images),
          f"{len(empty_fields) + len(no_images)} found", empty_fields + no_images)
    _line("   unexpected values (claim_object out of range)", not bad_objects,
          f"{len(bad_objects)} found", bad_objects)
    _line("   duplicate image IDs within a claim", not dup_image_ids,
          f"{len(dup_image_ids)} claims", dup_image_ids)
    _line("   duplicate claim records (all 4 inputs identical)", not dup_records,
          f"{len(dup_records)} found", dup_records)
    print(f"   note: users appearing in more than one row (expected, distinct claims): {repeated_users or 'none'}")

    failures = (len(missing_paths) + len(id_anomalies) + len(bad_objects)
                + len(history_misses) + len(no_rules) + len(empty_fields)
                + len(no_images) + len(dup_image_ids) + len(dup_records))
    return failures


def _line(label, ok, detail, examples):
    status = "PASS" if ok else "FAIL"
    suffix = "" if ok else f" -> {detail}: {examples[:5]}"
    print(f"  [{status}] {label}{suffix}")


def main():
    settings = config.load_settings()

    rules = ingest.load_evidence_requirements(settings.requirements_csv)
    history = ingest.load_user_history(settings.history_csv)
    print(f"evidence_requirements.csv: {len(rules)} rules loaded")
    print(f"user_history.csv: {len(history)} users loaded")
    objects_covered = sorted({r.claim_object for r in rules})
    print(f"evidence rule objects: {objects_covered}")

    failures = 0
    failures += validate_file("sample_claims.csv", settings.sample_csv, settings)
    failures += validate_file("claims.csv", settings.claims_csv, settings)

    print(f"\nTOTAL hard failures across both files: {failures}")
    if failures:
        print("Validation FAILED.")
        return 1
    print("Validation PASSED. Dataset is ready for the pipeline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
