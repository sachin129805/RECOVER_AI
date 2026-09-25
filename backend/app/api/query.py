from fastapi import APIRouter, HTTPException

from app.services.evidence_query_service import query_evidence

router = APIRouter(prefix="/api/evidence", tags=["Evidence Query"])


@router.get("/{evidence_id}/query")
def evidence_query(evidence_id: str, question: str | None = None):
    if not question:
        raise HTTPException(status_code=400, detail="A question parameter is required.")
    result = query_evidence(evidence_id, question)
    if not result["supported"]:
        return {"query_type": result["query_type"], "result": None, "supported": False, "evidence_references": result.get("evidence_references", [])}
    return result
