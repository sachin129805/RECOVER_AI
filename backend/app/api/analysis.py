import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.core.config import EVIDENCE_DIR
from app.core.database import get_connection
from app.recovery.integrity import validate_candidate
from app.recovery.scanner import scan_binary_file
from app.services.fragment_service import (
    get_fragments,
    save_fragment,
    update_fragment_integrity,
)
from app.services.relationship_service import (
    analyze_fragment_relationships,
    get_fragment_relationships,
)


router = APIRouter(
    prefix="/api/analysis",
    tags=["Analysis"],
)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def clear_previous_analysis(evidence_id: str):
    """
    Remove previous analysis results so rescanning the same evidence is
    deterministic and does not create duplicate fragments or relationships.
    """

    connection = get_connection()

    connection.execute(
        """
        DELETE FROM fragment_relationships
        WHERE evidence_id = ?
        """,
        (evidence_id,),
    )

    connection.execute(
        """
        DELETE FROM fragments
        WHERE evidence_id = ?
        """,
        (evidence_id,),
    )

    connection.commit()
    connection.close()


def get_evidence_record(evidence_id: str):
    connection = get_connection()

    row = connection.execute(
        """
        SELECT
            evidence_id,
            filename,
            size_bytes,
            sha256,
            file_type,
            extension,
            storage_path,
            metadata,
            upload_status
        FROM evidence
        WHERE evidence_id = ?
        """,
        (evidence_id,),
    ).fetchone()

    connection.close()

    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Metadata helpers
# ---------------------------------------------------------------------------

def parse_metadata(evidence_record: dict) -> dict:
    """
    Safely decode stored evidence metadata.

    Metadata is informational. It is never used to fabricate detections.
    """

    raw_metadata = evidence_record.get("metadata")

    if not raw_metadata:
        return {}

    if isinstance(raw_metadata, dict):
        return raw_metadata

    try:
        parsed = json.loads(raw_metadata)

        if isinstance(parsed, dict):
            return parsed

    except (TypeError, ValueError, json.JSONDecodeError):
        pass

    return {}


def determine_scan_mode(
    evidence_record: dict,
    metadata: dict,
) -> str:
    """
    Determine how the evidence should be scanned.

    The mode is derived from stored evidence metadata rather than from
    filenames or hardcoded fragment names.

    Supported modes:

        FILE
            Normal complete evidence file.

        RAW_IMAGE
            Raw storage image / disk image where embedded signatures
            should be searched.

        FRAGMENT_SET
            Evidence consists of supplied fragments. Individual fragments
            are analyzed as candidates rather than being treated as
            complete files.
    """

    explicit_mode = metadata.get("scan_mode")

    if explicit_mode:
        normalized = str(explicit_mode).strip().upper()

        if normalized in {
            "FILE",
            "RAW_IMAGE",
            "FRAGMENT_SET",
        }:
            return normalized

    upload_status = str(
        evidence_record.get("upload_status") or ""
    ).lower()

    if "fragment" in upload_status:
        return "FRAGMENT_SET"

    return "FILE"


# ---------------------------------------------------------------------------
# Fragment-set analysis
# ---------------------------------------------------------------------------

