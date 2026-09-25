import hashlib
import json
from pathlib import Path
from uuid import uuid4

from app.ai.confidence import build_assessment_record
from app.core.config import RECOVERED_DIR
from app.core.database import get_connection
from app.services.fragment_service import get_fragments
from app.services.hashing import calculate_sha256
from app.services.relationship_service import get_fragment_relationships


def generate_reconstruction_id():
    return f"RC-{uuid4().hex[:8].upper()}"


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value, default=None):
    try:
        number = float(value)
        if number != number:
            return default
        return number
    except (TypeError, ValueError):
        return default


def _parse_json_list(value):
    if value in (None, ""):
        return []

    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return parsed
    except (TypeError, ValueError, json.JSONDecodeError):
        pass

    return []


def _build_missing_regions(order):
    missing_regions = []

    for previous, current in zip(order, order[1:]):
        previous_offset = _safe_int(previous.get("offset"), 0)
        previous_size = _safe_int(previous.get("sample_size"), 0)
        current_offset = _safe_int(current.get("offset"), 0)

        previous_end = previous_offset + previous_size
        next_start = current_offset
        missing_bytes = next_start - previous_end

        if missing_bytes > 0:
            missing_regions.append(
                {
                    "from_fragment_id": previous.get("fragment_id"),
                    "to_fragment_id": current.get("fragment_id"),
                    "previous_end": previous_end,
                    "next_start": next_start,
                    "missing_bytes": missing_bytes,
                    "kind": "gap",
                }
            )
        elif missing_bytes < 0:
            missing_regions.append(
                {
                    "from_fragment_id": previous.get("fragment_id"),
                    "to_fragment_id": current.get("fragment_id"),
                    "previous_end": previous_end,
                    "next_start": next_start,
                    "missing_bytes": abs(missing_bytes),
                    "kind": "overlap",
                }
            )
        else:
            missing_regions.append(
                {
                    "from_fragment_id": previous.get("fragment_id"),
                    "to_fragment_id": current.get("fragment_id"),
                    "previous_end": previous_end,
                    "next_start": next_start,
                    "missing_bytes": 0,
                    "kind": "adjacent",
                }
            )

    return missing_regions


def _candidate_order(fragments, relationships):
    if not fragments:
        return []

    ordered = sorted(
        fragments,
        key=lambda fragment: (
            _safe_int(fragment.get("offset"), 0),
            _safe_int(fragment.get("sample_size"), 0),
        ),
    )

    if len(ordered) <= 1:
        return ordered

    relationship_map = {}
    for rel in relationships:
        left = rel.get("fragment_a_id")
        right = rel.get("fragment_b_id")
        score = _safe_float(rel.get("relationship_score"), 0.0) or 0.0
        if left and right:
            relationship_map.setdefault(left, []).append((right, score))
            relationship_map.setdefault(right, []).append((left, score))

    ordered_ids = [fragment["fragment_id"] for fragment in ordered]
    ranked = []
    for fragment in ordered:
        fragment_id = fragment["fragment_id"]
        score = 0.0
        neighbors = relationship_map.get(fragment_id, [])
        for _, relationship_score in neighbors:
            score += relationship_score
        ranked.append((fragment_id, score))

    ranked.sort(key=lambda item: (-item[1], item[0]))
    preferred_ids = [fragment_id for fragment_id, _ in ranked]

    preferred = []
    seen = set()
    for fragment_id in preferred_ids:
        if fragment_id in seen:
            continue
        found = next((fragment for fragment in ordered if fragment["fragment_id"] == fragment_id), None)
        if found is not None:
            preferred.append(found)
            seen.add(fragment_id)
    for fragment in ordered:
        if fragment["fragment_id"] not in seen:
            preferred.append(fragment)

    return preferred


def _candidate_status_from_signals(reasons, missing_regions, structural_integrity):
    if not reasons:
        return "UNABLE_TO_RECOVER"

    if structural_integrity is not None and structural_integrity >= 90.0:
        return "VERIFIED_RECOVERY"

    if any(region.get("kind") == "overlap" for region in missing_regions):
        return "STRUCTURAL_REPAIR"

    if any("gap" in reason.lower() or "missing" in reason.lower() for reason in reasons):
        return "STRUCTURAL_REPAIR"

    if any("inferred" in reason.lower() for reason in reasons):
        return "INFERRED_RECONSTRUCTION"

    return "UNABLE_TO_RECOVER"


def _compute_reconstruction_score(order, relationships):
    if len(order) < 2:
        return 0.0

    total_score = 0.0
    pair_count = 0

    for index, previous in enumerate(order[:-1]):
        current = order[index + 1]
        for relationship in relationships:
            if {
                relationship.get("fragment_a_id"),
                relationship.get("fragment_b_id"),
            } == {
                previous.get("fragment_id"),
                current.get("fragment_id"),
            }:
                total_score += float(relationship.get("relationship_score", 0.0) or 0.0)
                pair_count += 1
                break

    if pair_count == 0:
        return 0.0

    return total_score / pair_count


