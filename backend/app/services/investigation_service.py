import json
from itertools import combinations
from uuid import uuid4

from app.core.database import get_connection


# ============================================================
# INVESTIGATION DATABASE SCHEMA
# ============================================================

def ensure_investigation_schema():
    connection = get_connection()

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS investigations (
            investigation_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            source TEXT,
            status TEXT DEFAULT 'Open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS investigation_evidence (
            investigation_id TEXT NOT NULL,
            evidence_id TEXT NOT NULL,
            role TEXT DEFAULT 'evidence',
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (
                investigation_id,
                evidence_id
            )
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS investigation_relationships (
            relationship_id TEXT PRIMARY KEY,
            investigation_id TEXT NOT NULL,
            fragment_a_id TEXT NOT NULL,
            fragment_b_id TEXT NOT NULL,
            evidence_a_id TEXT NOT NULL,
            evidence_b_id TEXT NOT NULL,
            relationship_score REAL NOT NULL,
            relationship TEXT NOT NULL,
            reasons_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (
                investigation_id,
                fragment_a_id,
                fragment_b_id
            )
        )
        """
    )

    connection.commit()
    connection.close()


# ============================================================
# CREATE INVESTIGATION
# ============================================================

def create_investigation(
    name,
    description=None,
    source=None,
):
    ensure_investigation_schema()

    investigation_id = (
        f"INV-{uuid4().hex[:8].upper()}"
    )

    connection = get_connection()

    connection.execute(
        """
        INSERT INTO investigations (
            investigation_id,
            name,
            description,
            source
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            investigation_id,
            name,
            description or "",
            source or "Digital Evidence",
        ),
    )

    connection.commit()
    connection.close()

    return get_investigation(
        investigation_id
    )


# ============================================================
# GET INVESTIGATION
# ============================================================

def get_investigation(
    investigation_id,
):
    ensure_investigation_schema()

    connection = get_connection()

    row = connection.execute(
        """
        SELECT *
        FROM investigations
        WHERE investigation_id = ?
        """,
        (investigation_id,),
    ).fetchone()

    connection.close()

    return dict(row) if row else None


# ============================================================
# ATTACH EVIDENCE
# ============================================================

def attach_evidence(
    investigation_id,
    evidence_id,
    role="evidence",
):
    ensure_investigation_schema()

    connection = get_connection()

    investigation = connection.execute(
        """
        SELECT investigation_id
        FROM investigations
        WHERE investigation_id = ?
        """,
        (investigation_id,),
    ).fetchone()

    evidence = connection.execute(
        """
        SELECT evidence_id
        FROM evidence
        WHERE evidence_id = ?
        """,
        (evidence_id,),
    ).fetchone()

    if not investigation:
        connection.close()

        raise ValueError(
            "Investigation not found."
        )

    if not evidence:
        connection.close()

        raise ValueError(
            "Evidence not found."
        )

    connection.execute(
        """
        INSERT OR IGNORE INTO
        investigation_evidence (
            investigation_id,
            evidence_id,
            role
        )
        VALUES (?, ?, ?)
        """,
        (
            investigation_id,
            evidence_id,
            role,
        ),
    )

    connection.execute(
        """
        UPDATE investigations
        SET updated_at = CURRENT_TIMESTAMP
        WHERE investigation_id = ?
        """,
        (investigation_id,),
    )

    connection.commit()
    connection.close()

    return True


# ============================================================
# LIST INVESTIGATION EVIDENCE
# ============================================================

def list_investigation_evidence(
    investigation_id,
):
    ensure_investigation_schema()

    connection = get_connection()

    rows = connection.execute(
        """
        SELECT
            e.*,
            ie.role,
            ie.added_at
        FROM investigation_evidence ie
        JOIN evidence e
            ON e.evidence_id = ie.evidence_id
        WHERE ie.investigation_id = ?
        ORDER BY ie.added_at ASC
        """,
        (investigation_id,),
    ).fetchall()

    connection.close()

    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# FRAGMENT RELATIONSHIP SCORING
# ============================================================

