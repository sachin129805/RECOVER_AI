import json
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.config import EVIDENCE_DIR
from app.core.database import get_connection
from app.services.hashing import calculate_sha256
from app.services.metadata import extract_metadata


router = APIRouter(
    prefix="/api/evidence",
    tags=["Evidence"],
)


# ============================================================
# NORMAL EVIDENCE UPLOAD
# ============================================================

@router.post("/upload")
async def upload_evidence(file: UploadFile = File(...)):

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No filename provided.",
        )

    evidence_id = f"EVD-{uuid4().hex[:8].upper()}"

    safe_filename = Path(file.filename).name

    evidence_directory = EVIDENCE_DIR / evidence_id

    evidence_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination = evidence_directory / safe_filename

    try:

        with destination.open("wb") as output:

            while True:

                chunk = await file.read(
                    1024 * 1024
                )

                if not chunk:
                    break

                output.write(chunk)

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to store evidence: {error}",
        )

    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    metadata = extract_metadata(
        str(destination)
    )

    # --------------------------------------------------------
    # SHA-256
    # --------------------------------------------------------

    sha256 = calculate_sha256(
        str(destination)
    )

    # --------------------------------------------------------
    # Database
    # --------------------------------------------------------

    connection = get_connection()

    connection.execute(
        """
        INSERT INTO evidence (
            evidence_id,
            filename,
            size_bytes,
            sha256,
            file_type,
            extension,
            storage_path,
            upload_status,
            metadata
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            evidence_id,
            metadata["filename"],
            metadata["size_bytes"],
            sha256,
            metadata["file_type"],
            metadata["extension"],
            str(destination),
            "stored",
            json.dumps(metadata),
        ),
    )

    connection.commit()
    connection.close()

    return {
        "evidence_id": evidence_id,
        "filename": metadata["filename"],
        "size_bytes": metadata["size_bytes"],
        "sha256": sha256,
        "file_type": metadata["file_type"],
        "extension": metadata["extension"],
        "storage_path": str(destination),
        "upload_status": "stored",
        "metadata": {
            "width": metadata.get("width"),
            "height": metadata.get("height"),
            "mode": metadata.get("mode"),
        },
    }


# ============================================================
# IMPORT CONTROLLED DEMO FRAGMENTS
# ============================================================

@router.post("/import-demo-fragments")
def import_demo_fragments():

    demo_directory = (
        Path(__file__).resolve().parents[2]
        / "storage"
        / "demo"
        / "fragmented_pdf"
    )

    ground_truth_path = (
        demo_directory
        / "ground_truth.json"
    )

    if not demo_directory.exists():
        raise HTTPException(
            status_code=404,
            detail="Demo fragment dataset not found.",
        )

    if not ground_truth_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Demo ground truth file not found.",
        )

    # --------------------------------------------------------
    # Load ground truth
    # --------------------------------------------------------

    try:

        ground_truth = json.loads(
            ground_truth_path.read_text(
                encoding="utf-8"
            )
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to read ground truth: {error}",
        )

    fragment_definitions = ground_truth.get(
        "fragments",
        []
    )

    if not fragment_definitions:

        raise HTTPException(
            status_code=400,
            detail="No demo fragments defined.",
        )

    # --------------------------------------------------------
    # Create separate demo evidence ID
    # --------------------------------------------------------

    evidence_id = (
        f"EVD-DEMO-{uuid4().hex[:8].upper()}"
    )

    evidence_directory = (
        EVIDENCE_DIR / evidence_id
    )

    evidence_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    imported_fragments = []

    try:

        for fragment in fragment_definitions:

            filename = fragment["filename"]

            source = demo_directory / filename

            if not source.exists():

                raise FileNotFoundError(
                    f"Missing demo fragment: {filename}"
                )

            destination = (
                evidence_directory / filename
            )

            shutil.copy2(
                source,
                destination
            )

            fragment_hash = calculate_sha256(
                str(destination)
            )

            imported_fragments.append(
                {
                    "filename": filename,
                    "size_bytes": destination.stat().st_size,
                    "sha256": fragment_hash,
                    "ground_truth_offset": fragment.get(
                        "ground_truth_offset"
                    ),
                    "ground_truth_end": fragment.get(
                        "ground_truth_end"
                    ),
                    "storage_path": str(destination),
                }
            )

    except Exception as error:

        # Clean up incomplete demo evidence.
        if evidence_directory.exists():
            shutil.rmtree(
                evidence_directory,
                ignore_errors=True
            )

        raise HTTPException(
            status_code=500,
            detail=f"Failed to import demo fragments: {error}",
        )

    # --------------------------------------------------------
    # Store demo evidence record
    # --------------------------------------------------------

    original_size = ground_truth.get(
        "original_size_bytes",
        0
    )

    original_sha256 = ground_truth.get(
        "source_sha256",
        ""
    )

    metadata = {
        "dataset": "RECOVERAI Controlled Fragmented PDF",
        "source_file": ground_truth.get(
            "source_file"
        ),
        "original_size_bytes": original_size,
        "original_sha256": original_sha256,
        "fragment_count": len(
            imported_fragments
        ),
        "missing_region": ground_truth.get(
            "missing_region"
        ),
        "fragments": imported_fragments,
        "ground_truth": True,
    }

    connection = get_connection()

    connection.execute(
        """
        INSERT INTO evidence (
            evidence_id,
            filename,
            size_bytes,
            sha256,
            file_type,
            extension,
            storage_path,
            upload_status,
            metadata
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            evidence_id,
            ground_truth.get(
                "source_file",
                "fragmented_evidence"
            ),
            original_size,
            original_sha256,
            "PDF",
            ".pdf",
            str(evidence_directory),
            "demo-imported",
            json.dumps(metadata),
        ),
    )

    connection.commit()
    connection.close()

    return {
        "evidence_id": evidence_id,
        "status": "Demo fragments imported",
        "dataset": metadata["dataset"],
        "source_file": metadata["source_file"],
        "original_size_bytes": original_size,
        "fragment_count": len(
            imported_fragments
        ),
        "missing_region": metadata[
            "missing_region"
        ],
        "fragments": imported_fragments,
        "ground_truth": True,
    }