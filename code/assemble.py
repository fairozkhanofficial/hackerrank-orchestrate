"""Assemble the final OutputRow from all stage results.

Applies a small set of general coherence rules (not per-row answers) so the
fields never contradict each other, computes valid_image from the vision
findings, and keeps every value inside the allowed vocabularies.
"""

from __future__ import annotations

import schemas


def _valid_image(facts) -> bool:
    """The image set is usable for automated review: at least one genuine, clear,
    relevant photo of the claimed object."""
    for fact in facts:
        if (fact.object_present and fact.object_matches_claim and fact.clarity == "clear"
                and not fact.tampering_signs and not fact.screenshot_signs):
            return True
    return False


def _filter_supporting(ids, record) -> list:
    valid = set(record.image_ids)
    return [image_id for image_id in ids if image_id in valid]


def build_output_row(record, facts, sufficiency, decision, risk_flags,
                     cross_image_consistency="unknown", inconsistent_cap=False):
    met, reason, _ = sufficiency

    status = decision.claim_status
    object_part = decision.object_part

    # Cannot judge what cannot be clearly seen.
    if not met:
        status = "not_enough_information"
    # Supported requires an identifiable issue.
    if status == "supported" and decision.issue_type == "unknown":
        status = "not_enough_information"
    # Config D safety rule: when the image set appears to show different objects,
    # the object identity is not established, so the claim can never be supported;
    # fall back to not_enough_information (contradicted is left to the decision).
    if inconsistent_cap and cross_image_consistency == "inconsistent" and status == "supported":
        status = "not_enough_information"

    if status == "not_enough_information":
        issue_type = "unknown"
        severity = "unknown"
        supporting = []
    else:
        issue_type = decision.issue_type
        severity = decision.severity
        supporting = _filter_supporting(decision.supporting_image_ids, record)
        if issue_type == "none":
            severity = "none"

    return schemas.OutputRow(
        user_id=record.user_id,
        image_paths=record.image_paths_raw,
        user_claim=record.user_claim,
        claim_object=record.claim_object,
        evidence_standard_met=met,
        evidence_standard_met_reason=reason,
        risk_flags=risk_flags,
        issue_type=issue_type,
        object_part=object_part,
        claim_status=status,
        claim_status_justification=decision.justification,
        supporting_image_ids=supporting,
        valid_image=_valid_image(facts),
        severity=severity,
    )