def _assemble_candidate_bytes(order, missing_regions):
    if not order:
        return b""

    output = bytearray()
    for fragment in order:
        payload = b""
        if fragment.get("source_path"):
            try:
                payload = Path(fragment["source_path"]).read_bytes()
            except OSError:
                payload = b""
        elif fragment.get("storage_path"):
            try:
                payload = Path(fragment["storage_path"]).read_bytes()
            except OSError:
                payload = b""
        else:
            payload = b""
        output.extend(payload)

    if not output:
        return b""

    return bytes(output)


def _hash_bytes(data: bytes):
    if not data:
        return None
    return hashlib.sha256(data).hexdigest()


def _build_output_artifact(evidence_id: str, candidate_id: str, data: bytes, fragment_ids: list[str]):
    if not data:
        return None

    recovered_dir = RECOVERED_DIR / evidence_id
    recovered_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{candidate_id}.bin"
    output_path = recovered_dir / filename
    output_path.write_bytes(data)

    return {
        "output_path": str(output_path),
        "output_filename": filename,
        "sha256": _hash_bytes(data),
    }


def build_reconstruction_candidate(evidence_id: str):
    fragments = get_fragments(evidence_id)
    relationships = get_fragment_relationships(evidence_id)

    if len(fragments) < 2:
        return {
            "reconstruction_id": None,
            "evidence_id": evidence_id,
            "status": "Insufficient fragment candidates",
            "message": "At least two compatible fragments are required to build a reconstruction candidate.",
            "fragments_used": [],
            "fragment_count": len(fragments),
            "relationship_count": len(relationships),
            "missing_regions": [],
            "verified_bytes": 0,
            "inferred_bytes": 0,
            "missing_bytes": 0,
            "structural_integrity": None,
            "recovery_confidence": None,
            "output_path": None,
            "reasons": ["Insufficient fragment candidates"],
        }

    order = _candidate_order(fragments, relationships)
    missing_regions = _build_missing_regions(order)
    relationship_score = _compute_reconstruction_score(order, relationships)

    reasons = []
    if order:
        reasons.append("Fragments were ordered using actual storage offsets and relationship scores.")
    if missing_regions:
        reasons.append("Missing regions were calculated from actual fragment boundaries.")
    if relationship_score > 0:
        reasons.append("Candidate ordering is supported by measurable fragment relationships.")
    else:
        reasons.append("Candidate ordering has no strong measurable support from fragment relationships.")

    for region in missing_regions:
        if region.get("kind") == "gap":
            reasons.append(
                f"Gap between {region.get('from_fragment_id')} and {region.get('to_fragment_id')}: {region.get('missing_bytes', 0)} bytes."
            )
        elif region.get("kind") == "overlap":
            reasons.append(
                f"Overlap between {region.get('from_fragment_id')} and {region.get('to_fragment_id')}: {region.get('missing_bytes', 0)} bytes."
            )
        elif region.get("kind") == "adjacent":
            reasons.append(
                f"Adjacent fragments: {region.get('from_fragment_id')} and {region.get('to_fragment_id')}."
            )

    verified_bytes = 0
    for fragment in order:
        verified_bytes += _safe_int(fragment.get("verified_bytes"), 0)

    missing_bytes = sum(int(region.get("missing_bytes", 0)) for region in missing_regions)
    inferred_bytes = max(0, missing_bytes)

    structural_integrity = None
    if order:
        sample_values = [
            _safe_float(fragment.get("structural_integrity"), None)
            for fragment in order
            if _safe_float(fragment.get("structural_integrity"), None) is not None
        ]
        if sample_values:
            structural_integrity = sum(sample_values) / len(sample_values)

    status = _candidate_status_from_signals(reasons, missing_regions, structural_integrity)

    if status == "INFERRED_RECONSTRUCTION":
        reasons.append("INFERRED — NOT VERIFIED ORIGINAL DATA")

    reconstructed_data = _assemble_candidate_bytes(order, missing_regions)
    artifact = _build_output_artifact(
        evidence_id=evidence_id,
        candidate_id=generate_reconstruction_id(),
        data=reconstructed_data,
        fragment_ids=[fragment["fragment_id"] for fragment in order],
    )

    result = {
        "reconstruction_id": artifact["output_filename"].rsplit(".", 1)[0] if artifact else None,
        "evidence_id": evidence_id,
        "status": status,
        "reconstruction_type": status,
        "fragments_used": [fragment["fragment_id"] for fragment in order],
        "fragment_count": len(order),
        "relationship_count": len(relationships),
        "missing_regions": missing_regions,
        "verified_bytes": verified_bytes,
        "inferred_bytes": inferred_bytes,
        "missing_bytes": missing_bytes,
        "structural_integrity": structural_integrity,
        "recovery_confidence": None,
        "output_path": artifact["output_path"] if artifact else None,
        "output_filename": artifact["output_filename"] if artifact else None,
        "reconstructed_size": len(reconstructed_data),
        "sha256": artifact["sha256"] if artifact else None,
        "reasons": reasons,
        "conflicts": [],
    }

    result = build_assessment_record(result)
    evidence_analysis = analyze_evidence_issues(
        reconstruction_id=result.get("reconstruction_id"),
        evidence_id=evidence_id,
        reconstruction=result,
    )
    contribution_summary = analyze_fragment_contributions(
        reconstruction_id=result.get("reconstruction_id"),
        evidence_id=evidence_id,
        reconstruction=result,
    )
    priority_record = evaluate_recovery_priority(
        reconstruction_id=result.get("reconstruction_id"),
        evidence_id=evidence_id,
        reconstruction=result,
        evidence_analysis=evidence_analysis,
    )

    result["contribution_summary"] = contribution_summary
    result["missing_regions_analysis"] = evidence_analysis["missing_regions"]
    result["overlaps"] = evidence_analysis["overlaps"]
    result["contradictions"] = evidence_analysis["contradictions"]
    result["uncertainties"] = evidence_analysis["uncertainties"]
    result["evidence_status"] = evidence_analysis["evidence_status"]
    result["evidence_summary"] = {
        "status": evidence_analysis["evidence_status"],
        "explanation": evidence_analysis["explanation"],
    }
    result["priority"] = priority_record["priority"]
    result["priority_score"] = priority_record["score"]
    result["priority_factors"] = priority_record["factors"]
    result["positive_factors"] = priority_record["positive_factors"]
    result["negative_factors"] = priority_record["negative_factors"]
    result["unresolved_issues"] = priority_record["unresolved_issues"]
    result["priority_explanation"] = priority_record["explanation"]

    provenance_record = build_evidence_provenance(
        reconstruction_id=result.get("reconstruction_id"),
        evidence_id=evidence_id,
        reconstruction=result,
    )
    result["provenance"] = provenance_record

    connection = get_connection()
    connection.execute(
        """
        INSERT INTO reconstructions (
            reconstruction_id,
            evidence_id,
            status,
            reconstruction_type,
            output_path,
            output_filename,
            fragment_ids,
            missing_regions,
            reasons_json,
            verified_bytes,
            inferred_bytes,
            missing_bytes,
            structural_integrity,
            recovery_confidence,
            reconstructed_size,
            sha256,
            confidence_level,
            confidence_factors_json,
            feasibility_status,
            feasibility_factors_json,
            feasibility_blockers_json,
            verified_ratio,
            inferred_ratio,
            missing_ratio,
            contribution_summary_json,
            missing_regions_json,
            overlaps_json,
            contradictions_json,
            uncertainties_json,
            evidence_status,
            evidence_summary_json,
            priority,
            priority_score,
            priority_factors_json,
            positive_factors_json,
            negative_factors_json,
            unresolved_issues_json,
            priority_explanation
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            result["reconstruction_id"],
            evidence_id,
            status,
            status,
            result["output_path"],
            result["output_filename"],
            json.dumps(result["fragments_used"]),
            json.dumps(result["missing_regions"]),
            json.dumps(result["reasons"]),
            result["verified_bytes"],
            result["inferred_bytes"],
            result["missing_bytes"],
            result["structural_integrity"],
            result["recovery_confidence"],
            result["reconstructed_size"],
            result["sha256"],
            result.get("confidence_level"),
            json.dumps(result.get("confidence_factors", [])),
            result.get("feasibility_status"),
            json.dumps(result.get("feasibility_factors", [])),
            json.dumps(result.get("feasibility_blockers", [])),
            result.get("verified_ratio"),
            result.get("inferred_ratio"),
            result.get("missing_ratio"),
            json.dumps(contribution_summary),
            json.dumps(evidence_analysis["missing_regions"]),
            json.dumps(evidence_analysis["overlaps"]),
            json.dumps(evidence_analysis["contradictions"]),
            json.dumps(evidence_analysis["uncertainties"]),
            evidence_analysis["evidence_status"],
            json.dumps(result["evidence_summary"]),
            priority_record["priority"],
            priority_record["score"],
            json.dumps(priority_record["factors"]),
            json.dumps(priority_record["positive_factors"]),
            json.dumps(priority_record["negative_factors"]),
            json.dumps(priority_record["unresolved_issues"]),
            priority_record["explanation"],
        ),
    )
    connection.commit()
    connection.close()

    return result


def get_reconstructions_for_evidence(evidence_id: str):
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT *
        FROM reconstructions
        WHERE evidence_id = ?
        ORDER BY created_at DESC
        """,
        (evidence_id,),
    ).fetchall()
    connection.close()

    results = []
    for row in rows:
        item = dict(row)
        item["fragment_ids"] = _parse_json_list(item.get("fragment_ids"))
        item["missing_regions"] = _parse_json_list(item.get("missing_regions"))
        item["reasons"] = _parse_json_list(item.get("reasons_json"))
        item["confidence_factors"] = _parse_json_list(item.get("confidence_factors_json"))
        item["feasibility_factors"] = _parse_json_list(item.get("feasibility_factors_json"))
        item["feasibility_blockers"] = _parse_json_list(item.get("feasibility_blockers_json"))
        item["supporting_evidence"] = _parse_json_list(item.get("feasibility_supporting_evidence_json"))
        item["priority_factors"] = _parse_json_list(item.get("priority_factors_json"))
        item["positive_factors"] = _parse_json_list(item.get("positive_factors_json"))
        item["negative_factors"] = _parse_json_list(item.get("negative_factors_json"))
        item["unresolved_issues"] = _parse_json_list(item.get("unresolved_issues_json"))
        item.pop("reasons_json", None)
        item.pop("confidence_factors_json", None)
        item.pop("feasibility_factors_json", None)
        item.pop("feasibility_blockers_json", None)
        item.pop("feasibility_supporting_evidence_json", None)
        item.pop("priority_factors_json", None)
        item.pop("positive_factors_json", None)
        item.pop("negative_factors_json", None)
        item.pop("unresolved_issues_json", None)
        results.append(item)

    return results