def _fragment_score(a, b):
    score = 0.0
    reasons = []
    strong_signals = 0

    type_a = str(
        a.get("file_type") or ""
    ).upper()

    type_b = str(
        b.get("file_type") or ""
    ).upper()

    signature_a = str(
        a.get("signature") or ""
    ).lower()

    signature_b = str(
        b.get("signature") or ""
    ).lower()


    # --------------------------------------------------------
    # FILE TYPE
    # --------------------------------------------------------

    if (
        type_a
        and type_b
        and type_a != "UNKNOWN FRAGMENT"
        and type_a == type_b
    ):
        score += 0.25

        reasons.append(
            "Compatible detected file type"
        )

        strong_signals += 1


    # --------------------------------------------------------
    # SIGNATURE
    # --------------------------------------------------------

    if (
        signature_a
        and signature_b
        and signature_a == signature_b
    ):
        score += 0.25

        reasons.append(
            "Matching file signature"
        )

        strong_signals += 1


    # --------------------------------------------------------
    # ENTROPY
    # --------------------------------------------------------

    entropy_a = a.get("entropy")
    entropy_b = b.get("entropy")

    if (
        entropy_a is not None
        and entropy_b is not None
    ):
        difference = abs(
            float(entropy_a)
            - float(entropy_b)
        )

        if difference <= 0.15:
            score += 0.20

            reasons.append(
                "Very similar byte entropy"
            )

            strong_signals += 1

        elif difference <= 0.35:
            score += 0.10

            reasons.append(
                "Similar byte entropy"
            )


    # --------------------------------------------------------
    # SIZE
    # --------------------------------------------------------

    size_a = int(
        a.get("sample_size") or 0
    )

    size_b = int(
        b.get("sample_size") or 0
    )

    if size_a and size_b:
        ratio = (
            min(size_a, size_b)
            / max(size_a, size_b)
        )

        if ratio >= 0.85:
            score += 0.15

            reasons.append(
                "Comparable fragment size"
            )

        elif ratio >= 0.60:
            score += 0.05

            reasons.append(
                "Partially comparable fragment size"
            )


    # --------------------------------------------------------
    # FRAGMENT-LIKE STATUS
    # --------------------------------------------------------

    status_a = str(
        a.get("recovery_status") or ""
    ).lower()

    status_b = str(
        b.get("recovery_status") or ""
    ).lower()

    fragment_like = any(
        token in status_a
        or token in status_b
        for token in (
            "candidate fragment",
            "partial fragment",
            "inferred",
        )
    )

    if fragment_like:
        score += 0.20

        reasons.append(
            "Evidence is represented as a fragment candidate"
        )

        strong_signals += 1


    score = min(
        score,
        1.0,
    )


    # --------------------------------------------------------
    # DO NOT FABRICATE RELATIONSHIPS
    # --------------------------------------------------------

    if (
        strong_signals < 2
        or score < 0.60
    ):
        return None

    return (
        round(score, 4),
        reasons,
    )


# ============================================================
# INVESTIGATION-LEVEL RELATIONSHIP ANALYSIS
# ============================================================

