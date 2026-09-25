import json


def _safe_float(value, default=None):
    try:
        number = float(value)
        if number != number:
            return default
        return number
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _ratio(numerator, denominator):
    if denominator in (None, 0):
        return None
    return numerator / denominator


def _add_unique(values, item):
    if item and item not in values:
        values.append(item)


def assess_recovery_confidence(candidate):
    if not candidate:
        return {
            "recovery_confidence": None,
            "confidence_level": "INSUFFICIENT",
            "confidence_factors": ["Insufficient evidence"],
            "explanation": "Insufficient evidence",
        }

    structural_integrity = _safe_float(candidate.get("structural_integrity"), None)
    verified_bytes = _safe_int(candidate.get("verified_bytes"), 0)
    inferred_bytes = _safe_int(candidate.get("inferred_bytes"), 0)
    missing_bytes = _safe_int(candidate.get("missing_bytes"), 0)
    relationship_count = _safe_int(candidate.get("relationship_count"), 0)
    missing_regions = candidate.get("missing_regions") or []
    conflicts = candidate.get("conflicts") or []

    total_bytes = verified_bytes + inferred_bytes + missing_bytes
    verified_ratio = _ratio(verified_bytes, total_bytes)
    inferred_ratio = _ratio(inferred_bytes, total_bytes)
    missing_ratio = _ratio(missing_bytes, total_bytes)

    factors = []
    reasons = []

    if structural_integrity is not None:
        factors.append(f"Structural validation result: {structural_integrity:.2f}/100")
        reasons.append(f"Structural integrity is {structural_integrity:.2f}/100.")
    else:
        reasons.append("Structural integrity is unavailable.")

    if total_bytes > 0:
        if verified_ratio is not None:
            factors.append(f"Verified bytes comprise {verified_ratio * 100:.2f}% of the reconstructed range.")
        if inferred_ratio is not None:
            factors.append(f"Inferred bytes comprise {inferred_ratio * 100:.2f}% of the reconstructed range.")
        if missing_ratio is not None:
            factors.append(f"Missing bytes comprise {missing_ratio * 100:.2f}% of the reconstructed range.")
    else:
        factors.append("No measurable byte coverage was recorded.")

    if relationship_count > 0:
        factors.append(f"{relationship_count} fragment relationship(s) were evaluated.")

    if missing_regions:
        gap_count = sum(1 for region in missing_regions if region.get("kind") == "gap")
        overlap_count = sum(1 for region in missing_regions if region.get("kind") == "overlap")
        if gap_count:
            factors.append(f"{gap_count} storage gap(s) remain between fragments.")
        if overlap_count:
            factors.append(f"{overlap_count} overlap(s) were detected between fragments.")

    if conflicts:
        factors.append("Conflicting evidence was detected and penalized.")

    score = 0.0

    if structural_integrity is not None:
        score += min(structural_integrity / 100.0, 1.0) * 0.45

    if total_bytes > 0:
        if verified_ratio is not None:
            score += min(verified_ratio, 1.0) * 0.35
        if inferred_ratio is not None:
            score -= min(inferred_ratio, 1.0) * 0.15
        if missing_ratio is not None:
            score -= min(missing_ratio, 1.0) * 0.20

    if relationship_count > 0:
        score += min(relationship_count / 20.0, 0.10)

    if conflicts:
        score -= min(len(conflicts) * 0.10, 0.25)

    score = max(0.0, min(score, 1.0))

    if total_bytes <= 0 and (structural_integrity is None or structural_integrity < 50.0):
        confidence_level = "INSUFFICIENT"
        recovery_confidence = None
        explanation = "Insufficient evidence"
    else:
        if score >= 0.80:
            confidence_level = "HIGH"
        elif score >= 0.55:
            confidence_level = "MEDIUM"
        elif score >= 0.25:
            confidence_level = "LOW"
        else:
            confidence_level = "INSUFFICIENT"
            recovery_confidence = None
            explanation = "Insufficient evidence"
            return {
                "recovery_confidence": recovery_confidence,
                "confidence_level": confidence_level,
                "confidence_factors": factors,
                "explanation": explanation,
            }

        recovery_confidence = round(score * 100, 2)
        explanation = " ".join(reasons + [f"Overall recovery confidence is {recovery_confidence:.2f}% based on measurable evidence."])

    return {
        "recovery_confidence": recovery_confidence,
        "confidence_level": confidence_level,
        "confidence_factors": factors,
        "explanation": explanation,
    }