def detect_duplicate_evidence(evidence_id: str):
    connection = get_connection()
    evidence_row = connection.execute(
        "SELECT * FROM evidence WHERE evidence_id = ?",
        (evidence_id,),
    ).fetchone()
    if not evidence_row:
        connection.close()
        return {
            "evidence_id": evidence_id,
            "duplicates": [],
            "is_duplicate": False,
            "criteria": ["sha256", "size_bytes"],
            "explanation": "Evidence record not found.",
        }

    source = dict(evidence_row)
    duplicate_rows = connection.execute(
        """
        SELECT evidence_id, filename, file_type, size_bytes, sha256
        FROM evidence
        WHERE evidence_id != ?
          AND sha256 = ?
          AND size_bytes = ?
        ORDER BY created_at DESC
        """,
        (evidence_id, source.get("sha256"), source.get("size_bytes")),
    ).fetchall()
    connection.close()

    duplicates = [dict(row) for row in duplicate_rows]
    return {
        "evidence_id": evidence_id,
        "duplicates": duplicates,
        "is_duplicate": bool(duplicates),
        "criteria": ["sha256", "size_bytes"],
        "explanation": "Duplicate evidence is determined only from identical file hash and size, not filename matching.",
    }


def evaluate_recovery_priority(reconstruction_id: str, evidence_id: str, reconstruction: dict, evidence_analysis: dict | None = None):
    evidence_analysis = evidence_analysis or {}
    evidence_row = get_connection().execute(
        "SELECT * FROM evidence WHERE evidence_id = ?",
        (evidence_id,),
    ).fetchone()
    get_connection().close()

    if evidence_row:
        evidence_row = dict(evidence_row)
    else:
        evidence_row = {}

    structural_integrity = _safe_float(reconstruction.get("structural_integrity"), 0.0)
    recovery_confidence = _safe_float(reconstruction.get("recovery_confidence"), 0.0)
    verified_ratio = _safe_float(reconstruction.get("verified_ratio"), 0.0)
    inferred_ratio = _safe_float(reconstruction.get("inferred_ratio"), 0.0)
    missing_ratio = _safe_float(reconstruction.get("missing_ratio"), 0.0)
    missing_regions = evidence_analysis.get("missing_regions") or []
    contradictions = evidence_analysis.get("contradictions") or []
    uncertainties = evidence_analysis.get("uncertainties") or []

    positive_factors = []
    negative_factors = []
    factors = []
    unresolved_issues = []
    score = 0.0

    if reconstruction.get("status") == "VERIFIED_RECOVERY":
        positive_factors.append("Reconstruction passed structural validation.")
        factors.append("Structural validation passed")
        score += 0.25

    if recovery_confidence is not None:
        confidence_component = min(max(recovery_confidence / 100.0, 0.0), 1.0)
        score += confidence_component * 0.40
        factors.append(f"Recovery confidence: {recovery_confidence:.2f}%")
        if recovery_confidence >= 70:
            positive_factors.append("Recovery confidence is high.")
        elif recovery_confidence < 40:
            negative_factors.append("Recovery confidence is low.")

    if structural_integrity is not None:
        structural_component = min(max(structural_integrity / 100.0, 0.0), 1.0)
        score += structural_component * 0.25
        factors.append(f"Structural integrity: {structural_integrity:.2f}/100")
        if structural_integrity >= 80:
            positive_factors.append("Structural integrity is strong.")
        else:
            negative_factors.append("Structural integrity is limited.")

    if verified_ratio is not None:
        score += min(max(verified_ratio, 0.0), 1.0) * 0.20
        factors.append(f"Verified byte ratio: {verified_ratio * 100:.2f}%")
        if verified_ratio >= 0.5:
            positive_factors.append("A high proportion of bytes are directly verified.")

    if inferred_ratio is not None:
        score -= min(max(inferred_ratio, 0.0), 1.0) * 0.10
        factors.append(f"Inferred byte ratio: {inferred_ratio * 100:.2f}%")
        if inferred_ratio > 0.2:
            negative_factors.append("A meaningful proportion of bytes are inferred rather than verified.")

    if missing_ratio is not None:
        score -= min(max(missing_ratio, 0.0), 1.0) * 0.20
        factors.append(f"Missing byte ratio: {missing_ratio * 100:.2f}%")
        if missing_ratio > 0.2:
            negative_factors.append("Missing bytes remain in the recovery candidate.")

    if missing_regions:
        gap_count = sum(1 for region in missing_regions if region.get("kind") == "gap")
        if gap_count:
            negative_factors.append(f"{gap_count} storage gap(s) remain between fragments.")
            unresolved_issues.append(f"{gap_count} missing region(s) remain between candidate fragments.")
        overlap_count = sum(1 for region in missing_regions if region.get("kind") == "overlap")
        if overlap_count:
            negative_factors.append(f"{overlap_count} overlapping region(s) were detected.")
            unresolved_issues.append(f"{overlap_count} overlapping region(s) remain unresolved.")

    if contradictions:
        score -= min(len(contradictions) * 0.10, 0.30)
        for issue in contradictions:
            unresolved_issues.append(issue.get("description") or issue.get("type") or "Contradictory evidence was detected.")
            negative_factors.append(f"Contradiction: {issue.get('type', 'unexpected evidence conflict')}")

    if uncertainties:
        score -= min(len(uncertainties) * 0.05, 0.20)
        for issue in uncertainties:
            unresolved_issues.append(issue.get("description") or issue.get("type") or "Evidence remains ambiguous.")
            negative_factors.append(f"Uncertainty: {issue.get('type', 'ambiguous reconstruction evidence')}")

    if evidence_row.get("file_type"):
        factors.append(f"Evidence file type: {evidence_row.get('file_type')}")

    if not positive_factors:
        positive_factors.append("Evidence is technically recoverable but has limited direct support.")

    score = max(0.0, min(score, 1.0))
    if score >= 0.75:
        priority = "HIGH"
    elif score >= 0.45:
        priority = "MEDIUM"
    else:
        priority = "LOW"

    explanation = (
        f"Priority level {priority} was assigned from measured recovery confidence, \
        structural integrity, verified byte coverage, and unresolved evidence issues."
    )

    return {
        "reconstruction_id": reconstruction_id,
        "evidence_id": evidence_id,
        "priority": priority,
        "score": round(score, 4),
        "factors": factors,
        "positive_factors": positive_factors,
        "negative_factors": negative_factors,
        "unresolved_issues": unresolved_issues,
        "explanation": explanation,
    }


