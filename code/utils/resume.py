"""Claim-level result store for resume.

A completed claim's output row is saved keyed by a hash of its inputs plus the
prompt variant and model. On restart, completed claims are loaded and skipped, so
they are never reprocessed. The key is content-based, so an updated claim (for
example a revised sample row) gets a new key and is recomputed automatically,
while unchanged claims are reused.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _hash(*parts):
    digest = hashlib.sha256()
    for part in parts:
        digest.update(repr(part).encode("utf-8"))
    return digest.hexdigest()[:40]


class ResultStore:
    def __init__(self, directory):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)

    def key(self, record, vision_variant, decision_variant, model):
        return _hash(record.user_id, record.image_paths_raw, record.user_claim,
                     record.claim_object, vision_variant, decision_variant, model)

    def get(self, key):
        path = self.dir / f"{key}.json"
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
        return None

    def put(self, key, row_dict):
        (self.dir / f"{key}.json").write_text(
            json.dumps(row_dict, ensure_ascii=False), encoding="utf-8")
