import json

from fastapi import APIRouter, HTTPException

from app.core.database import get_connection
from app.services.recovery_comparison_service import (
    compare_recovery_artifacts,
    get_recovery_comparison_for_evidence,
)

router = APIRouter(prefix="/api/recovery-comparison", tags=["Recovery Comparison"])


@router.post("/{evidence_id}")
def create_recovery_comparison(
    evidence_id: str,
    reconstruction_id: str | None = None,
    source_path: str | None = None,
    recovered_path: str | None = None,
    reference_path: str | None = None,
    reference_evidence_id: str | None = None,
):
    connection = get_connection()
    evidence_row = connection.execute(
        "SELECT evidence_id FROM evidence WHERE evidence_id = ?",
        (evidence_id,),
    ).fetchone()
    connection.close()

    if not evidence_row:
        raise HTTPException(status_code=404, detail="Evidence not found.")

    if reconstruction_id is None:
        connection = get_connection()
        latest = connection.execute(
            "SELECT reconstruction_id, output_path FROM reconstructions WHERE evidence_id = ? ORDER BY created_at DESC LIMIT 1",
            (evidence_id,),
        ).fetchone()
        connection.close()
        if latest:
            reconstruction_id = latest["reconstruction_id"]
            if recovered_path is None:
                recovered_path = latest["output_path"]

    if reference_evidence_id:
        connection = get_connection()
        reference_row = connection.execute(
            "SELECT evidence_id, storage_path FROM evidence WHERE evidence_id = ?",
            (reference_evidence_id,),
        ).fetchone()
        connection.close()
        if reference_row:
            if reference_path is None:
                reference_path = reference_row["storage_path"]

    return compare_recovery_artifacts(
        evidence_id=evidence_id,
        reconstruction_id=reconstruction_id,
        source_path=source_path,
        recovered_path=recovered_path,
        reference_path=reference_path,
        reconstruction={
            "output_path": recovered_path,
            "verified_bytes": 0,
            "inferred_bytes": 0,
            "missing_bytes": 0,
        },
    )


@router.get("/{evidence_id}")
def get_recovery_comparison(evidence_id: str, reconstruction_id: str | None = None):
    connection = get_connection()
    evidence_exists = connection.execute(
        "SELECT evidence_id FROM evidence WHERE evidence_id = ?",
        (evidence_id,),
    ).fetchone()
    connection.close()

    if not evidence_exists:
        raise HTTPException(status_code=404, detail="Evidence not found.")

    results = get_recovery_comparison_for_evidence(evidence_id, reconstruction_id)
    return {
        "evidence_id": evidence_id,
        "reconstruction_id": reconstruction_id,
        "result_count": len(results),
        "results": results,
    }