def build_evidence_dna(reconstruction_id: str, evidence_id: str, reconstruction: dict):
    connection = get_connection()
    evidence_row = connection.execute(
        "SELECT * FROM evidence WHERE evidence_id = ?",
        (evidence_id,),
    ).fetchone()
    fragments = get_fragments(evidence_id)
    connection.close()

    evidence_data = dict(evidence_row) if evidence_row else {}
    artifact_hash = None
    artifact_path = reconstruction.get("output_path")
    if artifact_path and Path(artifact_path).exists():
        artifact_hash = calculate_sha256(artifact_path)

    entropy_values = [
        float(fragment.get("entropy"))
        for fragment in fragments
        if fragment.get("entropy") is not None
    ]
    metadata_summary = {}
    if evidence_row:
        metadata_summary = {
            "filename": evidence_data.get("filename"),
            "file_type": evidence_data.get("file_type"),
            "extension": evidence_data.get("extension"),
            "size_bytes": evidence_data.get("size_bytes"),
            "sha256": evidence_data.get("sha256"),
        }

    return {
        "evidence_id": evidence_id,
        "reconstruction_id": reconstruction_id,
        "artifact_sha256": artifact_hash,
        "source_evidence_sha256": evidence_data.get("sha256"),
        "file_type": evidence_data.get("file_type") or reconstruction.get("reconstruction_type"),
        "file_size": evidence_data.get("size_bytes") or reconstruction.get("reconstructed_size"),
        "fragment_count": len(fragments),
        "fragment_ids": [fragment.get("fragment_id") for fragment in fragments],
        "fragment_offsets": [fragment.get("offset") for fragment in fragments],
        "entropy_characteristics": {
            "min": min(entropy_values) if entropy_values else None,
            "max": max(entropy_values) if entropy_values else None,
            "mean": (sum(entropy_values) / len(entropy_values)) if entropy_values else None,
            "count": len(entropy_values),
        },
        "metadata_summary": metadata_summary,
        "structural_integrity": reconstruction.get("structural_integrity"),
        "recovery_status": reconstruction.get("status"),
        "recovery_confidence": reconstruction.get("recovery_confidence"),
        "verified_bytes": reconstruction.get("verified_bytes"),
        "inferred_bytes": reconstruction.get("inferred_bytes"),
        "missing_bytes": reconstruction.get("missing_bytes"),
        "created_at": evidence_data.get("created_at"),
    }


