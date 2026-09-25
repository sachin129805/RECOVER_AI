import json

from app.core.database import get_connection
from app.services.evidence_query_service import query_evidence


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


def _truncate_list(items, limit=25):
    if not isinstance(items, list):
        return items
    if len(items) <= limit:
        return items
    return {
        "count": len(items),
        "sample": items[:limit],
        "truncated": True,
    }


def build_evidence_context(evidence_id: str) -> dict:
    connection = get_connection()
    evidence = connection.execute(
        "SELECT * FROM evidence WHERE evidence_id = ?",
        (evidence_id,),
    ).fetchone()

    if evidence is None:
        connection.close()
        raise ValueError(f"Evidence not found: {evidence_id}")

    evidence_data = dict(evidence)
    evidence_data["metadata"] = json.loads(evidence_data.get("metadata") or "{}") if evidence_data.get("metadata") else {}

    fragments = connection.execute(
        "SELECT * FROM fragments WHERE evidence_id = ? ORDER BY offset ASC",
        (evidence_id,),
    ).fetchall()
    relationship_rows = connection.execute(
        "SELECT * FROM fragment_relationships WHERE evidence_id = ? ORDER BY created_at DESC",
        (evidence_id,),
    ).fetchall()
    reconstructions = connection.execute(
        "SELECT * FROM reconstructions WHERE evidence_id = ? ORDER BY created_at DESC",
        (evidence_id,),
    ).fetchall()

    fragment_list = [dict(row) for row in fragments]
    relationship_list = [dict(row) for row in relationship_rows]
    reconstruction_list = []
    for row in reconstructions:
        item = dict(row)
        item["fragment_ids"] = _safe_json_list(item.get("fragment_ids"))
        item["missing_regions"] = _safe_json_list(item.get("missing_regions"))
        item["reasons"] = _safe_json_list(item.get("reasons_json"))
        item["confidence_factors"] = _safe_json_list(item.get("confidence_factors_json"))
        item["feasibility_factors"] = _safe_json_list(item.get("feasibility_factors_json"))
        item["feasibility_blockers"] = _safe_json_list(item.get("feasibility_blockers_json"))
        reconstruction_list.append(item)

    connection.close()

    summary_questions = [
        "missing_regions",
        "relationships",
        "confidence",
        "contradictions",
        "recovery_status",
        "priority",
        "sha256",
    ]

    evidence_references = [
        f"Evidence {evidence_id}",
        f"SHA-256: {evidence_data.get('sha256')}",
        f"File type: {evidence_data.get('file_type')}",
        f"Fragments: {len(fragment_list)}",
        f"Reconstruction records: {len(reconstruction_list)}",
    ]

    result = {
        "evidence_id": evidence_id,
        "evidence": evidence_data,
        "fragments": _truncate_list(fragment_list, 25),
        "relationships": _truncate_list(relationship_list, 25),
        "reconstructions": _truncate_list(reconstruction_list, 25),
        "evidence_references": evidence_references,
        "limitations": [
            "Reference artifact unavailable unless explicitly supplied.",
            "Inferred byte ranges are not verified original data.",
            "Engineering confidence is not legal certainty.",
        ],
        "deterministic_queries": {
            question: query_evidence(evidence_id, question)["result"]
            for question in summary_questions
        },
    }
    return result