def analyze_investigation_relationships(
    investigation_id,
):
    ensure_investigation_schema()

    evidence = list_investigation_evidence(
        investigation_id
    )

    evidence_ids = [
        item["evidence_id"]
        for item in evidence
    ]

    if len(evidence_ids) < 2:
        return {
            "investigation_id": investigation_id,
            "evidence_count": len(
                evidence_ids
            ),
            "fragment_count": 0,
            "relationship_count": 0,
            "relationships": [],
            "status":
                "Insufficient evidence artifacts",
            "message":
                "At least two evidence artifacts are required for cross-evidence relationship analysis.",
        }


    connection = get_connection()

    placeholders = ",".join(
        "?"
        for _ in evidence_ids
    )

    rows = connection.execute(
        f"""
        SELECT *
        FROM fragments
        WHERE evidence_id IN (
            {placeholders}
        )
        ORDER BY evidence_id, offset
        """,
        evidence_ids,
    ).fetchall()

    fragments = [
        dict(row)
        for row in rows
    ]

    evidence_by_id = {
        item["evidence_id"]: item
        for item in evidence
    }


    # Remove previous investigation-level
    # relationship results.

    connection.execute(
        """
        DELETE FROM
        investigation_relationships
        WHERE investigation_id = ?
        """,
        (investigation_id,),
    )


    relationships = []


    # Compare fragments from different
    # evidence artifacts only.

    for a, b in combinations(
        fragments,
        2,
    ):
        if (
            a["evidence_id"]
            == b["evidence_id"]
        ):
            continue

        result = _fragment_score(
            a,
            b,
        )

        if not result:
            continue

        score, reasons = result

        relationship_id = (
            f"REL-{uuid4().hex[:10].upper()}"
        )

        connection.execute(
            """
            INSERT INTO
            investigation_relationships (
                relationship_id,
                investigation_id,
                fragment_a_id,
                fragment_b_id,
                evidence_a_id,
                evidence_b_id,
                relationship_score,
                relationship,
                reasons_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                relationship_id,
                investigation_id,
                a["fragment_id"],
                b["fragment_id"],
                a["evidence_id"],
                b["evidence_id"],
                score,
                "Potential Cross-Evidence Fragment Association",
                json.dumps(reasons),
            ),
        )

        relationships.append(
            {
                "relationship_id":
                    relationship_id,

                "investigation_id":
                    investigation_id,

                "fragment_a_id":
                    a["fragment_id"],

                "fragment_b_id":
                    b["fragment_id"],

                "evidence_a_id":
                    a["evidence_id"],

                "evidence_b_id":
                    b["evidence_id"],

                "evidence_a_filename":
                    evidence_by_id[
                        a["evidence_id"]
                    ]["filename"],

                "evidence_b_filename":
                    evidence_by_id[
                        b["evidence_id"]
                    ]["filename"],

                "relationship_score":
                    score,

                "relationship":
                    "Potential Cross-Evidence Fragment Association",

                "reasons":
                    reasons,
            }
        )


    connection.commit()
    connection.close()


    relationships.sort(
        key=lambda item:
            item["relationship_score"],
        reverse=True,
    )


    return {
        "investigation_id":
            investigation_id,

        "evidence_count":
            len(evidence_ids),

        "fragment_count":
            len(fragments),

        "relationship_count":
            len(relationships),

        "relationships":
            relationships,

        "status":
            "Relationship analysis completed",
    }


# ============================================================
# GET INVESTIGATION RELATIONSHIPS
# ============================================================

def get_investigation_relationships(
    investigation_id,
):
    ensure_investigation_schema()

    connection = get_connection()

    rows = connection.execute(
        """
        SELECT
            r.*,
            ea.filename AS evidence_a_filename,
            eb.filename AS evidence_b_filename
        FROM investigation_relationships r
        JOIN evidence ea
            ON ea.evidence_id =
               r.evidence_a_id
        JOIN evidence eb
            ON eb.evidence_id =
               r.evidence_b_id
        WHERE r.investigation_id = ?
        ORDER BY r.relationship_score DESC
        """,
        (investigation_id,),
    ).fetchall()

    connection.close()


    result = []

    for row in rows:
        item = dict(row)

        try:
            item["reasons"] = json.loads(
                item.get(
                    "reasons_json"
                ) or "[]"
            )
        except Exception:
            item["reasons"] = []

        result.append(item)

    return result


# ============================================================
# GET ALL FRAGMENTS IN INVESTIGATION
# ============================================================

def get_investigation_fragments(
    investigation_id,
):
    ensure_investigation_schema()

    evidence = list_investigation_evidence(
        investigation_id
    )

    evidence_ids = [
        item["evidence_id"]
        for item in evidence
    ]

    if not evidence_ids:
        return []


    connection = get_connection()

    placeholders = ",".join(
        "?"
        for _ in evidence_ids
    )

    rows = connection.execute(
        f"""
        SELECT
            f.*,
            e.filename AS evidence_filename
        FROM fragments f
        JOIN evidence e
            ON e.evidence_id =
               f.evidence_id
        WHERE f.evidence_id IN (
            {placeholders}
        )
        ORDER BY
            e.filename,
            f.offset
        """,
        evidence_ids,
    ).fetchall()

    connection.close()

    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# ANALYZE ENTIRE INVESTIGATION
# ============================================================

def analyze_investigation(
    investigation_id,
):
    ensure_investigation_schema()

    evidence = list_investigation_evidence(
        investigation_id
    )

    if not evidence:
        return {
            "investigation_id":
                investigation_id,

            "status":
                "No evidence artifacts",

            "evidence_count": 0,

            "fragment_count": 0,

            "relationship_count": 0,

            "relationships": [],

            "analysis_results": [],
        }


    # Import here to avoid circular imports
    # during application startup.

    from app.api.analysis import (
        run_analysis,
    )


    analysis_results = []
    failures = []


    for item in evidence:
        evidence_id = item[
            "evidence_id"
        ]

        try:
            result = run_analysis(
                evidence_id
            )

            analysis_results.append(
                result
            )

        except Exception as error:
            failures.append(
                {
                    "evidence_id":
                        evidence_id,

                    "filename":
                        item["filename"],

                    "error":
                        str(error),
                }
            )


    relationship_result = (
        analyze_investigation_relationships(
            investigation_id
        )
    )


    fragment_count = sum(
        int(
            result.get(
                "fragment_count"
            ) or 0
        )
        for result in analysis_results
    )


    return {
        "investigation_id":
            investigation_id,

        "status":
            "Investigation analysis completed",

        "evidence_count":
            len(evidence),

        "fragment_count":
            fragment_count,

        "relationship_count":
            relationship_result.get(
                "relationship_count",
                0,
            ),

        "relationships":
            relationship_result.get(
                "relationships",
                [],
            ),

        "analysis_results":
            analysis_results,

        "failures":
            failures,
    }