def build_evidence_provenance(reconstruction_id: str, evidence_id: str, reconstruction: dict):
    connection = get_connection()
    evidence_row = connection.execute(
        "SELECT * FROM evidence WHERE evidence_id = ?",
        (evidence_id,),
    ).fetchone()
    fragments = get_fragments(evidence_id)
    relationship_rows = get_fragment_relationships(evidence_id)
    connection.close()

    if not evidence_row:
        return {
            "provenance_id": None,
            "evidence_id": evidence_id,
            "reconstruction_id": reconstruction_id,
            "nodes": [],
            "edges": [],
            "explanation": "No original evidence record is available for provenance assembly.",
        }

    evidence = dict(evidence_row)
    fragment_ids = [fragment.get("fragment_id") for fragment in fragments]
    relationship_ids = [relationship.get("relationship_id") for relationship in relationship_rows if relationship.get("relationship_id")]

    graph_nodes = [
        {"id": evidence_id, "type": "evidence", "label": evidence.get("filename")},
    ]
    graph_edges = [
        {"source": evidence_id, "target": fragment_id, "relation": "CONTAINS"}
        for fragment_id in fragment_ids
    ]

    for fragment in fragments:
        fragment_id = fragment.get("fragment_id")
        if fragment_id:
            graph_nodes.append({"id": fragment_id, "type": "fragment", "label": fragment_id})

    for relation in relationship_rows:
        relation_id = relation.get("relationship_id")
        if relation_id:
            graph_nodes.append({"id": relation_id, "type": "relationship", "label": relation_id})
            graph_edges.append({"source": relation.get("fragment_a_id"), "target": relation_id, "relation": "RELATED_TO"})
            graph_edges.append({"source": relation.get("fragment_b_id"), "target": relation_id, "relation": "RELATED_TO"})

    validation_id = f"VALIDATION-{reconstruction_id}"
    artifact_id = f"ARTIFACT-{reconstruction_id}"
    graph_nodes.append({"id": reconstruction_id, "type": "reconstruction", "label": reconstruction_id})
    graph_nodes.append({"id": validation_id, "type": "validation", "label": reconstruction.get("status") or "validation"})
    graph_nodes.append({"id": artifact_id, "type": "recovered artifact", "label": reconstruction.get("output_filename") or artifact_id})

    for fragment_id in fragment_ids:
        graph_edges.append({"source": fragment_id, "target": validation_id, "relation": "VALIDATED_BY"})

    graph_edges.append({"source": reconstruction_id, "target": validation_id, "relation": "VALIDATED_BY"})
    graph_edges.append({"source": reconstruction_id, "target": artifact_id, "relation": "PRODUCED"})
    graph_edges.append({"source": evidence_id, "target": reconstruction_id, "relation": "USED_IN"})

    provenance_id = f"PV-{uuid4().hex[:8].upper()}"
    provenance_record = {
        "provenance_id": provenance_id,
        "evidence_id": evidence_id,
        "reconstruction_id": reconstruction_id,
        "fragment_ids": fragment_ids,
        "relationship_ids": relationship_ids,
        "validation_result": reconstruction.get("status"),
        "recovery_status": reconstruction.get("status"),
        "confidence_assessment": reconstruction.get("confidence_level") or reconstruction.get("recovery_confidence"),
        "output_path": reconstruction.get("output_path"),
        "output_filename": reconstruction.get("output_filename"),
        "output_sha256": reconstruction.get("sha256"),
        "graph": {"nodes": graph_nodes, "edges": graph_edges},
        "summary": {
            "original_evidence": evidence_id,
            "fragment_count": len(fragment_ids),
            "relationship_count": len(relationship_ids),
            "reconstruction_id": reconstruction_id,
            "validation_result": reconstruction.get("status"),
            "output_sha256": reconstruction.get("sha256"),
        },
    }

    connection = get_connection()
    connection.execute(
        """
        INSERT OR REPLACE INTO evidence_provenance (
            provenance_id,
            evidence_id,
            reconstruction_id,
            fragment_ids,
            relationship_ids,
            validation_result,
            recovery_status,
            confidence_level,
            output_path,
            output_filename,
            output_sha256,
            graph_json,
            provenance_summary_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            provenance_id,
            evidence_id,
            reconstruction_id,
            json.dumps(fragment_ids),
            json.dumps(relationship_ids),
            reconstruction.get("status"),
            reconstruction.get("status"),
            reconstruction.get("confidence_level"),
            reconstruction.get("output_path"),
            reconstruction.get("output_filename"),
            reconstruction.get("sha256"),
            json.dumps(graph_nodes + graph_edges),
            json.dumps(provenance_record["summary"]),
        ),
    )
    connection.execute(
        """
        INSERT OR REPLACE INTO provenance_events (
            event_id,
            evidence_id,
            reconstruction_id,
            event_type,
            source_id,
            target_id,
            details_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"EVT-{uuid4().hex[:8].upper()}",
            evidence_id,
            reconstruction_id,
            "RECONSTRUCTION_PRODUCED",
            evidence_id,
            reconstruction_id,
            json.dumps({"output_filename": reconstruction.get("output_filename"), "sha256": reconstruction.get("sha256")}),
        ),
    )
    connection.commit()
    connection.close()

    return provenance_record


