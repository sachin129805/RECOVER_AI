import hashlib
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.database import get_connection
from app.services.hashing import calculate_sha256


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        number = float(value)
        if number != number:
            return default
        return number
    except (TypeError, ValueError):
        return default


def _file_exists(path: str | None) -> bool:
    return bool(path) and Path(path).exists()


def _get_file_size(path: str | None) -> int | None:
    if not _file_exists(path):
        return None
    try:
        return os.path.getsize(path)
    except OSError:
        return None


def _hash_file(path: str | None) -> str | None:
    if not _file_exists(path):
        return None
    try:
        return calculate_sha256(path)
    except OSError:
        return None


def _read_chunk(path: str, start: int, end: int) -> bytes:
    with open(path, "rb") as handle:
        handle.seek(start)
        return handle.read(max(0, end - start))


def _compare_byte_ranges(source_path: str | None, recovered_path: str | None, chunk_size: int = 1024 * 1024) -> tuple[int, int, int]:
    source_exists = _file_exists(source_path)
    recovered_exists = _file_exists(recovered_path)

    if not source_exists or not recovered_exists:
        return 0, 0, 0

    source_size = _get_file_size(source_path) or 0
    recovered_size = _get_file_size(recovered_path) or 0
    total_size = max(source_size, recovered_size)

    identical_bytes = 0
    changed_bytes = 0
    missing_bytes = 0

    for offset in range(0, total_size, chunk_size):
        end = min(offset + chunk_size, total_size)
        source_chunk = b""
        recovered_chunk = b""

        if offset < source_size:
            source_chunk = _read_chunk(source_path, offset, min(source_size, end))
        if offset < recovered_size:
            recovered_chunk = _read_chunk(recovered_path, offset, min(recovered_size, end))

        if len(source_chunk) == 0 and len(recovered_chunk) == 0:
            continue
        if len(source_chunk) == 0 or len(recovered_chunk) == 0:
            missing_bytes += max(len(source_chunk), len(recovered_chunk))
            continue

        if source_chunk == recovered_chunk:
            identical_bytes += len(source_chunk)
        else:
            changed_bytes += len(source_chunk)

    return identical_bytes, changed_bytes, missing_bytes


def _build_reference_record(reference_path: str | None, reference_available: bool = False) -> dict[str, Any]:
    if not reference_available or not _file_exists(reference_path):
        return {
            "available": False,
            "type": None,
            "filename": None,
            "sha256": None,
            "size_bytes": None,
        }

    return {
        "available": True,
        "type": "CONTROLLED_REFERENCE",
        "filename": Path(reference_path).name,
        "sha256": _hash_file(reference_path),
        "size_bytes": _get_file_size(reference_path),
    }


def _build_artifact_record(path: str | None, label: str) -> dict[str, Any]:
    if not _file_exists(path):
        return {"available": False, "type": label, "filename": None, "sha256": None, "size_bytes": None}

    return {
        "available": True,
        "type": label,
        "filename": Path(path).name,
        "sha256": _hash_file(path),
        "size_bytes": _get_file_size(path),
    }


def _status_for_block(start: int, end: int, source_state: str, recovered_state: str, reference_state: str, comparison: str) -> dict[str, Any]:
    return {
        "start": start,
        "end": end,
        "source_status": source_state,
        "recovered_status": recovered_state,
        "reference_status": reference_state,
        "comparison": comparison,
    }


