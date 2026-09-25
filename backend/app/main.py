from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analysis import router as analysis_router
from app.api.evidence import router as evidence_router
from app.core.database import initialize_database


initialize_database()


app = FastAPI(
    title="RECOVERAI Backend",
    description=(
        "AI-Assisted Intelligent Data Recovery "
        "and Digital Evidence Reconstruction"
    ),
    version="0.2.0",
)


# Allow the React/Vite frontend to communicate with FastAPI.
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


# API routers
app.include_router(evidence_router)
app.include_router(analysis_router)


@app.get("/")
def root():
    return {
        "name": "RECOVERAI",
        "status": "online",
        "version": "0.2.0",
    }


@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "service": "RECOVERAI backend",
    }