def get_evidence_provenance(evidence_id: str):
    connection = get_connection()
    rows = connection.execute(
        "SELECT * FROM evidence_provenance WHERE evidence_id = ? ORDER BY created_at DESC",
        (evidence_id,),
    ).fetchall()
    connection.close()
    result = []
    for row in rows:
        item = dict(row)
        item["fragment_ids"] = _parse_json_list(item.get("fragment_ids"))
        item["relationship_ids"] = _parse_json_list(item.get("relationship_ids"))
        item["graph"] = json.loads(item.get("graph_json") or "[]")
        item["summary"] = json.loads(item.get("provenance_summary_json") or "{}")
        item.pop("graph_json", None)
        item.pop("provenance_summary_json", None)
        result.append(item)
    return result


def analyze_fragment_contributions(reconstruction_id: str, evidence_id: str, reconstruction: dict):
    fragments = get_fragments(evidence_id)
    fragment_ids = reconstruction.get("fragment_ids") or []
    fragment_lookup = {fragment["fragment_id"]: fragment for fragment in fragments}

    selected = [fragment_lookup.get(fragment_id) for fragment_id in fragment_ids if fragment_lookup.get(fragment_id)]

    if not selected:
        return {
            "reconstruction_id": reconstruction_id,
            "fragments": [],
            "total_verified_bytes": 0,
            "total_inferred_bytes": 0,
            "total_missing_bytes": 0,
            "overlap_bytes": 0,
            "explanation": "Insufficient evidence",
        }

    ordered = sorted(
        selected,
        key=lambda fragment: (_safe_int(fragment.get("offset"), 0), _safe_int(fragment.get("sample_size"), 0)),
    )

    contributing = []
    total_verified_bytes = 0
    total_inferred_bytes = 0
    overlap_bytes = 0

    for position, fragment in enumerate(ordered, start=1):
        offset = _safe_int(fragment.get("offset"), 0)
        size = _safe_int(fragment.get("sample_size"), 0)
        end_offset = offset + size
        verified_bytes = _safe_int(fragment.get("verified_bytes"), 0)
        inferred_bytes = _safe_int(fragment.get("inferred_bytes"), 0)
        bytes_contributed = max(size, verified_bytes + inferred_bytes)
        total_verified_bytes += verified_bytes
        total_inferred_bytes += inferred_bytes

        contributing.append(
            {
                "fragment_id": fragment.get("fragment_id"),
                "filename": fragment.get("filename"),
                "position": position,
                "offset": offset,
                "end_offset": end_offset,
                "sample_size": size,
                "bytes_contributed": bytes_contributed,
                "verified_bytes": verified_bytes,
                "inferred_bytes": inferred_bytes,
                "relationship_score": None,
                "contribution_start": offset,
                "contribution_end": end_offset,
            }
        )

    for index, previous in enumerate(contributing[:-1]):
        current = contributing[index + 1]
        previous_end = previous["end_offset"]
        current_start = current["offset"]
        overlap = max(0, min(previous_end, current_start) - max(previous["offset"], current_start))
        if overlap > 0:
            overlap_bytes += overlap

    missing_byte_total = _safe_int(reconstruction.get("missing_bytes"), 0)
    return {
        "reconstruction_id": reconstruction_id,
        "fragments": contributing,
        "total_verified_bytes": total_verified_bytes,
        "total_inferred_bytes": total_inferred_bytes,
        "total_missing_bytes": missing_byte_total,
        "overlap_bytes": overlap_bytes,
        "explanation": "Contribution values were derived from actual fragment offsets, sizes, and stored validation metadata.",
    }


