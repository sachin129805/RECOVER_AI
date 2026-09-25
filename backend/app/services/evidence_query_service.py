import json

from app.core.database import get_connection
from app.services.reconstruction_service import (
    analyze_contradictions_for_reconstruction,
    analyze_missing_regions_for_reconstruction,
    analyze_overlaps_for_reconstruction,
    analyze_uncertainties_for_reconstruction,
)


SUPPORTED_QUERY_TYPES = {
    "fragments",
    "largest_fragment",
    "overlaps",
    "missing_regions",
    "recovery_status",
    "confidence",
    "feasibility",
    "contradictions",
    "priority",
    "sha256",
    "verified_bytes",
    "inferred_bytes",
    "unknown_regions",
    "relationships",
}


def _safe_json_list(value):
    if value in (None, ""):
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return parsed
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return []


def query_evidence(evidence_id: str, question: str):
    if not evidence_id or not question:
        return {
            "query_type": "unsupported",
            "result": None,
            "supported": False,
            "evidence_references": [],
            "error": "Evidence ID and question are required.",
        }

    connection = get_connection()
    evidence_row = connection.execute(
        "SELECT * FROM evidence WHERE evidence_id = ?",
        (evidence_id,),
    ).fetchone()
    if evidence_row is None:
        connection.close()
        return {
            "query_type": "missing_evidence",
            "result": None,
            "supported": False,
            "evidence_references": [],
            "error": "Evidence not found.",
        }

    fragments = [dict(row) for row in connection.execute(
        "SELECT * FROM fragments WHERE evidence_id = ? ORDER BY offset ASC",
        (evidence_id,),
    ).fetchall()]
    relationships = [dict(row) for row in connection.execute(
        "SELECT * FROM fragment_relationships WHERE evidence_id = ? ORDER BY created_at DESC",
        (evidence_id,),
    ).fetchall()]
    reconstructions = connection.execute(
        "SELECT * FROM reconstructions WHERE evidence_id = ? ORDER BY created_at DESC LIMIT 1",
        (evidence_id,),
    ).fetchone()
    connection.close()

    normalized = str(question).lower()
    query_type = "unsupported"
    result = None

    if "fragment" in normalized and "largest" in normalized:
        query_type = "largest_fragment"
        result = sorted(fragments, key=lambda item: int(item.get("sample_size") or 0), reverse=True)[:5]
    elif "fragment" in normalized:
        query_type = "fragments"
        result = fragments
    elif "overlap" in normalized:
        query_type = "overlaps"
        if reconstructions is None:
            result = []
        else:
            result = analyze_overlaps_for_reconstruction(reconstructions["reconstruction_id"], evidence_id, dict(reconstructions))["overlaps"]
    elif "missing" in normalized and "region" in normalized:
        query_type = "missing_regions"
        if reconstructions is None:
            result = []
        else:
            result = analyze_missing_regions_for_reconstruction(reconstructions["reconstruction_id"], evidence_id, dict(reconstructions))["missing_regions"]
    elif "confidence" in normalized:
        query_type = "confidence"
        if reconstructions is not None:
            result = {
                "confidence_level": reconstructions["confidence_level"],
                "recovery_confidence": reconstructions["recovery_confidence"],
                "confidence_factors": _safe_json_list(reconstructions["confidence_factors_json"]),
            }
        else:
            result = {"confidence_level": "UNKNOWN", "recovery_confidence": None}
    elif "feas" in normalized or "feasible" in normalized:
        query_type = "feasibility"
        if reconstructions is not None:
            result = {
                "feasibility_status": reconstructions["feasibility_status"],
                "feasibility_factors": _safe_json_list(reconstructions["feasibility_factors_json"]),
                "feasibility_blockers": _safe_json_list(reconstructions["feasibility_blockers_json"]),
            }
        else:
            result = {"feasibility_status": "UNKNOWN"}
    elif "contradict" in normalized:
        query_type = "contradictions"
        if reconstructions is not None:
            result = analyze_contradictions_for_reconstruction(reconstructions["reconstruction_id"], evidence_id, dict(reconstructions))["contradictions"]
        else:
            result = []
    elif "priority" in normalized:
        query_type = "priority"
        if reconstructions is not None:
            result = {
                "priority": reconstructions["priority"],
                "priority_score": reconstructions["priority_score"],
                "priority_factors": _safe_json_list(reconstructions["priority_factors_json"]),
                "positive_factors": _safe_json_list(reconstructions["positive_factors_json"]),
                "negative_factors": _safe_json_list(reconstructions["negative_factors_json"]),
            }
        else:
            result = {"priority": "UNKNOWN", "priority_score": None}
    elif "sha" in normalized or "hash" in normalized:
        query_type = "sha256"
        result = evidence_row["sha256"]
    elif "relationship" in normalized:
        query_type = "relationships"
        result = relationships
    elif "verified" in normalized and "byte" in normalized:
        query_type = "verified_bytes"
        if reconstructions is not None:
            result = reconstructions["verified_bytes"]
    elif "inferred" in normalized and "byte" in normalized:
        query_type = "inferred_bytes"
        if reconstructions is not None:
            result = reconstructions["inferred_bytes"]
    elif "unknown" in normalized or ("missing" in normalized and "unknown" in normalized):
        query_type = "unknown_regions"
        if reconstructions is not None:
            result = analyze_uncertainties_for_reconstruction(reconstructions["reconstruction_id"], evidence_id, dict(reconstructions))["uncertainties"]
        else:
            result = []
    elif "status" in normalized or "recover" in normalized:
        query_type = "recovery_status"
        if reconstructions is not None:
            result = {"status": reconstructions["status"], "reconstruction_type": reconstructions["reconstruction_type"]}
        else:
            result = {"status": "UNKNOWN"}

    supported = query_type in SUPPORTED_QUERY_TYPES and result is not None
    return {
        "query_type": query_type,
        "result": result,
        "supported": supported,
        "evidence_references": [
            f"Evidence {evidence_id}",
            f"Fragment count: {len(fragments)}",
            f"Relationship count: {len(relationships)}",
        ],
    }
