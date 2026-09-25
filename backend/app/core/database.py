import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "recoverai.db"


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    connection = get_connection()

    # ---------------------------------------------------------
    # EVIDENCE
    # ---------------------------------------------------------

    connection.execute("""
        CREATE TABLE IF NOT EXISTS evidence (
            evidence_id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            sha256 TEXT NOT NULL,
            file_type TEXT,
            extension TEXT,
            storage_path TEXT NOT NULL,
            metadata TEXT,
            upload_status TEXT DEFAULT 'Uploaded',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ---------------------------------------------------------
    # FRAGMENTS
    # ---------------------------------------------------------

    connection.execute("""
        CREATE TABLE IF NOT EXISTS fragments (
            fragment_id TEXT PRIMARY KEY,
            evidence_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            file_type TEXT NOT NULL,
            mime_type TEXT,
            signature TEXT,
            offset INTEGER NOT NULL,
            sample_size INTEGER NOT NULL,
            entropy REAL,
            classification_confidence REAL,
            integrity_status TEXT,
            recovery_status TEXT,
            structural_integrity REAL,
            verified_bytes INTEGER DEFAULT 0,
            inferred_bytes INTEGER DEFAULT 0,
            validation_message TEXT,
            FOREIGN KEY (evidence_id) REFERENCES evidence(evidence_id)
        )
    """)

    # ---------------------------------------------------------
    # FRAGMENT RELATIONSHIPS
    # ---------------------------------------------------------

    connection.execute("""
        CREATE TABLE IF NOT EXISTS fragment_relationships (
            relationship_id TEXT PRIMARY KEY,
            evidence_id TEXT NOT NULL,
            fragment_a_id TEXT NOT NULL,
            fragment_b_id TEXT NOT NULL,
            relationship_score REAL NOT NULL,
            relationship TEXT NOT NULL,
            reasons TEXT,
            reasons_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (evidence_id) REFERENCES evidence(evidence_id)
        )
    """)

    # ---------------------------------------------------------
    # EVIDENCE MIGRATIONS
    # ---------------------------------------------------------

    evidence_columns = {
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(evidence)"
        ).fetchall()
    }

    evidence_required_columns = {
        "metadata": "TEXT",
        "upload_status": "TEXT DEFAULT 'Uploaded'",
    }

    for column_name, column_type in evidence_required_columns.items():

        if column_name not in evidence_columns:

            connection.execute(
                f"""
                ALTER TABLE evidence
                ADD COLUMN {column_name} {column_type}
                """
            )

    # ---------------------------------------------------------
    # FRAGMENT MIGRATIONS
    # ---------------------------------------------------------

    fragment_columns = {
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(fragments)"
        ).fetchall()
    }

    fragment_required_columns = {
        "integrity_status": "TEXT",
        "recovery_status": "TEXT",
        "structural_integrity": "REAL",
        "verified_bytes": "INTEGER DEFAULT 0",
        "inferred_bytes": "INTEGER DEFAULT 0",
        "validation_message": "TEXT",
        "classification_confidence": "REAL",
    }

    for column_name, column_type in fragment_required_columns.items():

        if column_name not in fragment_columns:

            connection.execute(
                f"""
                ALTER TABLE fragments
                ADD COLUMN {column_name} {column_type}
                """
            )

    # ---------------------------------------------------------
    # RELATIONSHIP MIGRATIONS
    # ---------------------------------------------------------

    relationship_columns = {
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(fragment_relationships)"
        ).fetchall()
    }

    if "reasons" not in relationship_columns:

        connection.execute(
            """
            ALTER TABLE fragment_relationships
            ADD COLUMN reasons TEXT
            """
        )

    if "reasons_json" not in relationship_columns:

        connection.execute(
            """
            ALTER TABLE fragment_relationships
            ADD COLUMN reasons_json TEXT
            """
        )

    connection.commit()
    connection.close()