def analyze_missing_regions_for_reconstruction(reconstruction_id: str, evidence_id: str, reconstruction: dict):
    fragments = get_fragments(evidence_id)
    ordered = sorted(
        fragments,
        key=lambda fragment: (_safe_int(fragment.get("offset"), 0), _safe_int(fragment.get("sample_size"), 0)),
    )

    missing_regions = []
    for previous, current in zip(ordered, ordered[1:]):
        previous_offset = _safe_int(previous.get("offset"), 0)
        previous_size = _safe_int(previous.get("sample_size"), 0)
        next_offset = _safe_int(current.get("offset"), 0)
        previous_end = previous_offset + previous_size
        if next_offset > previous_end:
            missing_regions.append(
                {
                    "start": previous_end,
                    "end": next_offset,
                    "size": next_offset - previous_end,
                    "reason": "No supplied fragment covers this storage range.",
                    "from_fragment_id": previous.get("fragment_id"),
                    "to_fragment_id": current.get("fragment_id"),
                }
            )
        elif next_offset < previous_end:
            missing_regions.append(
                {
                    "start": next_offset,
                    "end": previous_end,
                    "size": previous_end - next_offset,
                    "reason": "Overlapping ranges were detected between supplied fragments.",
                    "from_fragment_id": previous.get("fragment_id"),
                    "to_fragment_id": current.get("fragment_id"),
                }
            )

    if not missing_regions and not ordered:
        return {
            "reconstruction_id": reconstruction_id,
            "missing_regions": [],
            "explanation": "Insufficient evidence",
        }

    return {
        "reconstruction_id": reconstruction_id,
        "missing_regions": missing_regions,
        "explanation": "Missing regions were derived from actual fragment boundaries using offset + sample_size calculations.",
    }


def analyze_overlaps_for_reconstruction(reconstruction_id: str, evidence_id: str, reconstruction: dict):
    fragments = get_fragments(evidence_id)
    overlaps = []

    for index, first in enumerate(fragments):
        for second in fragments[index + 1:]:
            start_a = _safe_int(first.get("offset"), 0)
            end_a = start_a + _safe_int(first.get("sample_size"), 0)
            start_b = _safe_int(second.get("offset"), 0)
            end_b = start_b + _safe_int(second.get("sample_size"), 0)

            overlap_start = max(start_a, start_b)
            overlap_end = min(end_a, end_b)
            overlap_bytes = max(0, overlap_end - overlap_start)

            if overlap_bytes > 0:
                overlaps.append(
                    {
                        "fragment_a_id": first.get("fragment_id"),
                        "fragment_b_id": second.get("fragment_id"),
                        "overlap_start": overlap_start,
                        "overlap_end": overlap_end,
                        "overlap_bytes": overlap_bytes,
                        "description": "Two supplied fragments claim overlapping storage ranges.",
                    }
                )

    return {
        "reconstruction_id": reconstruction_id,
        "overlaps": overlaps,
        "explanation": "Overlap detection was derived from actual fragment range boundaries.",
    }


