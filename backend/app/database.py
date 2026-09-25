import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "recoverai.db"


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_database():
    connection = get_connection()

    # Evidence table
    connection.execute("""
        CREATE TABLE IF NOT EXISTS evidence (
            evidence_id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            sha256 TEXT NOT NULL,
            file_type TEXT,
            extension TEXT,
            storage_path TEXT NOT NULL,
            upload_status TEXT NOT NULL,
            metadata TEXT
        )
    """)

    # Fragment table
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
            FOREIGN KEY (evidence_id)
                REFERENCES evidence(evidence_id)
        )
    """)

    connection.commit()
    connection.close()


init_database()