def _build_regions(
    source_path: str | None,
    recovered_path: str | None,
    reference_path: str | None,
    chunk_size: int,
    reference_available: bool,
) -> list[dict[str, Any]]:
    source_size = _get_file_size(source_path) or 0
    recovered_size = _get_file_size(recovered_path) or 0
    reference_size = _get_file_size(reference_path) or 0
    max_size = max(source_size, recovered_size, reference_size)

    if max_size == 0:
        return []

    regions: list[dict[str, Any]] = []
    for start in range(0, max_size, chunk_size):
        end = min(start + chunk_size, max_size)
        source_present = start < source_size
        recovered_present = start < recovered_size
        reference_present = reference_available and start < reference_size

        if reference_available:
            if reference_present and source_present and recovered_present:
                source_chunk = _read_chunk(source_path, start, min(source_size, end))
                recovered_chunk = _read_chunk(recovered_path, start, min(recovered_size, end))
                reference_chunk = _read_chunk(reference_path, start, min(reference_size, end))
                if source_chunk == recovered_chunk == reference_chunk:
                    comparison = "IDENTICAL"
                    recovered_status = "VERIFIED"
                    source_status = "PRESENT"
                    reference_status = "PRESENT"
                elif source_chunk == reference_chunk and recovered_chunk != reference_chunk:
                    comparison = "DIFFERENT"
                    recovered_status = "CHANGED"
                    source_status = "PRESENT"
                    reference_status = "PRESENT"
                else:
                    comparison = "MISSING"
                    recovered_status = "MISSING"
                    source_status = "PRESENT" if source_present else "MISSING"
                    reference_status = "PRESENT"
            elif recovered_present and not source_present and reference_present:
                comparison = "MISSING"
                recovered_status = "MISSING"
                source_status = "MISSING"
                reference_status = "PRESENT"
            elif source_present and not recovered_present and reference_present:
                comparison = "MISSING"
                recovered_status = "MISSING"
                source_status = "PRESENT"
                reference_status = "PRESENT"
            elif recovered_present and not reference_present:
                comparison = "UNKNOWN"
                recovered_status = "UNKNOWN"
                source_status = "PRESENT" if source_present else "UNKNOWN"
                reference_status = "UNAVAILABLE"
            else:
                comparison = "UNKNOWN"
                recovered_status = "UNKNOWN"
                source_status = "UNKNOWN"
                reference_status = "UNKNOWN"
        else:
            if source_present and recovered_present:
                source_chunk = _read_chunk(source_path, start, min(source_size, end))
                recovered_chunk = _read_chunk(recovered_path, start, min(recovered_size, end))
                if source_chunk == recovered_chunk:
                    comparison = "IDENTICAL"
                    recovered_status = "VERIFIED"
                    source_status = "PRESENT"
                    reference_status = "UNAVAILABLE"
                else:
                    comparison = "DIFFERENT"
                    recovered_status = "DIFFERENT"
                    source_status = "PRESENT"
                    reference_status = "UNAVAILABLE"
            elif recovered_present:
                comparison = "MISSING"
                recovered_status = "MISSING"
                source_status = "MISSING"
                reference_status = "UNAVAILABLE"
            elif source_present:
                comparison = "MISSING"
                recovered_status = "MISSING"
                source_status = "PRESENT"
                reference_status = "UNAVAILABLE"
            else:
                comparison = "UNKNOWN"
                recovered_status = "UNKNOWN"
                source_status = "UNKNOWN"
                reference_status = "UNAVAILABLE"

        regions.append(
            _status_for_block(
                start=start,
                end=end,
                source_state=source_status,
                recovered_state=recovered_status,
                reference_state=reference_status,
                comparison=comparison,
            )
        )

    return regions


def summarize_range_statuses(regions: list[dict[str, Any]]) -> dict[str, Any]:
    overlap_count = 0
    overlap_bytes = 0
    for region in regions:
        if region.get("source_status") == "PRESENT" and region.get("recovered_status") in {"VERIFIED", "DIFFERENT"}:
            overlap_count += 1
            overlap_bytes += max(0, int(region.get("end", 0)) - int(region.get("start", 0)))
    return {
        "overlap_count": overlap_count,
        "overlap_bytes": overlap_bytes,
    }