def analyze_fragment_set(
    evidence_id: str,
    evidence_record: dict,
    evidence_directory: Path,
    metadata: dict,
):
    """
    Analyze supplied fragments without assuming their original file type.

    Important:

    A partial fragment must not automatically be called a complete
    recovered file merely because its first bytes happen to contain a
    recognizable signature.
    """

    fragment_definitions = metadata.get("fragments")

    if not isinstance(fragment_definitions, list):
        fragment_definitions = []

    files = [
        path
        for path in evidence_directory.iterdir()
        if path.is_file()
    ]

    if not files:
        raise HTTPException(
            status_code=400,
            detail="No evidence files found.",
        )

    # Index optional acquisition metadata by filename.
    metadata_by_filename = {}

    for item in fragment_definitions:
        if not isinstance(item, dict):
            continue

        filename = item.get("filename")

        if filename:
            metadata_by_filename[str(filename)] = item

    clear_previous_analysis(evidence_id)

    results = []

    for file_path in files:
        file_metadata = metadata_by_filename.get(
            file_path.name,
            {},
        )

        fragment_size = file_path.stat().st_size

        # A fragment is not automatically a complete file.
        # We therefore do not run complete-file structural validation
        # against it.
        detection = {
            "file_type": "Unknown Fragment",
            "mime_type": None,
            "signature": None,
            "offset": file_metadata.get(
                "ground_truth_offset",
                file_metadata.get("offset", 0),
            ),
            "sample_size": fragment_size,
            "entropy": None,
            "classification_confidence": None,
            "fragment_start": file_metadata.get(
                "ground_truth_offset",
                file_metadata.get("offset"),
            ),
            "fragment_end": file_metadata.get(
                "ground_truth_end",
                file_metadata.get("end_offset"),
            ),
            "fragment_size": fragment_size,
            "ground_truth_fragment": bool(
                metadata.get("ground_truth")
            ),
        }

        # Entropy is calculated by the scanner's own implementation when
        # possible. Importing it here avoids duplicating entropy logic.
        from app.recovery.scanner import calculate_entropy

        detection["entropy"] = calculate_entropy(file_path)

        fragment_id = save_fragment(
            evidence_id=evidence_id,
            filename=file_path.name,
            detection=detection,
        )

        validation = {
            "integrity_status": "Partial Fragment",
            "recovery_status": "Candidate Fragment",
            "structural_integrity": None,
            "verified_bytes": 0,
            "inferred_bytes": 0,
            "validation_message": (
                "Evidence is being analyzed as a fragment set. "
                "This fragment is not treated as a complete file. "
                "No complete-file recovery has been verified."
            ),
        }

        update_fragment_integrity(
            fragment_id,
            validation,
        )

        results.append(
            {
                **detection,
                "filename": file_path.name,
                "fragment_id": fragment_id,
                "integrity_status": validation[
                    "integrity_status"
                ],
                "recovery_status": validation[
                    "recovery_status"
                ],
                "structural_integrity": validation[
                    "structural_integrity"
                ],
                "verified_bytes": validation[
                    "verified_bytes"
                ],
                "inferred_bytes": validation[
                    "inferred_bytes"
                ],
                "validation_message": validation[
                    "validation_message"
                ],
            }
        )

    return {
        "evidence_id": evidence_id,
        "status": "Fragment-set analysis completed",
        "analysis_mode": "FRAGMENT_SET",
        "files_scanned": len(files),
        "fragment_count": len(results),
        "ground_truth": bool(
            metadata.get("ground_truth")
        ),
        "results": [
            {
                "filename": item["filename"],
                "detections": [item],
            }
            for item in results
        ],
    }


# ---------------------------------------------------------------------------
# Standard evidence analysis
# ---------------------------------------------------------------------------

