from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services.image_recovery_service import (
    ImageRecoveryError,
    get_recovered_path,
    restore_image,
)

router = APIRouter(
    prefix="/api/image-recovery",
    tags=["Image Recovery"],
)


@router.post("/run/{evidence_id}")
def run_image_recovery(evidence_id: str):
    try:
        return restore_image(evidence_id)
    except ImageRecoveryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Image recovery failed: {exc}",
        ) from exc


@router.get("/{evidence_id}/preview")
def preview_image_recovery(evidence_id: str):
    try:
        path = get_recovered_path(evidence_id)
    except ImageRecoveryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return FileResponse(
        path=str(path),
        filename=path.name,
        content_disposition_type="inline",
        media_type="image/png",
    )


@router.get("/{evidence_id}/download")
def download_image_recovery(evidence_id: str):
    try:
        path = get_recovered_path(evidence_id)
    except ImageRecoveryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return FileResponse(
        path=str(path),
        filename=path.name,
        content_disposition_type="attachment",
        media_type="image/png",
    )
