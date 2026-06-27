"""Deterministic evidence sufficiency.

evidence_standard_met is true when at least one submitted image shows the claimed
object and the claimed part clearly enough to inspect the claimed condition, per
evidence_requirements.csv. This is decided from the vision findings, with no model
call, so it stays reproducible. Authenticity concerns are handled separately by
valid_image and risk_flags, not here.
"""

from __future__ import annotations


def _assessable(fact) -> bool:
    return fact.object_present and fact.claimed_part_visible and fact.clarity == "clear"


def evaluate(record, facts, cross_image_consistency="unknown", consistency_blocks=True):
    """Return (met: bool, reason: str, assessable_ids: list).

    consistency_blocks: when True (default, Config A/B), an inconsistent image set
    hard-blocks evidence sufficiency. When False (Config C), inconsistency no
    longer forces not-met here; it remains a risk flag and decision context, and
    the decision model may still return not_enough_information if warranted.
    """
    if consistency_blocks and cross_image_consistency == "inconsistent":
        return False, ("The submitted images appear to show different objects, so the "
                       "claimed object's identity cannot be confirmed from this set."), []

    assessable = [f for f in facts if _assessable(f)]
    if assessable:
        ids = ";".join(f.image_id for f in assessable)
        reason = (f"The claimed {record.claim_object} part is visible and clear "
                  f"enough to inspect in {ids}.")
        return True, reason, [f.image_id for f in assessable]

    if not facts:
        return False, "No usable image was submitted for this claim.", []
    if not any(f.object_present for f in facts):
        return False, f"No submitted image clearly shows a {record.claim_object}.", []
    if not any(f.claimed_part_visible for f in facts):
        return False, ("The submitted images do not show the claimed part clearly "
                       "enough to assess the claim."), []

    blockers = sorted({f.clarity for f in facts if f.claimed_part_visible and f.clarity != "clear"})
    reason = "The claimed part is not shown clearly enough to assess"
    if blockers:
        reason += f" ({', '.join(blockers)})"
    return False, reason + ".", []
