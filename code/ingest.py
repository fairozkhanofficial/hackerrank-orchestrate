"""Load and join the four dataset files into ClaimRecord objects.

Only the four input columns are read from the claim CSVs. The gold answer
columns present in sample_claims.csv are deliberately ignored here, so the
pipeline can never see a label. Evaluation reads those columns separately.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

import config


@dataclass
class ImageRef:
    image_id: str
    rel_path: str
    abs_path: Path
    exists: bool


@dataclass
class UserHistory:
    user_id: str
    past_claim_count: int = 0
    accept_claim: int = 0
    manual_review_claim: int = 0
    rejected_claim: int = 0
    last_90_days_claim_count: int = 0
    history_flags: list = field(default_factory=list)
    history_summary: str = ""

    @property
    def reject_ratio(self) -> float:
        return self.rejected_claim / self.past_claim_count if self.past_claim_count else 0.0


@dataclass
class EvidenceRule:
    requirement_id: str
    claim_object: str
    applies_to: str
    minimum_image_evidence: str


@dataclass
class ClaimRecord:
    row_index: int
    user_id: str
    image_paths_raw: str
    user_claim: str
    claim_object: str
    images: list = field(default_factory=list)
    history: object = None
    evidence_rules: list = field(default_factory=list)

    @property
    def image_ids(self) -> list:
        return [img.image_id for img in self.images]

    @property
    def existing_images(self) -> list:
        return [img for img in self.images if img.exists]


def _read_csv(path: Path) -> list:
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _to_int(value, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def parse_image_paths(raw: str, data_root: Path) -> list:
    """Split the semicolon-separated image_paths field into resolved ImageRefs."""
    refs = []
    for rel in (part.strip() for part in (raw or "").split(";")):
        if not rel:
            continue
        abs_path = (data_root / rel).resolve()
        refs.append(ImageRef(
            image_id=Path(rel).stem,
            rel_path=rel,
            abs_path=abs_path,
            exists=abs_path.is_file(),
        ))
    return refs


def load_user_history(path: Path) -> dict:
    history = {}
    for row in _read_csv(path):
        flags = [f.strip() for f in (row.get("history_flags") or "").split(";") if f.strip()]
        history[row["user_id"]] = UserHistory(
            user_id=row["user_id"],
            past_claim_count=_to_int(row.get("past_claim_count")),
            accept_claim=_to_int(row.get("accept_claim")),
            manual_review_claim=_to_int(row.get("manual_review_claim")),
            rejected_claim=_to_int(row.get("rejected_claim")),
            last_90_days_claim_count=_to_int(row.get("last_90_days_claim_count")),
            history_flags=flags,
            history_summary=(row.get("history_summary") or "").strip(),
        )
    return history


def load_evidence_requirements(path: Path) -> list:
    return [
        EvidenceRule(
            requirement_id=row["requirement_id"],
            claim_object=row["claim_object"],
            applies_to=row["applies_to"],
            minimum_image_evidence=row["minimum_image_evidence"],
        )
        for row in _read_csv(path)
    ]


def applicable_rules(rules: list, claim_object: str) -> list:
    """Rules for this object plus the all-object rules."""
    return [rule for rule in rules if rule.claim_object in (claim_object, "all")]


def build_claim_records(csv_path: Path, settings: config.Settings) -> list:
    """Build ClaimRecords from a claims CSV, joined to history and evidence rules."""
    history = load_user_history(settings.history_csv)
    rules = load_evidence_requirements(settings.requirements_csv)
    records = []
    for index, row in enumerate(_read_csv(csv_path)):
        user_id = (row.get("user_id") or "").strip()
        claim_object = (row.get("claim_object") or "").strip().lower()
        records.append(ClaimRecord(
            row_index=index,
            user_id=user_id,
            image_paths_raw=(row.get("image_paths") or "").strip(),
            user_claim=(row.get("user_claim") or "").strip(),
            claim_object=claim_object,
            images=parse_image_paths(row.get("image_paths"), settings.data_root),
            history=history.get(user_id),
            evidence_rules=applicable_rules(rules, claim_object),
        ))
    return records


if __name__ == "__main__":
    settings = config.load_settings()
    for name, path in (("claims", settings.claims_csv), ("sample", settings.sample_csv)):
        records = build_claim_records(path, settings)
        total_images = sum(len(r.images) for r in records)
        missing = sum(1 for r in records for img in r.images if not img.exists)
        no_history = [r.user_id for r in records if r.history is None]
        objects = {}
        for record in records:
            objects[record.claim_object] = objects.get(record.claim_object, 0) + 1
        print(f"{name}: {len(records)} records | {total_images} images | "
              f"missing {missing} | no-history {len(no_history)} | objects {objects}")
