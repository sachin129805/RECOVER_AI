import json
from uuid import uuid4

from app.core.database import get_connection


# ============================================================
# FRAGMENT ID
# ============================================================

def generate_fragment_id():
    return f"F-{uuid4().hex[:8].upper()}"


# ============================================================
# SAVE FRAGMENT
# ============================================================

def save_fragment(
    evidence_id,
    filename,
    detection,
):
    fragment_id = generate_fragment_id()

    connection = get_connection()

    connection.execute(
        """
        INSERT INTO fragments (
            fragment_id,
            evidence_id,
            filename,
            file_type,
            mime_type,
            signature,
            offset,
            sample_size,
            entropy,
            classification_confidence,
            integrity_status,
            recovery_status,
            structural_integrity,
            verified_bytes,
            inferred_bytes,
            validation_message
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            fragment_id,
            evidence_id,
            filename,
            detection.get("file_type", "Unknown"),
            detection.get("mime_type"),
            detection.get("signature"),
            detection.get("offset", 0),
            detection.get("sample_size", 0),
            detection.get("entropy"),
            detection.get("classification_confidence"),
            "Pending Validation",
            "Candidate",
            None,
            0,
            0,
            "Structural validation pending.",
        ),
    )

    connection.commit()
    connection.close()

    return fragment_id


# ============================================================
# UPDATE FRAGMENT INTEGRITY
# ============================================================

def update_fragment_integrity(
    fragment_id,
    validation,
):
    """
    Update structural validation results.

    The validation object may contain nested dictionaries.
    SQLite cannot directly store Python dictionaries, so the
    validation message is converted to a readable string.
    """

    if validation is None:
        validation = {}

    integrity_status = validation.get(
        "integrity_status",
        "Unknown"
    )

    recovery_status = validation.get(
        "recovery_status",
        "Candidate"
    )

    structural_integrity = validation.get(
        "structural_integrity",
        0
    )

    verified_bytes = validation.get(
        "verified_bytes",
        0
    )

    inferred_bytes = validation.get(
        "inferred_bytes",
        0
    )

    validation_message = validation.get(
        "validation_message",
        ""
    )

    # --------------------------------------------------------
    # Make sure the validation message is SQLite-safe
    # --------------------------------------------------------

    if isinstance(validation_message, dict):
        validation_message = json.dumps(
            validation_message,
            default=str
        )

    elif isinstance(validation_message, list):
        validation_message = json.dumps(
            validation_message,
            default=str
        )

    elif validation_message is None:
        validation_message = ""

    else:
        validation_message = str(
            validation_message
        )

    connection = get_connection()

    connection.execute(
        """
        UPDATE fragments
        SET
            integrity_status = ?,
            recovery_status = ?,
            structural_integrity = ?,
            verified_bytes = ?,
            inferred_bytes = ?,
            validation_message = ?
        WHERE fragment_id = ?
        """,
        (
            integrity_status,
            recovery_status,
            structural_integrity,
            verified_bytes,
            inferred_bytes,
            validation_message,
            fragment_id,
        ),
    )

    connection.commit()
    connection.close()


# ============================================================
# GET FRAGMENTS
# ============================================================

def get_fragments(evidence_id):

    connection = get_connection()

    rows = connection.execute(
        """
        SELECT
            fragment_id,
            evidence_id,
            filename,
            file_type,
            mime_type,
            signature,
            offset,
            sample_size,
            entropy,
            classification_confidence,
            integrity_status,
            recovery_status,
            structural_integrity,
            verified_bytes,
            inferred_bytes,
            validation_message
        FROM fragments
        WHERE evidence_id = ?
        ORDER BY offset ASC
        """,
        (evidence_id,),
    ).fetchall()

    connection.close()

    return [
        dict(row)
        for row in rows
    ]