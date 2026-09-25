import hashlib
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.core.database import get_connection
from app.recovery.integrity import validate_candidate

router = APIRouter(prefix="/api/benchmarks", tags=["Benchmark"])


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
    return bool(path) and Path(path).is_file()


def _hash_file(path: str | None) -> str | None:
    if not _file_exists(path):
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_regions(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        start = _safe_int(item.get("start"), 0)
        end = _safe_int(item.get("end"), start)
        if start < 0:
            start = 0
        if end < start:
            end = start
        normalized.append({"start": start, "end": end})
    return normalized


def _build_missing_region_accuracy(actual_regions: list[dict[str, Any]], ground_truth: list[dict[str, Any]]) -> tuple[float | None, str | None]:
    if not ground_truth:
        return None, "Ground-truth missing regions unavailable."
    actual_set = {(int(item.get("start", 0)), int(item.get("end", item.get("start", 0)))) for item in actual_regions}
    truth_set = {(int(item.get("start", 0)), int(item.get("end", item.get("start", 0)))) for item in ground_truth}
    if not truth_set:
        return None, "Ground-truth missing regions unavailable."
    matches = len(actual_set & truth_set)
    return matches / len(truth_set), None


def _build_relationship_accuracy(actual_relationships: list[dict[str, Any]], ground_truth: list[dict[str, Any]]) -> tuple[float | None, str | None]:
    if not ground_truth:
        return None, "Ground-truth relationships unavailable."
    canonical_actual = {
        (
            str(item.get("fragment_a_id") or ""),
            str(item.get("fragment_b_id") or ""),
            str(item.get("relationship") or ""),
        )
        for item in actual_relationships
        if item.get("fragment_a_id") and item.get("fragment_b_id")
    }
    canonical_expected = {
        (
            str(item.get("fragment_a_id") or ""),
            str(item.get("fragment_b_id") or ""),
            str(item.get("relationship") or ""),
        )
        for item in ground_truth
        if item.get("fragment_a_id") and item.get("fragment_b_id")
    }
    if not canonical_expected:
        return None, "Ground-truth relationships unavailable."
    matches = len(canonical_actual & canonical_expected)
    return matches / len(canonical_expected), None


def _evaluate_reference_match(reference_path: str | None, recovered_path: str | None, chunk_size: int = 1024 * 1024) -> dict[str, Any]:
    if not _file_exists(reference_path) or not _file_exists(recovered_path):
        return {
            "reference_size": 0,
            "recovered_size": 0,
            "correctly_recovered_bytes": 0,
            "incorrectly_recovered_bytes": 0,
            "missing_bytes": 0,
            "precision": None,
            "recall": None,
            "f1": None,
            "coverage": None,
            "exact_sha256_match": False,
        }

    reference_size = os.path.getsize(reference_path)
    recovered_size = os.path.getsize(recovered_path)
    ref_hash = _hash_file(reference_path)
    rec_hash = _hash_file(recovered_path)

    overlap_size = min(reference_size, recovered_size)
    correct = 0
    incorrect = 0
    missing = 0

    for offset in range(0, overlap_size, chunk_size):
        end = min(offset + chunk_size, overlap_size)
        with open(reference_path, "rb") as ref_handle, open(recovered_path, "rb") as rec_handle:
            ref_handle.seek(offset)
            rec_handle.seek(offset)
            ref_chunk = ref_handle.read(end - offset)
            rec_chunk = rec_handle.read(end - offset)
        if ref_chunk == rec_chunk:
            correct += len(ref_chunk)
        else:
            incorrect += len(rec_chunk)
            # bytes absent from recovered artifact are not counted in the overlap, so they are later accounted for by the reference gap.

    if recovered_size > reference_size:
        incorrect += max(0, recovered_size - reference_size)

    missing = max(0, reference_size - correct)

    recovered_bytes = recovered_size
    precision = (correct / recovered_bytes) if recovered_bytes > 0 else None
    recall = (correct / reference_size) if reference_size > 0 else None
    if precision is not None and recall is not None and (precision + recall) > 0:
        f1 = (2 * precision * recall) / (precision + recall)
    else:
        f1 = None
    coverage = recall
    exact_match = bool(ref_hash and rec_hash and ref_hash == rec_hash)

    return {
        "reference_size": reference_size,
        "recovered_size": recovered_size,
        "correctly_recovered_bytes": correct,
        "incorrectly_recovered_bytes": incorrect,
        "missing_bytes": missing,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "coverage": coverage,
        "exact_sha256_match": exact_match,
    }


def _evaluate_benchmark(payload: dict[str, Any]) -> dict[str, Any]:
    reference_path = payload.get("reference_path")
    reconstructed_path = payload.get("reconstructed_path")
    file_type = payload.get("file_type") or payload.get("detected_file_type") or "Unknown"

    if not reconstructed_path:
        raise HTTPException(status_code=400, detail="reconstructed_path is required.")

    if not _file_exists(reconstructed_path):
        raise HTTPException(status_code=404, detail="Recovered artifact not found.")

    evaluation = _evaluate_reference_match(reference_path, reconstructed_path)
    if _file_exists(reference_path) and _file_exists(reconstructed_path):
        reference_size = evaluation["reference_size"]
        recovered_size = evaluation["recovered_size"]
        reference_sha256 = _hash_file(reference_path)
        recovered_sha256 = _hash_file(reconstructed_path)
    else:
        reference_size = 0
        recovered_size = os.path.getsize(reconstructed_path)
        reference_sha256 = None
        recovered_sha256 = _hash_file(reconstructed_path)

    structural = validate_candidate(Path(reconstructed_path), {"file_type": file_type, "offset": 0})
    structural_validity = float(structural.get("structural_integrity", 0.0) / 100.0) if isinstance(structural, dict) else 0.0

    actual_missing = _normalize_regions(payload.get("reconstruction_missing_regions") or payload.get("missing_regions") or [])
    ground_truth_missing = _normalize_regions(payload.get("ground_truth_missing_regions") or [])
    actual_relationships = payload.get("reconstruction_relationships") or payload.get("relationships") or []
    ground_truth_relationships = payload.get("ground_truth_relationships") or []

    if ground_truth_missing:
        missing_region_accuracy, missing_region_reason = _build_missing_region_accuracy(actual_missing, ground_truth_missing)
    else:
        missing_region_accuracy, missing_region_reason = None, "Ground-truth missing regions unavailable."

    if ground_truth_relationships:
        relationship_accuracy, relationship_reason = _build_relationship_accuracy(actual_relationships, ground_truth_relationships)
    else:
        relationship_accuracy, relationship_reason = None, "Ground-truth relationships unavailable."

    return {
        "reference_path": reference_path,
        "reconstructed_path": reconstructed_path,
        "reference_sha256": reference_sha256,
        "recovered_sha256": recovered_sha256,
        "reference_size": reference_size,
        "recovered_size": recovered_size,
        "correctly_recovered_bytes": evaluation["correctly_recovered_bytes"],
        "incorrectly_recovered_bytes": evaluation["incorrectly_recovered_bytes"],
        "missing_bytes": max(_safe_int(payload.get("missing_bytes"), evaluation["missing_bytes"]), evaluation["missing_bytes"]),
        "verified_bytes": _safe_int(payload.get("verified_bytes"), evaluation["correctly_recovered_bytes"]),
        "inferred_bytes": _safe_int(payload.get("inferred_bytes"), 0),
        "precision": _safe_float(payload.get("precision"), evaluation["precision"]),
        "recall": _safe_float(payload.get("recall"), evaluation["recall"]),
        "f1": _safe_float(payload.get("f1"), evaluation["f1"]),
        "coverage": _safe_float(payload.get("coverage"), evaluation["coverage"]),
        "exact_sha256_match": bool(payload.get("exact_sha256_match") if payload.get("exact_sha256_match") is not None else evaluation["exact_sha256_match"]),
        "structural_validity": structural_validity,
        "missing_region_accuracy": missing_region_accuracy,
        "relationship_accuracy": relationship_accuracy,
        "missing_region_reason": missing_region_reason,
        "relationship_reason": relationship_reason,
        "evaluation_status": "completed",
    }


@router.post("/run")
def run_benchmark(payload: dict):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Benchmark payload is required.")

    evidence_id = payload.get("evidence_id")
    reconstructed_path = payload.get("reconstructed_path")
    reference_path = payload.get("reference_path")
    reconstruction_id = payload.get("reconstruction_id")

    if not evidence_id or not reconstructed_path:
        raise HTTPException(status_code=400, detail="evidence_id and reconstructed_path are required.")

    benchmark_id = f"BENCH-{uuid4().hex[:8].upper()}"
    evaluated = _evaluate_benchmark(payload)

    connection = get_connection()
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS benchmark_runs (
            benchmark_id TEXT PRIMARY KEY,
            evidence_id TEXT,
            reconstruction_id TEXT,
            reference_path TEXT,
            reconstructed_path TEXT,
            reference_sha256 TEXT,
            recovered_sha256 TEXT,
            reference_size INTEGER DEFAULT 0,
            recovered_size INTEGER DEFAULT 0,
            correctly_recovered_bytes INTEGER DEFAULT 0,
            incorrectly_recovered_bytes INTEGER DEFAULT 0,
            missing_bytes INTEGER DEFAULT 0,
            verified_bytes INTEGER DEFAULT 0,
            inferred_bytes INTEGER DEFAULT 0,
            precision REAL,
            recall REAL,
            f1 REAL,
            coverage REAL,
            exact_sha256_match INTEGER DEFAULT 0,
            structural_validity REAL,
            missing_region_accuracy REAL,
            relationship_accuracy REAL,
            evaluation_status TEXT DEFAULT 'completed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        INSERT INTO benchmark_runs (
            benchmark_id,
            evidence_id,
            reconstruction_id,
            reference_path,
            reconstructed_path,
            reference_sha256,
            recovered_sha256,
            reference_size,
            recovered_size,
            correctly_recovered_bytes,
            incorrectly_recovered_bytes,
            missing_bytes,
            verified_bytes,
            inferred_bytes,
            precision,
            recall,
            f1,
            coverage,
            exact_sha256_match,
            structural_validity,
            missing_region_accuracy,
            relationship_accuracy,
            evaluation_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            benchmark_id,
            evidence_id,
            reconstruction_id,
            reference_path,
            reconstructed_path,
            evaluated["reference_sha256"],
            evaluated["recovered_sha256"],
            evaluated["reference_size"],
            evaluated["recovered_size"],
            evaluated["correctly_recovered_bytes"],
            evaluated["incorrectly_recovered_bytes"],
            evaluated["missing_bytes"],
            evaluated["verified_bytes"],
            evaluated["inferred_bytes"],
            evaluated["precision"],
            evaluated["recall"],
            evaluated["f1"],
            evaluated["coverage"],
            int(bool(evaluated["exact_sha256_match"])),
            evaluated["structural_validity"],
            evaluated["missing_region_accuracy"],
            evaluated["relationship_accuracy"],
            evaluated["evaluation_status"],
        ),
    )
    connection.commit()
    connection.close()

    response = {"benchmark_id": benchmark_id, "status": "registered", **evaluated}
    return response


@router.get("/{benchmark_id}")
def get_benchmark(benchmark_id: str):
    connection = get_connection()
    row = connection.execute(
        "SELECT * FROM benchmark_runs WHERE benchmark_id = ?",
        (benchmark_id,),
    ).fetchone()
    connection.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Benchmark run not found.")
    return dict(row)


@router.get("/{benchmark_id}/results")
def get_benchmark_results(benchmark_id: str):
    return get_benchmark(benchmark_id)
