from io import BytesIO
from pathlib import Path

from PIL import Image


def validate_candidate(file_path: Path, detection: dict) -> dict:
    """
    Validate a detected file-signature candidate.

    This does NOT claim forensic recovery.
    It checks whether the candidate can be structurally
    interpreted as the detected file type.
    """

    file_type = detection.get("file_type", "Unknown")
    offset = int(detection.get("offset", 0))

    try:
        with open(file_path, "rb") as file:
            file.seek(offset)
            candidate_bytes = file.read()

    except Exception as error:
        return {
            "structural_integrity": 0.0,
            "verified_bytes": 0,
            "inferred_bytes": 0,
            "integrity_status": "Validation Error",
            "validation_message": str(error),
        }

    candidate_size = len(candidate_bytes)

    if candidate_size == 0:
        return {
            "structural_integrity": 0.0,
            "verified_bytes": 0,
            "inferred_bytes": 0,
            "integrity_status": "No Data",
            "validation_message": "No candidate bytes available.",
        }

    try:
        # ---------------------------------------------------------
        # JPEG / PNG / GIF / BMP / TIFF
        # ---------------------------------------------------------
        if file_type in {
            "JPEG",
            "PNG",
            "GIF",
            "BMP",
            "TIFF",
        }:
            image = Image.open(BytesIO(candidate_bytes))

            # Force Pillow to actually decode the image.
            image.verify()

            return {
                "structural_integrity": 100.0,
                "verified_bytes": candidate_size,
                "inferred_bytes": 0,
                "integrity_status": "Structurally Valid",
                "validation_message": (
                    f"{file_type} structure validated successfully."
                ),
            }

        # ---------------------------------------------------------
        # PDF
        # ---------------------------------------------------------
        if file_type == "PDF":
            import fitz

            document = fitz.open(
                stream=candidate_bytes,
                filetype="pdf",
            )

            page_count = document.page_count

            document.close()

            if page_count > 0:
                return {
                    "structural_integrity": 100.0,
                    "verified_bytes": candidate_size,
                    "inferred_bytes": 0,
                    "integrity_status": "Structurally Valid",
                    "validation_message": (
                        f"PDF opened successfully with "
                        f"{page_count} page(s)."
                    ),
                }

        # ---------------------------------------------------------
        # ZIP
        # ---------------------------------------------------------
        if file_type == "ZIP":
            import zipfile

            with zipfile.ZipFile(BytesIO(candidate_bytes)) as archive:
                bad_file = archive.testzip()

                if bad_file is None:
                    return {
                        "structural_integrity": 100.0,
                        "verified_bytes": candidate_size,
                        "inferred_bytes": 0,
                        "integrity_status": "Structurally Valid",
                        "validation_message": (
                            "ZIP archive structure validated successfully."
                        ),
                    }

                return {
                    "structural_integrity": 50.0,
                    "verified_bytes": 0,
                    "inferred_bytes": 0,
                    "integrity_status": "Corrupted",
                    "validation_message": (
                        f"ZIP contains a corrupted member: {bad_file}"
                    ),
                }

        # ---------------------------------------------------------
        # Unknown / unsupported type
        # ---------------------------------------------------------
        return {
            "structural_integrity": 0.0,
            "verified_bytes": 0,
            "inferred_bytes": 0,
            "integrity_status": "Unsupported Validation",
            "validation_message": (
                f"No structural validator is available for {file_type}."
            ),
        }

    except Exception as error:

        # The signature exists, but the candidate cannot be
        # structurally decoded as the expected format.
        return {
            "structural_integrity": 0.0,
            "verified_bytes": 0,
            "inferred_bytes": 0,
            "integrity_status": "Corrupted or Incomplete",
            "validation_message": (
                f"{file_type} candidate could not be decoded: {error}"
            ),
        }