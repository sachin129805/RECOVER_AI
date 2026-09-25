import json

from pathlib import Path

from fastapi import (
    APIRouter,
    HTTPException,
)

from fastapi.responses import FileResponse

from app.core.config import RECOVERED_DIR
from app.core.database import get_connection

from app.services.reconstruction_service import (
    analyze_fragment_contributions,
    analyze_evidence_issues,
    build_evidence_dna,
    build_evidence_provenance,
    build_reconstruction_candidate,
    detect_duplicate_evidence,
    evaluate_recovery_priority,
    get_evidence_provenance,
    get_reconstructions_for_evidence,
)


router = APIRouter(
    prefix="/api/reconstruction",
    tags=["Reconstruction"],
)


# ============================================================
# RUN RECONSTRUCTION
# ============================================================

@router.post(
    "/run/{evidence_id}"
)
def run_reconstruction(
    evidence_id: str
):

    connection = get_connection()

    evidence_row = connection.execute(
        """
        SELECT evidence_id
        FROM evidence
        WHERE evidence_id = ?
        """,
        (
            evidence_id,
        ),
    ).fetchone()

    connection.close()

    if not evidence_row:

        raise HTTPException(
            status_code=404,
            detail="Evidence not found.",
        )

    return build_reconstruction_candidate(
        evidence_id
    )


# ============================================================
# GET RECONSTRUCTION RESULTS
# ============================================================

@router.get(
    "/results/{evidence_id}"
)
def get_reconstruction_results(
    evidence_id: str
):

    connection = get_connection()

    evidence_row = connection.execute(
        """
        SELECT evidence_id
        FROM evidence
        WHERE evidence_id = ?
        """,
        (
            evidence_id,
        ),
    ).fetchone()

    connection.close()

    if not evidence_row:

        raise HTTPException(
            status_code=404,
            detail="Evidence not found.",
        )

    results = (
        get_reconstructions_for_evidence(
            evidence_id
        )
    )

    return {
        "evidence_id":
            evidence_id,

        "result_count":
            len(results),

        "results":
            results,
    }


# ============================================================
# INTERNAL RECONSTRUCTION FILE LOOKUP
# ============================================================

def _get_reconstruction_file(
    reconstruction_id: str,
):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT
            reconstruction_id,
            evidence_id,
            output_path,
            output_filename,
            status,
            sha256
        FROM reconstructions
        WHERE reconstruction_id = ?
        """,
        (
            reconstruction_id,
        ),
    ).fetchone()

    connection.close()

    if not row:

        raise HTTPException(
            status_code=404,
            detail="Reconstruction not found.",
        )

    record = dict(row)

    output_path = (
        record.get(
            "output_path"
        )
    )

    if not output_path:

        raise HTTPException(
            status_code=404,
            detail=(
                "This reconstruction "
                "does not contain a "
                "recoverable output artifact."
            ),
        )

    path = Path(
        output_path
    )

    if not path.is_file():

        raise HTTPException(
            status_code=404,
            detail=(
                "Recovered artifact "
                "is not available."
            ),
        )

    try:

        path.resolve().relative_to(
            RECOVERED_DIR.resolve()
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=403,
            detail=(
                "Recovered artifact path "
                "is outside the managed "
                "recovery store."
            ),
        ) from exc

    return record, path


# ============================================================
# PREVIEW RECONSTRUCTED ARTIFACT
# ============================================================

@router.get(
    "/{reconstruction_id}/preview"
)
def preview_reconstruction(
    reconstruction_id: str
):

    record, path = (
        _get_reconstruction_file(
            reconstruction_id
        )
    )

    filename = (
        record.get(
            "output_filename"
        )
        or path.name
    )

    media_type = (
        "application/octet-stream"
    )

    suffix = (
        path.suffix.lower()
    )

    if suffix == ".pdf":
        media_type = "application/pdf"

    elif suffix in (
        ".jpg",
        ".jpeg",
    ):
        media_type = "image/jpeg"

    elif suffix == ".png":
        media_type = "image/png"

    elif suffix == ".gif":
        media_type = "image/gif"

    elif suffix == ".webp":
        media_type = "image/webp"

    elif suffix == ".txt":
        media_type = "text/plain"

    elif suffix == ".json":
        media_type = "application/json"

    elif suffix == ".html":
        media_type = "text/html"

    return FileResponse(
        path=str(path),
        media_type=media_type,
        filename=filename,
        content_disposition_type="inline",
    )


# ============================================================
# DOWNLOAD RECONSTRUCTED ARTIFACT
# ============================================================

@router.get(
    "/{reconstruction_id}/download"
)
def download_reconstruction(
    reconstruction_id: str
):

    record, path = (
        _get_reconstruction_file(
            reconstruction_id
        )
    )

    filename = (
        record.get(
            "output_filename"
        )
        or path.name
    )

    return FileResponse(
        path=str(path),
        media_type=(
            "application/octet-stream"
        ),
        filename=filename,
        content_disposition_type="attachment",
    )


# ============================================================
# ASSESSMENT
# ============================================================

@router.get(
    "/{reconstruction_id}/assessment"
)
def get_reconstruction_assessment(
    reconstruction_id: str
):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT *
        FROM reconstructions
        WHERE reconstruction_id = ?
        """,
        (
            reconstruction_id,
        ),
    ).fetchone()

    connection.close()

    if not row:

        raise HTTPException(
            status_code=404,
            detail="Reconstruction not found.",
        )

    item = dict(row)

    item["fragment_ids"] = json.loads(
        item.get(
            "fragment_ids"
        ) or "[]"
    )

    item["missing_regions"] = json.loads(
        item.get(
            "missing_regions"
        ) or "[]"
    )

    item["reasons"] = json.loads(
        item.get(
            "reasons_json"
        ) or "[]"
    )

    item["confidence_factors"] = json.loads(
        item.get(
            "confidence_factors_json"
        ) or "[]"
    )

    item["feasibility_factors"] = json.loads(
        item.get(
            "feasibility_factors_json"
        ) or "[]"
    )

    item["feasibility_blockers"] = json.loads(
        item.get(
            "feasibility_blockers_json"
        ) or "[]"
    )

    item["supporting_evidence"] = json.loads(
        item.get(
            "feasibility_supporting_evidence_json"
        ) or "[]"
    )

    return item


