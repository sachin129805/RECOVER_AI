from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analysis import router as analysis_router
from app.api.benchmarks import router as benchmark_router
from app.api.copilot import router as copilot_router
from app.api.evidence import router as evidence_router
from app.api.investigations import (
    router as investigations_router,
)
from app.api.query import router as query_router
from app.api.reconstruction import (
    router as reconstruction_router,
)
from app.api.recovery_comparison import (
    router as recovery_comparison_router,
)
from app.api.regions import router as regions_router

from app.core.database import (
    initialize_database,
)

from app.services.investigation_service import (
    ensure_investigation_schema,
)


# ============================================================
# DATABASE
# ============================================================

initialize_database()
ensure_investigation_schema()


# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(
    title="RECOVERAI Backend",
    description=(
        "AI-Assisted Intelligent Data Recovery "
        "and Digital Evidence Reconstruction"
    ),
    version="0.3.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# ROUTERS
# ============================================================

app.include_router(
    evidence_router
)

app.include_router(
    investigations_router
)

app.include_router(
    analysis_router
)

app.include_router(
    reconstruction_router
)

app.include_router(
    recovery_comparison_router
)

app.include_router(
    copilot_router
)

app.include_router(
    benchmark_router
)

app.include_router(
    regions_router
)

app.include_router(
    query_router
)


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "name": "RECOVERAI",
        "status": "online",
        "version": "0.3.0",
    }


@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "service": "RECOVERAI backend",
    }