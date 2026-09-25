import json

from fastapi import APIRouter, HTTPException

from app.services.copilot_context import build_evidence_context
from app.services.evidence_query_service import query_evidence
from app.services.ollama_service import (
    OllamaError,
    ask_ollama,
    ollama_status,
)

router = APIRouter(prefix="/api/copilot", tags=["Copilot"])



@router.get("/status")
def copilot_status():
    """
    Return the live local Ollama connection/model status.

    This endpoint is intentionally separate from /query so the frontend
    can distinguish:
      - Ollama server online
      - configured model available
      - Ollama unavailable
    """
    try:
        status = ollama_status()

        return {
            "available": bool(status.get("available")),
            "model_available": bool(status.get("model_available")),
            "model": status.get("model"),
            "base_url": status.get("base_url"),
            "models": status.get("models", []),
            "error": status.get("error"),
        }

    except Exception as exc:
        return {
            "available": False,
            "model_available": False,
            "model": None,
            "base_url": None,
            "models": [],
            "error": str(exc),
        }


@router.post("/query")
def copilot_query(payload: dict):
    """
    Evidence Copilot.

    Existing RECOVERAI behaviour is preserved:
      1. Validate evidence/question.
      2. Build the evidence-grounded context.
      3. Use the deterministic evidence engine when appropriate.
      4. Use local Ollama when explicitly enabled.
      5. Return a grounded fallback instead of fabricating evidence.

    `use_ollama` is now actually honoured by the backend.
    """
    payload = payload or {}

    evidence_id = payload.get("evidence_id")
    question = payload.get("question")
    use_ollama = bool(payload.get("use_ollama", False))

    if not evidence_id or not question:
        raise HTTPException(
            status_code=400,
            detail="Evidence ID and question are required.",
        )

    evidence_id = str(evidence_id)
    question = str(question).strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty.",
        )

    try:
        context = build_evidence_context(evidence_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # ------------------------------------------------------------
    # OLLAMA-FIRST MODE
    # ------------------------------------------------------------
    #
    # The frontend checkbox explicitly requests local AI reasoning.
    # Do not silently run the deterministic engine first in this mode.
    #
    if use_ollama:
        try:
            result = ask_ollama(question, context)

            return {
                "answer": result.get("answer", ""),
                "grounded": result.get("grounded", True),
                "source": "ollama",
                "evidence_references": result.get(
                    "evidence_references",
                    [],
                ),
                "limitations": result.get(
                    "limitations",
                    context.get("limitations", []),
                ),
                "model": result.get("model"),
                "ollama_available": True,
                "ollama_error": None,
            }

        except OllamaError as exc:
            # Do not hide the real reason anymore.
            #
            # We still attempt the deterministic engine so Copilot remains
            # useful when the local model has a temporary problem.
            deterministic = query_evidence(
                evidence_id,
                question,
            )

            if (
                deterministic.get("supported")
                and deterministic.get("result") is not None
            ):
                answer = deterministic["result"]

                return {
                    "answer": json.dumps(
                        answer,
                        ensure_ascii=False,
                        default=str,
                    ),
                    "grounded": True,
                    "source": "deterministic-fallback",
                    "evidence_references": deterministic.get(
                        "evidence_references",
                        [],
                    ),
                    "limitations": [
                        *context.get("limitations", []),
                        f"Ollama unavailable: {exc}",
                    ],
                    "model": "deterministic-backend",
                    "ollama_available": False,
                    "ollama_error": str(exc),
                }

            return {
                "answer": (
                    "Insufficient evidence to answer this from the "
                    "current investigation."
                ),
                "grounded": False,
                "source": "fallback",
                "evidence_references": context.get(
                    "evidence_references",
                    [],
                ),
                "limitations": [
                    *context.get("limitations", []),
                    f"Ollama unavailable: {exc}",
                ],
                "model": None,
                "ollama_available": False,
                "ollama_error": str(exc),
            }

    # ------------------------------------------------------------
    # EXISTING DETERMINISTIC MODE
    # ------------------------------------------------------------
    #
    # Preserve the original RECOVERAI behaviour when Ollama is disabled.
    #
    deterministic = query_evidence(
        evidence_id,
        question,
    )

    if (
        deterministic.get("supported")
        and deterministic.get("result") is not None
    ):
        answer = deterministic["result"]

        return {
            "answer": json.dumps(
                answer,
                ensure_ascii=False,
                default=str,
            ),
            "grounded": True,
            "source": "deterministic",
            "evidence_references": deterministic.get(
                "evidence_references",
                [],
            ),
            "limitations": context.get("limitations", []),
            "model": "deterministic-backend",
            "ollama_available": None,
            "ollama_error": None,
        }

    # ------------------------------------------------------------
    # ORIGINAL OLLAMA FALLBACK PATH
    # ------------------------------------------------------------
    #
    # Keep the old behaviour available when deterministic analysis
    # cannot answer a question and the user has not explicitly disabled
    # the AI layer.
    #
    try:
        result = ask_ollama(question, context)

        return {
            "answer": result["answer"],
            "grounded": result.get("grounded", True),
            "source": "ollama",
            "evidence_references": result.get(
                "evidence_references",
                [],
            ),
            "limitations": result.get(
                "limitations",
                context.get("limitations", []),
            ),
            "model": result.get("model"),
            "ollama_available": True,
            "ollama_error": None,
        }

    except OllamaError as exc:
        return {
            "answer": (
                "Insufficient evidence to answer this from the "
                "current investigation."
            ),
            "grounded": False,
            "source": "fallback",
            "evidence_references": context.get(
                "evidence_references",
                [],
            ),
            "limitations": [
                *context.get("limitations", []),
                str(exc),
            ],
            "model": None,
            "ollama_available": False,
            "ollama_error": str(exc),
        }