# ============================================================
# CONTRIBUTIONS
# ============================================================

@router.get(
    "/{reconstruction_id}/contributions"
)
def get_reconstruction_contributions(
    reconstruction_id: str
):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT *
        FROM reconstructions
        WHERE reconstruction_id = ?
        """,
        (
            reconstruction_id,
        ),
    ).fetchone()

    connection.close()

    if not row:

        raise HTTPException(
            status_code=404,
            detail="Reconstruction not found.",
        )

    reconstruction = dict(row)

    return analyze_fragment_contributions(
        reconstruction_id=
            reconstruction_id,

        evidence_id=
            reconstruction[
                "evidence_id"
            ],

        reconstruction=
            reconstruction,
    )


# ============================================================
# EVIDENCE ANALYSIS
# ============================================================

@router.get(
    "/{reconstruction_id}/evidence-analysis"
)
def get_reconstruction_evidence_analysis(
    reconstruction_id: str
):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT *
        FROM reconstructions
        WHERE reconstruction_id = ?
        """,
        (
            reconstruction_id,
        ),
    ).fetchone()

    connection.close()

    if not row:

        raise HTTPException(
            status_code=404,
            detail="Reconstruction not found.",
        )

    reconstruction = dict(row)

    return analyze_evidence_issues(
        reconstruction_id=
            reconstruction_id,

        evidence_id=
            reconstruction[
                "evidence_id"
            ],

        reconstruction=
            reconstruction,
    )


# ============================================================
# PRIORITY
# ============================================================

@router.get(
    "/{reconstruction_id}/priority"
)
def get_reconstruction_priority(
    reconstruction_id: str
):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT *
        FROM reconstructions
        WHERE reconstruction_id = ?
        """,
        (
            reconstruction_id,
        ),
    ).fetchone()

    connection.close()

    if not row:

        raise HTTPException(
            status_code=404,
            detail="Reconstruction not found.",
        )

    reconstruction = dict(row)

    evidence_analysis = (
        analyze_evidence_issues(
            reconstruction_id=
                reconstruction_id,

            evidence_id=
                reconstruction[
                    "evidence_id"
                ],

            reconstruction=
                reconstruction,
        )
    )

    return evaluate_recovery_priority(
        reconstruction_id=
            reconstruction_id,

        evidence_id=
            reconstruction[
                "evidence_id"
            ],

        reconstruction=
            reconstruction,

        evidence_analysis=
            evidence_analysis,
    )


# ============================================================
# EVIDENCE DNA
# ============================================================

@router.get(
    "/{reconstruction_id}/dna"
)
def get_reconstruction_dna(
    reconstruction_id: str
):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT *
        FROM reconstructions
        WHERE reconstruction_id = ?
        """,
        (
            reconstruction_id,
        ),
    ).fetchone()

    connection.close()

    if not row:

        raise HTTPException(
            status_code=404,
            detail="Reconstruction not found.",
        )

    reconstruction = dict(row)

    return build_evidence_dna(
        reconstruction_id=
            reconstruction_id,

        evidence_id=
            reconstruction[
                "evidence_id"
            ],

        reconstruction=
            reconstruction,
    )


# ============================================================
# PROVENANCE
# ============================================================

@router.get(
    "/{reconstruction_id}/provenance"
)
def get_reconstruction_provenance(
    reconstruction_id: str
):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT *
        FROM reconstructions
        WHERE reconstruction_id = ?
        """,
        (
            reconstruction_id,
        ),
    ).fetchone()

    connection.close()

    if not row:

        raise HTTPException(
            status_code=404,
            detail="Reconstruction not found.",
        )

    reconstruction = dict(row)

    return build_evidence_provenance(
        reconstruction_id=
            reconstruction_id,

        evidence_id=
            reconstruction[
                "evidence_id"
            ],

        reconstruction=
            reconstruction,
    )


# ============================================================
# DUPLICATE EVIDENCE
# ============================================================

@router.get(
    "/evidence/{evidence_id}/duplicates"
)
def get_duplicate_evidence(
    evidence_id: str
):

    return detect_duplicate_evidence(
        evidence_id
    )


# ============================================================
# EVIDENCE PROVENANCE
# ============================================================

@router.get(
    "/evidence/{evidence_id}/provenance"
)
def get_evidence_provenance_by_id(
    evidence_id: str
):

    return get_evidence_provenance(
        evidence_id
    )