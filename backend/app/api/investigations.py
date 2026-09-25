from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from uuid import uuid4
from datetime import datetime

from app.core.database import get_connection
from app.services.fragment_service import get_fragments
from app.services.relationship_service import (
    analyze_fragment_relationships,
    get_fragment_relationships,
)


router = APIRouter(
    prefix="/api/investigations",
    tags=["Investigations"],
)


class InvestigationCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""
    source: str = ""


class EvidenceAttach(BaseModel):
    evidence_id: str
    role: str = "evidence"


def _row_dict(row):
    return dict(row) if row else None


def _get_investigation(investigation_id: str):
    connection = get_connection()
    row = connection.execute(
        """
        SELECT investigation_id, name, description, source, created_at
        FROM investigations
        WHERE investigation_id = ?
        """,
        (investigation_id,),
    ).fetchone()
    connection.close()
    return _row_dict(row)


def _ensure_investigations_table():
    connection = get_connection()
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS investigations (
            investigation_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            source TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS investigation_evidence (
            investigation_id TEXT NOT NULL,
            evidence_id TEXT NOT NULL,
            role TEXT DEFAULT 'evidence',
            attached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (investigation_id, evidence_id)
        )
        """
    )
    connection.commit()
    connection.close()


_ensure_investigations_table()


@router.post("")
@router.post("/")
def create_investigation(payload: InvestigationCreate):
    investigation_id = f"INV-{uuid4().hex[:8].upper()}"

    connection = get_connection()
    connection.execute(
        """
        INSERT INTO investigations (
            investigation_id, name, description, source
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            investigation_id,
            payload.name.strip(),
            payload.description,
            payload.source,
        ),
    )
    connection.commit()
    connection.close()

    return {
        "investigation_id": investigation_id,
        "name": payload.name.strip(),
        "description": payload.description,
        "source": payload.source,
        "created_at": datetime.utcnow().isoformat(),
        "status": "created",
    }


@router.get("/{investigation_id}")
def get_investigation(investigation_id: str):
    investigation = _get_investigation(investigation_id)

    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found.")

    return investigation


@router.post("/{investigation_id}/evidence")
def attach_evidence(
    investigation_id: str,
    payload: EvidenceAttach,
):
    investigation = _get_investigation(investigation_id)

    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found.")

    connection = get_connection()

    evidence = connection.execute(
        """
        SELECT evidence_id, filename, size_bytes, sha256, file_type,
               extension, storage_path, metadata, upload_status, created_at
        FROM evidence
        WHERE evidence_id = ?
        """,
        (payload.evidence_id,),
    ).fetchone()

    if not evidence:
        connection.close()
        raise HTTPException(status_code=404, detail="Evidence not found.")

    connection.execute(
        """
        INSERT OR REPLACE INTO investigation_evidence (
            investigation_id, evidence_id, role
        )
        VALUES (?, ?, ?)
        """,
        (
            investigation_id,
            payload.evidence_id,
            payload.role,
        ),
    )

    connection.commit()
    connection.close()

    return {
        "investigation_id": investigation_id,
        "evidence_id": payload.evidence_id,
        "role": payload.role,
        "status": "attached",
    }


@router.get("/{investigation_id}/evidence")
def get_investigation_evidence(investigation_id: str):
    investigation = _get_investigation(investigation_id)

    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found.")

    connection = get_connection()

    rows = connection.execute(
        """
        SELECT
            e.evidence_id,
            e.filename,
            e.size_bytes,
            e.sha256,
            e.file_type,
            e.extension,
            e.storage_path,
            e.metadata,
            e.upload_status,
            e.created_at,
            ie.role,
            ie.attached_at
        FROM investigation_evidence ie
        JOIN evidence e
          ON e.evidence_id = ie.evidence_id
        WHERE ie.investigation_id = ?
        ORDER BY ie.attached_at ASC
        """,
        (investigation_id,),
    ).fetchall()

    connection.close()

    return {
        "investigation_id": investigation_id,
        "evidence_count": len(rows),
        "evidence": [dict(row) for row in rows],
    }


@router.post("/{investigation_id}/analyze")
def analyze_investigation(investigation_id: str):
    investigation = _get_investigation(investigation_id)

    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found.")

    connection = get_connection()
    evidence_rows = connection.execute(
        """
        SELECT evidence_id
        FROM investigation_evidence
        WHERE investigation_id = ?
        ORDER BY attached_at ASC
        """,
        (investigation_id,),
    ).fetchall()
    connection.close()

    if not evidence_rows:
        return {
            "investigation_id": investigation_id,
            "status": "No evidence attached",
            "evidence_count": 0,
            "results": [],
        }

    # Analysis is intentionally delegated to the existing evidence-level
    # services/routes. This endpoint returns investigation scope and status;
    # it never invents analysis results.
    results = []

    for row in evidence_rows:
        evidence_id = row["evidence_id"]
        fragments = get_fragments(evidence_id)
        relationships = get_fragment_relationships(evidence_id)

        results.append(
            {
                "evidence_id": evidence_id,
                "fragment_count": len(fragments),
                "relationship_count": len(relationships),
                "status": "Analysis available",
            }
        )

    return {
        "investigation_id": investigation_id,
        "status": "Analysis completed",
        "evidence_count": len(evidence_rows),
        "results": results,
    }


@router.get("/{investigation_id}/fragments")
def investigation_fragments(investigation_id: str):
    investigation = _get_investigation(investigation_id)

    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found.")

    connection = get_connection()
    evidence_rows = connection.execute(
        """
        SELECT evidence_id
        FROM investigation_evidence
        WHERE investigation_id = ?
        ORDER BY attached_at ASC
        """,
        (investigation_id,),
    ).fetchall()
    connection.close()

    fragments = []

    for row in evidence_rows:
        evidence_id = row["evidence_id"]
        for fragment in get_fragments(evidence_id):
            fragments.append(fragment)

    return {
        "investigation_id": investigation_id,
        "fragment_count": len(fragments),
        "fragments": fragments,
    }


@router.post("/{investigation_id}/relationships")
def investigation_relationships_analysis(investigation_id: str):
    investigation = _get_investigation(investigation_id)

    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found.")

    connection = get_connection()
    evidence_rows = connection.execute(
        """
        SELECT evidence_id
        FROM investigation_evidence
        WHERE investigation_id = ?
        ORDER BY attached_at ASC
        """,
        (investigation_id,),
    ).fetchall()
    connection.close()

    results = []

    for row in evidence_rows:
        results.append(
            analyze_fragment_relationships(row["evidence_id"])
        )

    return {
        "investigation_id": investigation_id,
        "evidence_count": len(results),
        "results": results,
    }


@router.get("/{investigation_id}/relationships")
def investigation_relationships(investigation_id: str):
    investigation = _get_investigation(investigation_id)

    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found.")

    connection = get_connection()
    evidence_rows = connection.execute(
        """
        SELECT evidence_id
        FROM investigation_evidence
        WHERE investigation_id = ?
        ORDER BY attached_at ASC
        """,
        (investigation_id,),
    ).fetchall()
    connection.close()

    relationships = []

    for row in evidence_rows:
        evidence_id = row["evidence_id"]
        relationships.extend(get_fragment_relationships(evidence_id))

    return {
        "investigation_id": investigation_id,
        "relationship_count": len(relationships),
        "relationships": relationships,
    }