def analyze_contradictions_for_reconstruction(reconstruction_id: str, evidence_id: str, reconstruction: dict):
    fragments = get_fragments(evidence_id)
    relationships = get_fragment_relationships(evidence_id)
    contradictions = []

    for overlap in analyze_overlaps_for_reconstruction(reconstruction_id, evidence_id, reconstruction)["overlaps"]:
        if overlap["overlap_bytes"] > 0:
            contradictions.append(
                {
                    "type": "OVERLAPPING_EVIDENCE",
                    "severity": "HIGH",
                    "fragments": [overlap["fragment_a_id"], overlap["fragment_b_id"]],
                    "description": "Candidate fragments overlap the same storage range.",
                }
            )

    for relationship in relationships:
        if relationship.get("relationship") == "No Supported Relationship":
            contradictions.append(
                {
                    "type": "UNSUPPORTED_RELATIONSHIP",
                    "severity": "MEDIUM",
                    "fragments": [relationship.get("fragment_a_id"), relationship.get("fragment_b_id")],
                    "description": "Available evidence does not support a reliable relationship between these candidate fragments.",
                }
            )

    for first in fragments:
        for second in fragments:
            if first["fragment_id"] == second["fragment_id"]:
                continue
            if first.get("file_type") and second.get("file_type") and first.get("file_type") != second.get("file_type"):
                contradictions.append(
                    {
                        "type": "INCOMPATIBLE_FILE_TYPE",
                        "severity": "MEDIUM",
                        "fragments": [first["fragment_id"], second["fragment_id"]],
                        "description": "Candidate fragments do not share the same observed file classification.",
                    }
                )

    return {
        "reconstruction_id": reconstruction_id,
        "contradictions": contradictions,
        "explanation": "Contradictions are limited to evidence-backed conflicts, not ordinary uncertainty.",
    }


def analyze_uncertainties_for_reconstruction(reconstruction_id: str, evidence_id: str, reconstruction: dict):
    fragments = get_fragments(evidence_id)
    uncertainties = []

    if len(fragments) < 2:
        uncertainties.append(
            {
                "type": "INSUFFICIENT_FRAGMENTS",
                "severity": "HIGH",
                "fragments": [fragment.get("fragment_id") for fragment in fragments],
                "description": "Too few fragments are available for reliable ordering and reconstruction.",
            }
        )

    missing = analyze_missing_regions_for_reconstruction(reconstruction_id, evidence_id, reconstruction)["missing_regions"]
    if missing:
        first_missing = missing[0]
        uncertainties.append(
            {
                "type": "MISSING_REGION",
                "severity": "MEDIUM",
                "fragments": [first_missing.get("from_fragment_id"), first_missing.get("to_fragment_id")],
                "description": "A storage gap remains between adjacent fragments and is not covered by supplied evidence.",
            }
        )

    overlaps = analyze_overlaps_for_reconstruction(reconstruction_id, evidence_id, reconstruction)["overlaps"]
    if overlaps:
        first_overlap = overlaps[0]
        uncertainties.append(
            {
                "type": "OVERLAP",
                "severity": "HIGH",
                "fragments": [first_overlap["fragment_a_id"], first_overlap["fragment_b_id"]],
                "description": "Two supplied fragments overlap the same storage range.",
            }
        )

    if not fragments:
        uncertainties.append(
            {
                "type": "UNKNOWN_FILE_BOUNDARIES",
                "severity": "INFO",
                "fragments": [],
                "description": "No fragment metadata is available to establish file boundaries.",
            }
        )

    return {
        "reconstruction_id": reconstruction_id,
        "uncertainties": uncertainties,
        "explanation": "Uncertainty entries reflect actual missing, incomplete, or ambiguous evidence conditions.",
    }


def analyze_evidence_issues(reconstruction_id: str, evidence_id: str, reconstruction: dict):
    missing_analysis = analyze_missing_regions_for_reconstruction(reconstruction_id, evidence_id, reconstruction)
    overlap_analysis = analyze_overlaps_for_reconstruction(reconstruction_id, evidence_id, reconstruction)
    contradiction_analysis = analyze_contradictions_for_reconstruction(reconstruction_id, evidence_id, reconstruction)
    uncertainty_analysis = analyze_uncertainties_for_reconstruction(reconstruction_id, evidence_id, reconstruction)

    evidence_status = "COMPLETE"
    if not reconstruction.get("fragments_used"):
        evidence_status = "INSUFFICIENT"
    elif contradiction_analysis["contradictions"]:
        evidence_status = "CONFLICTING"
    elif uncertainty_analysis["uncertainties"]:
        evidence_status = "AMBIGUOUS"
    elif missing_analysis["missing_regions"]:
        evidence_status = "PARTIALLY_COMPLETE"

    return {
        "reconstruction_id": reconstruction_id,
        "evidence_id": evidence_id,
        "missing_regions": missing_analysis["missing_regions"],
        "overlaps": overlap_analysis["overlaps"],
        "contradictions": contradiction_analysis["contradictions"],
        "uncertainties": uncertainty_analysis["uncertainties"],
        "evidence_status": evidence_status,
        "explanation": "Evidence status is derived from actual detected gaps, overlaps, contradictions, and uncertainty conditions.",
    }