def assess_recovery_feasibility(candidate):
    if not candidate:
        return {
            "feasibility_status": "INSUFFICIENT_EVIDENCE",
            "feasibility_factors": ["No candidate data available."],
            "blockers": ["Insufficient evidence"],
            "supporting_evidence": [],
            "explanation": "Insufficient evidence",
        }

    fragments_used = candidate.get("fragments_used") or []
    missing_regions = candidate.get("missing_regions") or []
    relationship_count = _safe_int(candidate.get("relationship_count"), 0)
    structural_integrity = _safe_float(candidate.get("structural_integrity"), None)
    conflicts = candidate.get("conflicts") or []

    supporting_evidence = []
    blockers = []
    factors = []

    if len(fragments_used) >= 2:
        supporting_evidence.append("Multiple fragments are present for ordering analysis.")
        factors.append("At least two fragments are available.")
    else:
        blockers.append("Insufficient fragment candidates")

    if relationship_count > 0:
        supporting_evidence.append("Fragment relationships were measured and recorded.")
        factors.append(f"{relationship_count} relationship(s) were available for evidence comparison.")
    else:
        blockers.append("No measured fragment relationships were available.")

    if structural_integrity is not None:
        if structural_integrity >= 90.0:
            supporting_evidence.append("Structural validation succeeded for the reconstruction candidate.")
        else:
            blockers.append("Structural validation did not fully succeed.")

    if missing_regions:
        gap_count = sum(1 for region in missing_regions if region.get("kind") == "gap")
        overlap_count = sum(1 for region in missing_regions if region.get("kind") == "overlap")
        if gap_count:
            blockers.append(f"{gap_count} storage gap(s) remain between fragment boundaries.")
        if overlap_count:
            blockers.append(f"{overlap_count} overlapping range(s) were detected.")
        factors.append(f"{len(missing_regions)} boundary condition(s) were evaluated.")
    else:
        supporting_evidence.append("Fragment boundaries are continuous or adjacent.")

    if conflicts:
        blockers.extend(conflicts)
        factors.append("Conflicting evidence was detected.")

    if not blockers:
        feasibility_status = "HIGH_FEASIBILITY"
        explanation = "Evidence supports a realistic reconstruction path."
    elif len(blockers) <= 2:
        feasibility_status = "PARTIAL_FEASIBILITY"
        explanation = "Some evidence supports reconstruction, but important gaps or conflicts remain."
    elif len(blockers) <= 4:
        feasibility_status = "LOW_FEASIBILITY"
        explanation = "Evidence is limited and a reliable recovery is uncertain."
    else:
        feasibility_status = "INSUFFICIENT_EVIDENCE"
        explanation = "Insufficient evidence"

    if len(fragments_used) < 2 and feasibility_status != "INSUFFICIENT_EVIDENCE":
        feasibility_status = "INSUFFICIENT_EVIDENCE"
        explanation = "Insufficient evidence"

    return {
        "feasibility_status": feasibility_status,
        "feasibility_factors": factors,
        "blockers": blockers,
        "supporting_evidence": supporting_evidence,
        "explanation": explanation,
    }


def build_assessment_record(candidate):
    confidence = assess_recovery_confidence(candidate)
    feasibility = assess_recovery_feasibility(candidate)

    candidate["recovery_confidence"] = confidence.get("recovery_confidence")
    candidate["confidence_level"] = confidence.get("confidence_level")
    candidate["confidence_factors"] = confidence.get("confidence_factors", [])
    candidate["confidence_explanation"] = confidence.get("explanation")
    candidate["feasibility_status"] = feasibility.get("feasibility_status")
    candidate["feasibility_factors"] = feasibility.get("feasibility_factors", [])
    candidate["feasibility_blockers"] = feasibility.get("blockers", [])
    candidate["feasibility_supporting_evidence"] = feasibility.get("supporting_evidence", [])
    candidate["feasibility_explanation"] = feasibility.get("explanation")

    total_bytes = _safe_int(candidate.get("verified_bytes"), 0) + _safe_int(candidate.get("inferred_bytes"), 0) + _safe_int(candidate.get("missing_bytes"), 0)
    candidate["verified_ratio"] = _ratio(_safe_int(candidate.get("verified_bytes"), 0), total_bytes)
    candidate["inferred_ratio"] = _ratio(_safe_int(candidate.get("inferred_bytes"), 0), total_bytes)
    candidate["missing_ratio"] = _ratio(_safe_int(candidate.get("missing_bytes"), 0), total_bytes)

    candidate["conflicts"] = candidate.get("conflicts") or []

    return candidate