def compare_recovery_artifacts(
    evidence_id: str,
    reconstruction_id: str | None = None,
    source_path: str | None = None,
    recovered_path: str | None = None,
    reference_path: str | None = None,
    reconstruction: dict[str, Any] | None = None,
    chunk_size: int = 1024 * 1024,
) -> dict[str, Any]:
    reconstruction = reconstruction or {}
    if chunk_size <= 0:
        chunk_size = 1024 * 1024

    connection = get_connection()
    evidence_row = connection.execute(
        "SELECT evidence_id, filename, storage_path, sha256, size_bytes FROM evidence WHERE evidence_id = ?",
        (evidence_id,),
    ).fetchone()
    connection.close()

    if evidence_row is not None:
        evidence_data = dict(evidence_row)
        if source_path is None:
            source_path = evidence_data.get("storage_path")
    else:
        evidence_data = {}

    if recovered_path is None:
        recovered_path = reconstruction.get("output_path")

    source_exists = _file_exists(source_path)
    recovered_exists = _file_exists(recovered_path)
    reference_available = bool(reference_path and _file_exists(reference_path))

    source_size_bytes = _get_file_size(source_path) if source_exists else 0
    recovered_size_bytes = _get_file_size(recovered_path) if recovered_exists else 0
    reference_size_bytes = _get_file_size(reference_path) if reference_available else 0

    source_sha256 = _hash_file(source_path) if source_exists else None
    recovered_sha256 = _hash_file(recovered_path) if recovered_exists else None
    reference_sha256 = _hash_file(reference_path) if reference_available else None

    identical_bytes = 0
    changed_bytes = 0
    missing_bytes = _safe_int(reconstruction.get("missing_bytes"), 0)

    if source_exists and recovered_exists:
        overlap_size = min(source_size_bytes, recovered_size_bytes)
        for start in range(0, overlap_size, chunk_size):
            end = min(start + chunk_size, overlap_size)
            source_chunk = _read_chunk(source_path, start, end)
            recovered_chunk = _read_chunk(recovered_path, start, end)
            if source_chunk == recovered_chunk:
                identical_bytes += len(source_chunk)
            else:
                changed_bytes += len(source_chunk)
        if recovered_size_bytes > source_size_bytes:
            changed_bytes += recovered_size_bytes - source_size_bytes
        missing_bytes = max(missing_bytes, max(0, source_size_bytes - identical_bytes - changed_bytes))
    elif source_exists and not recovered_exists:
        missing_bytes = max(missing_bytes, source_size_bytes)
    elif recovered_exists and not source_exists:
        missing_bytes = max(missing_bytes, recovered_size_bytes)

    if reference_available and source_exists and recovered_exists:
        recovered_matches_reference = bool(recovered_sha256 and reference_sha256 and recovered_sha256 == reference_sha256)
        if recovered_sha256 and reference_sha256 and recovered_sha256 != reference_sha256:
            recovered_matches_reference = False
    else:
        recovered_matches_reference = None

    source_artifact = _build_artifact_record(source_path, "source")
    recovered_artifact = _build_artifact_record(recovered_path, "recovered")
    reference = _build_reference_record(reference_path, reference_available)

    if not reference_available:
        comparison_status = "NO_REFERENCE_AVAILABLE"
        if source_exists and recovered_exists:
            comparison_status = "SOURCE_RECONSTRUCTION_COMPARISON"
    else:
        comparison_status = "CONTROLLED_REFERENCE_COMPARISON"
        if recovered_matches_reference is True:
            comparison_status = "RECOVERED_MATCHES_REFERENCE"
        elif recovered_matches_reference is False:
            comparison_status = "RECOVERED_DIFFERS_FROM_REFERENCE"

    coverage_ratio = None
    verified_ratio = None
    inferred_ratio = None
    if reference_available and reference_size_bytes:
        if recovered_size_bytes > 0:
            coverage_ratio = min(recovered_size_bytes / reference_size_bytes, 1.0)
        else:
            coverage_ratio = 0.0
        verified_ratio = (_safe_int(reconstruction.get("verified_bytes"), 0) / reference_size_bytes) if reference_size_bytes else None
        inferred_ratio = (_safe_int(reconstruction.get("inferred_bytes"), 0) / reference_size_bytes) if reference_size_bytes else None
    elif source_size_bytes:
        claimed_coverage = _safe_int(reconstruction.get("verified_bytes"), 0) + _safe_int(reconstruction.get("inferred_bytes"), 0)
        coverage_ratio = min(claimed_coverage / source_size_bytes, 1.0) if source_size_bytes else None
        verified_ratio = (_safe_int(reconstruction.get("verified_bytes"), 0) / source_size_bytes) if source_size_bytes else None
        inferred_ratio = (_safe_int(reconstruction.get("inferred_bytes"), 0) / source_size_bytes) if source_size_bytes else None

    regions = _build_regions(
        source_path=source_path,
        recovered_path=recovered_path,
        reference_path=reference_path,
        chunk_size=chunk_size,
        reference_available=reference_available,
    )

    result = {
        "comparison_id": f"CMP-{uuid4().hex[:8].upper()}",
        "evidence_id": evidence_id,
        "reconstruction_id": reconstruction_id,
        "source": source_artifact,
        "recovered_artifact": recovered_artifact,
        "reference": reference,
        "source_size_bytes": source_size_bytes,
        "recovered_size_bytes": recovered_size_bytes,
        "reference_size_bytes": reference_size_bytes,
        "source_sha256": source_sha256,
        "recovered_sha256": recovered_sha256,
        "reference_sha256": reference_sha256,
        "verified_bytes": _safe_int(reconstruction.get("verified_bytes"), 0),
        "inferred_bytes": _safe_int(reconstruction.get("inferred_bytes"), 0),
        "missing_bytes": missing_bytes,
        "changed_bytes": max(changed_bytes, 0),
        "identical_bytes": identical_bytes,
        "differing_bytes": changed_bytes,
        "overlap_bytes": summarize_range_statuses(regions).get("overlap_bytes", 0),
        "coverage_ratio": coverage_ratio,
        "verified_ratio": verified_ratio,
        "inferred_ratio": inferred_ratio,
        "recovered_matches_reference": recovered_matches_reference,
        "comparison_status": comparison_status,
        "reference_available": reference_available,
        "status": bool(reference_available and recovered_matches_reference is True and recovered_size_bytes > 0 and source_size_bytes > 0),
        "comparison_summary": (
            "Reference artifact unavailable; comparison is limited to source/reconstruction consistency."
            if not reference_available
            else "Recovered bytes were compared against the supplied reference artifact."
        ),
        "regions": regions,
    }

    connection = get_connection()
    connection.execute(
        """
        INSERT INTO recovery_comparisons (
            comparison_id,
            evidence_id,
            reconstruction_id,
            reference_evidence_id,
            source_sha256,
            recovered_sha256,
            reference_sha256,
            source_size_bytes,
            recovered_size_bytes,
            reference_size_bytes,
            verified_bytes,
            inferred_bytes,
            missing_bytes,
            changed_bytes,
            identical_bytes,
            coverage_ratio,
            verified_ratio,
            inferred_ratio,
            reference_available,
            comparison_status,
            regions_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            result["comparison_id"],
            evidence_id,
            reconstruction_id,
            reference_path,
            source_sha256,
            recovered_sha256,
            reference_sha256,
            source_size_bytes,
            recovered_size_bytes,
            reference_size_bytes,
            result["verified_bytes"],
            result["inferred_bytes"],
            result["missing_bytes"],
            result["changed_bytes"],
            result["identical_bytes"],
            coverage_ratio,
            verified_ratio,
            inferred_ratio,
            int(reference_available),
            result["comparison_status"],
            json.dumps(result["regions"]),
        ),
    )
    connection.commit()
    connection.close()

    return result


def get_recovery_comparison_for_evidence(evidence_id: str, reconstruction_id: str | None = None) -> list[dict[str, Any]]:
    connection = get_connection()
    if reconstruction_id:
        rows = connection.execute(
            "SELECT * FROM recovery_comparisons WHERE evidence_id = ? AND reconstruction_id = ? ORDER BY created_at DESC",
            (evidence_id, reconstruction_id),
        ).fetchall()
    else:
        rows = connection.execute(
            "SELECT * FROM recovery_comparisons WHERE evidence_id = ? ORDER BY created_at DESC",
            (evidence_id,),
        ).fetchall()
    connection.close()

    results = []
    for row in rows:
        item = dict(row)
        item["regions"] = json.loads(item.get("regions_json") or "[]")
        item.pop("regions_json", None)
        results.append(item)
    return results