def analyze_standard_evidence(
    evidence_id: str,
    evidence_directory: Path,
    scan_mode: str,
):
    """
    Analyze normal evidence files.

    FILE mode:
        Analyze each supplied file as a complete candidate.

    RAW_IMAGE mode:
        Permit embedded signature scanning because raw storage evidence
        can contain multiple recoverable objects.
    """

    files = [
        path
        for path in evidence_directory.iterdir()
        if path.is_file()
    ]

    if not files:
        raise HTTPException(
            status_code=400,
            detail="No evidence files found.",
        )

    clear_previous_analysis(evidence_id)

    all_results = []

    allow_embedded_signatures = scan_mode == "RAW_IMAGE"

    for file_path in files:
        detections = scan_binary_file(
            file_path,
            allow_embedded_signatures=allow_embedded_signatures,
        )

        validated_detections = []

        for detection in detections:
            fragment_id = save_fragment(
                evidence_id=evidence_id,
                filename=file_path.name,
                detection=detection,
            )

            validation = validate_candidate(
                file_path,
                detection,
            )

            recovery_status = validation.get(
                "recovery_status"
            )

            if not recovery_status:
                integrity_status = validation.get(
                    "integrity_status",
                    "",
                )

                if integrity_status == "Structurally Valid":
                    recovery_status = "Verified Recovery"

                elif integrity_status == "Unsupported Validation":
                    recovery_status = "Unable to Validate"

                elif integrity_status:
                    recovery_status = "Partially Recovered"

                else:
                    recovery_status = "Candidate"

                validation["recovery_status"] = recovery_status

            update_fragment_integrity(
                fragment_id,
                validation,
            )

            validated_detections.append(
                {
                    **detection,
                    "fragment_id": fragment_id,
                    "integrity_status": validation.get(
                        "integrity_status"
                    ),
                    "recovery_status": recovery_status,
                    "structural_integrity": validation.get(
                        "structural_integrity"
                    ),
                    "verified_bytes": validation.get(
                        "verified_bytes",
                        0,
                    ),
                    "inferred_bytes": validation.get(
                        "inferred_bytes",
                        0,
                    ),
                    "validation_message": validation.get(
                        "validation_message"
                    ),
                }
            )

        all_results.append(
            {
                "filename": file_path.name,
                "detections": validated_detections,
            }
        )

    total_fragments = sum(
        len(result["detections"])
        for result in all_results
    )

    return {
        "evidence_id": evidence_id,
        "status": "Analysis completed",
        "analysis_mode": scan_mode,
        "files_scanned": len(files),
        "fragment_count": total_fragments,
        "results": all_results,
    }


# ---------------------------------------------------------------------------
# Analysis endpoint
# ---------------------------------------------------------------------------

@router.get("/scan/{evidence_id}")
def run_analysis(evidence_id: str):
    evidence_directory = EVIDENCE_DIR / evidence_id

    if not evidence_directory.exists():
        raise HTTPException(
            status_code=404,
            detail="Evidence not found.",
        )

    evidence_record = get_evidence_record(
        evidence_id
    )

    if not evidence_record:
        raise HTTPException(
            status_code=404,
            detail="Evidence database record not found.",
        )

    metadata = parse_metadata(
        evidence_record
    )

    scan_mode = determine_scan_mode(
        evidence_record,
        metadata,
    )

    if scan_mode == "FRAGMENT_SET":
        return analyze_fragment_set(
            evidence_id=evidence_id,
            evidence_record=evidence_record,
            evidence_directory=evidence_directory,
            metadata=metadata,
        )

    return analyze_standard_evidence(
        evidence_id=evidence_id,
        evidence_directory=evidence_directory,
        scan_mode=scan_mode,
    )


# ---------------------------------------------------------------------------
# Fragment endpoint
# ---------------------------------------------------------------------------

@router.get("/fragments/{evidence_id}")
def list_fragments(evidence_id: str):
    evidence_directory = EVIDENCE_DIR / evidence_id

    if not evidence_directory.exists():
        raise HTTPException(
            status_code=404,
            detail="Evidence not found.",
        )

    fragments = get_fragments(evidence_id)

    return {
        "evidence_id": evidence_id,
        "fragment_count": len(fragments),
        "fragments": fragments,
    }


# ---------------------------------------------------------------------------
# Relationship analysis
# ---------------------------------------------------------------------------

@router.post("/relationships/{evidence_id}")
def analyze_relationships(evidence_id: str):
    evidence_directory = EVIDENCE_DIR / evidence_id

    if not evidence_directory.exists():
        raise HTTPException(
            status_code=404,
            detail="Evidence not found.",
        )

    return analyze_fragment_relationships(
        evidence_id
    )


@router.get("/relationships/{evidence_id}")
def list_relationships(evidence_id: str):
    evidence_directory = EVIDENCE_DIR / evidence_id

    if not evidence_directory.exists():
        raise HTTPException(
            status_code=404,
            detail="Evidence not found.",
        )

    relationships = get_fragment_relationships(
        evidence_id
    )

    return {
        "evidence_id": evidence_id,
        "relationship_count": len(relationships),
        "relationships": relationships,
    }