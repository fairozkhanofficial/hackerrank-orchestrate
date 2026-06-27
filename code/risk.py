"""Deterministic risk flags.

Risk flags combine three sources: user history, the vision findings (image
quality, manipulation, in-image instructions), and the decision outcome
(claim mismatch). Prompt-injection text in the conversation is detected here in
three languages so a manipulation attempt is always recorded, even though it
never changes the decision. The flags are returned in the canonical order from
config.RISK_FLAGS.
"""

from __future__ import annotations

import re

import config

# Prompt-injection phrases in English, romanised Hindi (Hinglish), and Spanish.
# These detect an attempt to instruct the system; they never change the verdict,
# they only raise text_instruction_present and force manual review.
INJECTION_PATTERNS = [
    # English
    r"ignore (all |any )?(previous|prior|earlier|above) instructions",
    r"approve (the |this |my )?claim",
    r"approve (this|it|the claim)(\s+\w+){0,3}\s+(immediately|now|quickly)",
    r"mark (this|it|the row|the claim)(\s+\w+){0,3}\s+(supported|approved|accepted)",
    r"skip (the )?(manual )?review",
    r"follow (the |this )?(note|instruction)",
    r"should be (approved|accepted|supported|marked)",
    # Hinglish (romanised Hindi)
    r"approve\s+kar(\s+(do|de\s*do|dena|den))?",
    r"approve\s+kara\s*do",
    r"claim\s+approve",
    r"follow\s+kar(ke|o)?",
    r"mark\s+kar(\s+(do|dena))?",
    r"ignore\s+kar(o|\s+do|\s+dena)?",
    r"review\s+(mat\s+karo|skip)",
    r"manual\s+review\s+skip",
    # Spanish
    r"aprueb[ae]\s+(el|la|este|esta|mi)?\s*(reclamo|caso|solicitud|reclamacion)?",
    r"aprobar\s+(el|la|este|esta|mi)?\s*(reclamo|caso)?",
    r"ignor[ae]\s+(las|todas\s+las)?\s*instrucciones",
    r"marca(r)?\s+como\s+(aprobado|soportado|aceptado)",
    r"salta(r)?\s+(la\s+)?revision",
    r"debe\s+ser\s+(aprobado|aceptado)",
]
INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)

CLARITY_TO_FLAG = {
    "blurry": "blurry_image",
    "cropped_or_obstructed": "cropped_or_obstructed",
    "low_light_or_glare": "low_light_or_glare",
    "wrong_angle": "wrong_angle",
}


def detect_injection(text: str) -> bool:
    """True if the text contains an instruction-injection attempt (any language)."""
    return bool(INJECTION_RE.search(text or ""))


def compute(record, facts, decision, sufficiency_met, cross_image_consistency="unknown") -> list:
    flags = set()

    # History-driven risk.
    if record.history:
        for flag in record.history.history_flags:
            if flag in config.RISK_FLAGS and flag != "none":
                flags.add(flag)
        if record.history.reject_ratio >= 0.4 and record.history.past_claim_count >= 3:
            flags.add("user_history_risk")

    # Vision-driven risk.
    any_object = any(f.object_present for f in facts)
    for fact in facts:
        if fact.clarity in CLARITY_TO_FLAG:
            flags.add(CLARITY_TO_FLAG[fact.clarity])
        if fact.tampering_signs:
            flags.add("possible_manipulation")
        if fact.screenshot_signs:
            flags.add("non_original_image")
        if fact.in_image_instruction_present:
            flags.add("text_instruction_present")
    if any_object and not any(f.object_matches_claim for f in facts):
        flags.add("wrong_object")

    # The claimed damage is not visible: either the part is never shown, or the
    # part is shown but no real damage is found while the claim was not supported.
    real_issue = any(o.issue_type not in ("none", "unknown")
                     for f in facts for o in f.observations)
    part_never_visible = bool(facts) and not any(f.claimed_part_visible for f in facts)
    if part_never_visible or (decision.claim_status in ("contradicted", "not_enough_information")
                              and not real_issue):
        flags.add("damage_not_visible")

    # Wrong object part: the right object is present, but the claimed part is not
    # shown while a different, specific part is. Distinct from wrong_object (a
    # different object entirely) and from damage_not_visible (claimed damage absent).
    observed_parts = {o.object_part for f in facts for o in f.observations
                      if o.object_part not in ("unknown", "")}
    claimed_part = decision.object_part
    object_ok = any(f.object_present and f.object_matches_claim for f in facts)
    if (object_ok and part_never_visible and observed_parts
            and claimed_part not in ("unknown", "") and claimed_part not in observed_parts):
        flags.add("wrong_object_part")

    # Cross-image inconsistency: the set appears to show different objects.
    inconsistent = cross_image_consistency == "inconsistent"
    if inconsistent:
        flags.add("claim_mismatch")

    # Conversation injection (English / Hinglish / Spanish).
    if detect_injection(record.user_claim):
        flags.add("text_instruction_present")

    # Decision-driven risk.
    if decision.claim_mismatch:
        flags.add("claim_mismatch")

    # Manual-review escalation.
    history_review = bool(record.history) and "manual_review_required" in record.history.history_flags
    if (history_review
            or inconsistent
            or "possible_manipulation" in flags
            or "non_original_image" in flags
            or "text_instruction_present" in flags
            or "wrong_object" in flags
            or "wrong_object_part" in flags
            or ("user_history_risk" in flags and decision.claim_status != "supported")):
        flags.add("manual_review_required")

    return [flag for flag in config.RISK_FLAGS if flag in flags and flag != "none"]
