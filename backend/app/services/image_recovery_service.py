import hashlib
import json
from pathlib import Path

from PIL import Image

from app.core.config import STORAGE_DIR
from app.core.database import get_connection


IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"
}


class ImageRecoveryError(Exception):
    pass


_LAMA = None


def _get_evidence(evidence_id: str):
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT evidence_id, filename, storage_path, size_bytes, sha256,
                   extension, file_type
            FROM evidence
            WHERE evidence_id = ?
            """,
            (evidence_id,),
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        raise ImageRecoveryError(f"Evidence not found: {evidence_id}")

    path = Path(row["storage_path"]).resolve()
    if not path.exists() or not path.is_file():
        raise ImageRecoveryError("Stored evidence file is unavailable.")

    extension = (row["extension"] or path.suffix).lower()
    if extension not in IMAGE_EXTENSIONS:
        raise ImageRecoveryError(
            "AI image restoration is only available for image evidence."
        )

    return dict(row), path


def _sha256(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _get_lama():
    global _LAMA

    if _LAMA is not None:
        return _LAMA

    try:
        from simple_lama_inpainting import SimpleLama
    except ImportError as exc:
        raise ImageRecoveryError(
            "LaMa AI restoration is not installed. "
            "Install simple-lama-inpainting in the backend virtual environment."
        ) from exc

    try:
        _LAMA = SimpleLama()
    except Exception as exc:
        raise ImageRecoveryError(
            f"LaMa model could not be loaded: {exc}"
        ) from exc

    return _LAMA


def _build_corruption_mask(source: Path):
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise ImageRecoveryError(
            "OpenCV and NumPy are required for corruption-mask detection."
        ) from exc

    image = cv2.imread(str(source), cv2.IMREAD_COLOR)
    if image is None:
        raise ImageRecoveryError("The evidence image could not be decoded.")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape

    # Local discontinuity detector. Glitch blocks and broken scan lines tend
    # to have much stronger local differences than ordinary photographic
    # texture.
    smooth = cv2.GaussianBlur(gray, (0, 0), 3)
    local_difference = cv2.absdiff(gray, smooth)
    mask = np.where(local_difference > 48, 255, 0).astype(np.uint8)

    # Detect long horizontal/vertical corruption bands.
    horizontal_score = np.mean(local_difference > 38, axis=1)
    vertical_score = np.mean(local_difference > 38, axis=0)

    row_mask = np.zeros_like(gray, dtype=np.uint8)
    col_mask = np.zeros_like(gray, dtype=np.uint8)

    row_mask[horizontal_score > 0.16, :] = 255
    col_mask[:, vertical_score > 0.20] = 255

    # Dilate narrow detections so LaMa receives a coherent missing region.
    row_mask = cv2.dilate(row_mask, np.ones((9, 1), np.uint8), iterations=1)
    col_mask = cv2.dilate(col_mask, np.ones((1, 7), np.uint8), iterations=1)

    mask = cv2.bitwise_or(mask, row_mask)
    mask = cv2.bitwise_or(mask, col_mask)

    # Detect extreme glitch pixels that strongly disagree with a local median.
    median = cv2.medianBlur(gray, 9)
    median_difference = cv2.absdiff(gray, median)
    extreme = ((gray < 10) | (gray > 247)).astype(np.uint8) * 255
    extreme_mask = np.where(
        (extreme > 0) & (median_difference > 45),
        255,
        0,
    ).astype(np.uint8)
    mask = cv2.bitwise_or(mask, extreme_mask)

    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    mask = cv2.dilate(mask, np.ones((5, 5), np.uint8), iterations=1)

    damage_ratio = float(np.count_nonzero(mask)) / float(mask.size)

    # Prevent a detector failure from asking the model to regenerate almost
    # the entire photograph.
    if damage_ratio > 0.55:
        mask = cv2.erode(mask, np.ones((5, 5), np.uint8), iterations=1)
        damage_ratio = float(np.count_nonzero(mask)) / float(mask.size)

    return image, mask, damage_ratio


def _restore_with_lama(source: Path, target: Path, mask_path: Path):
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise ImageRecoveryError(
            "OpenCV and NumPy are required for LaMa preprocessing."
        ) from exc

    image_bgr, mask, damage_ratio = _build_corruption_mask(source)
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

    # LaMa works on PIL RGB images and binary masks.
    image_pil = Image.fromarray(image_rgb).convert("RGB")
    mask_pil = Image.fromarray(mask).convert("L")

    lama = _get_lama()
    result = lama(image_pil, mask_pil).convert("RGB")

    # Preserve every pixel outside the detected damage mask. This makes the
    # restoration an explicit repair of detected corruption rather than a
    # wholesale regeneration of the evidence image.
    # np.asarray(PIL image) may return a read-only view; LaMa output must be writable.
    result_np = np.array(result, dtype=np.uint8, copy=True)
    original_np = np.asarray(image_pil, dtype=np.uint8)
    clean = mask == 0
    result_np[clean] = original_np[clean]

    output = Image.fromarray(result_np, mode="RGB")
    target.parent.mkdir(parents=True, exist_ok=True)
    output.save(target, format="PNG", optimize=True)

    Image.fromarray(mask).save(mask_path, format="PNG")

    return {
        "width": int(image_bgr.shape[1]),
        "height": int(image_bgr.shape[0]),
        "damaged_pixels": int(np.count_nonzero(mask)),
        "damage_ratio": round(damage_ratio * 100, 2),
        "method": "LaMa neural image inpainting with automatic OpenCV corruption-mask detection",
        "model": "LaMa (Resolution-robust Large Mask Inpainting, WACV 2022)",
    }


def restore_image(evidence_id: str):
    evidence, source = _get_evidence(evidence_id)

    output_dir = (
        Path(STORAGE_DIR)
        / "recovered"
        / "ai_inferred"
        / evidence_id
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_stem = Path(evidence["filename"]).stem
    target = output_dir / f"{safe_stem}_LAMA_INFERRED.png"
    mask_path = output_dir / f"{safe_stem}_CORRUPTION_MASK.png"

    metadata = _restore_with_lama(source, target, mask_path)

    source_sha = evidence["sha256"] or _sha256(source)
    output_sha = _sha256(target)
    output_size = target.stat().st_size

    # This is intentionally a heuristic engineering indicator, not a forensic
    # probability or claim that the generated pixels match the original.
    recovery_confidence = max(
        0.0,
        min(
            100.0,
            round(100.0 - metadata["damage_ratio"] * 0.55, 1),
        ),
    )

    metadata_path = target.with_suffix(".json")
    metadata_path.write_text(
        json.dumps(
            {
                "evidence_id": evidence_id,
                "source_filename": evidence["filename"],
                "source_sha256": source_sha,
                "output_filename": target.name,
                "output_sha256": output_sha,
                "output_size_bytes": output_size,
                "status": "AI-Inferred Reconstruction",
                "verification": "INFERRED — NOT VERIFIED ORIGINAL DATA",
                "verification_note": (
                    "Generated pixels are model-inferred and are not byte-verified "
                    "against an original reference."
                ),
                "mask_filename": mask_path.name,
                "recovery_confidence": recovery_confidence,
                **metadata,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "evidence_id": evidence_id,
        "status": "AI-Inferred Reconstruction",
        "verification": "INFERRED — NOT VERIFIED ORIGINAL DATA",
        "source_filename": evidence["filename"],
        "source_size_bytes": int(evidence["size_bytes"]),
        "output_filename": target.name,
        "recovered_size_bytes": output_size,
        "verified_bytes": 0,
        "inferred_bytes": output_size,
        "damage_ratio": metadata["damage_ratio"],
        "method": metadata["method"],
        "model": metadata["model"],
        "source_sha256": source_sha,
        "output_sha256": output_sha,
        "mask_filename": mask_path.name,
        "recovery_confidence": recovery_confidence,
        "preview_url": f"/api/image-recovery/{evidence_id}/preview",
        "download_url": f"/api/image-recovery/{evidence_id}/download",
    }


def get_recovered_path(evidence_id: str):
    evidence, _ = _get_evidence(evidence_id)
    target = (
        Path(STORAGE_DIR)
        / "recovered"
        / "ai_inferred"
        / evidence_id
        / f"{Path(evidence['filename']).stem}_LAMA_INFERRED.png"
    )

    if not target.exists():
        raise ImageRecoveryError(
            "No AI-inferred image recovery exists. Run image recovery first."
        )

    return target
