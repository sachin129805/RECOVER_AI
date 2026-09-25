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

    if "reasons_json" not in relationship_columns:
        if "reasons" in relationship_columns:
            try:
                connection.execute(
                    """
                    ALTER TABLE fragment_relationships
                    RENAME COLUMN reasons TO reasons_json
                    """
                )
            except sqlite3.OperationalError:
                connection.execute(
                    """
                    ALTER TABLE fragment_relationships
                    ADD COLUMN reasons_json TEXT
                    """
                )
        else:
            connection.execute(
                """
                ALTER TABLE fragment_relationships
                ADD COLUMN reasons_json TEXT
                """
            )

    if "reasons" in relationship_columns and "reasons_json" in relationship_columns:
        connection.execute(
            """
            UPDATE fragment_relationships
            SET reasons_json = COALESCE(reasons_json, reasons)
            WHERE reasons_json IS NULL AND reasons IS NOT NULL
            """
        )

    # ---------------------------------------------------------
    # RECONSTRUCTION MIGRATIONS
    # ---------------------------------------------------------

    connection.execute("""
        CREATE TABLE IF NOT EXISTS reconstructions (
            reconstruction_id TEXT PRIMARY KEY,
            evidence_id TEXT NOT NULL,
            status TEXT NOT NULL,
            reconstruction_type TEXT,
            output_path TEXT,
            output_filename TEXT,
            fragment_ids TEXT,
            missing_regions TEXT,
            reasons_json TEXT,
            verified_bytes INTEGER DEFAULT 0,
            inferred_bytes INTEGER DEFAULT 0,
            missing_bytes INTEGER DEFAULT 0,
            structural_integrity REAL,
            recovery_confidence REAL,
            reconstructed_size INTEGER DEFAULT 0,
            sha256 TEXT,
            priority TEXT,
            priority_score REAL,
            priority_factors_json TEXT,
            positive_factors_json TEXT,
            negative_factors_json TEXT,
            unresolved_issues_json TEXT,
            priority_explanation TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (evidence_id) REFERENCES evidence(evidence_id)
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS evidence_provenance (
            provenance_id TEXT PRIMARY KEY,
            evidence_id TEXT NOT NULL,
            reconstruction_id TEXT,
            fragment_ids TEXT,
            relationship_ids TEXT,
            validation_result TEXT,
            recovery_status TEXT,
            confidence_level TEXT,
            output_path TEXT,
            output_filename TEXT,
            output_sha256 TEXT,
            graph_json TEXT,
            provenance_summary_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (evidence_id) REFERENCES evidence(evidence_id),
            FOREIGN KEY (reconstruction_id) REFERENCES reconstructions(reconstruction_id)
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS provenance_events (
            event_id TEXT PRIMARY KEY,
            evidence_id TEXT,
            reconstruction_id TEXT,
            event_type TEXT NOT NULL,
            source_id TEXT,
            target_id TEXT,
            details_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS recovery_comparisons (
            comparison_id TEXT PRIMARY KEY,
            evidence_id TEXT NOT NULL,
            reconstruction_id TEXT,
            reference_evidence_id TEXT,
            source_sha256 TEXT,
            recovered_sha256 TEXT,
            reference_sha256 TEXT,
            source_size_bytes INTEGER DEFAULT 0,
            recovered_size_bytes INTEGER DEFAULT 0,
            reference_size_bytes INTEGER DEFAULT 0,
            verified_bytes INTEGER DEFAULT 0,
            inferred_bytes INTEGER DEFAULT 0,
            missing_bytes INTEGER DEFAULT 0,
            changed_bytes INTEGER DEFAULT 0,
            identical_bytes INTEGER DEFAULT 0,
            coverage_ratio REAL,
            verified_ratio REAL,
            inferred_ratio REAL,
            reference_available INTEGER DEFAULT 0,
            comparison_status TEXT,
            regions_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (evidence_id) REFERENCES evidence(evidence_id),
            FOREIGN KEY (reconstruction_id) REFERENCES reconstructions(reconstruction_id)
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS benchmark_runs (
            benchmark_id TEXT PRIMARY KEY,
            evidence_id TEXT,
            reconstruction_id TEXT,
            reference_path TEXT,
            reconstructed_path TEXT,
            reference_sha256 TEXT,
            recovered_sha256 TEXT,
            reference_size INTEGER DEFAULT 0,
            recovered_size INTEGER DEFAULT 0,
            correctly_recovered_bytes INTEGER DEFAULT 0,
            incorrectly_recovered_bytes INTEGER DEFAULT 0,
            missing_bytes INTEGER DEFAULT 0,
            verified_bytes INTEGER DEFAULT 0,
            inferred_bytes INTEGER DEFAULT 0,
            precision REAL,
            recall REAL,
            f1 REAL,
            coverage REAL,
            exact_sha256_match INTEGER DEFAULT 0,
            structural_validity REAL,
            missing_region_accuracy REAL,
            relationship_accuracy REAL,
            evaluation_status TEXT DEFAULT 'completed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    reconstruction_columns = {
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(reconstructions)"
        ).fetchall()
    }

    reconstruction_required_columns = {
        "reconstruction_type": "TEXT",
        "output_path": "TEXT",
        "output_filename": "TEXT",
        "fragment_ids": "TEXT",
        "missing_regions": "TEXT",
        "reasons_json": "TEXT",
        "verified_bytes": "INTEGER DEFAULT 0",
        "inferred_bytes": "INTEGER DEFAULT 0",
        "missing_bytes": "INTEGER DEFAULT 0",
        "structural_integrity": "REAL",
        "recovery_confidence": "REAL",
        "reconstructed_size": "INTEGER DEFAULT 0",
        "sha256": "TEXT",
        "confidence_level": "TEXT",
        "confidence_factors_json": "TEXT",
        "feasibility_status": "TEXT",
        "feasibility_factors_json": "TEXT",
        "feasibility_blockers_json": "TEXT",
        "feasibility_supporting_evidence_json": "TEXT",
        "verified_ratio": "REAL",
        "inferred_ratio": "REAL",
        "missing_ratio": "REAL",
        "contribution_summary_json": "TEXT",
        "missing_regions_json": "TEXT",
        "overlaps_json": "TEXT",
        "contradictions_json": "TEXT",
        "uncertainties_json": "TEXT",
        "evidence_status": "TEXT",
        "evidence_summary_json": "TEXT",
        "priority": "TEXT",
        "priority_score": "REAL",
        "priority_factors_json": "TEXT",
        "positive_factors_json": "TEXT",
        "negative_factors_json": "TEXT",
        "unresolved_issues_json": "TEXT",
        "priority_explanation": "TEXT",
    }

    for column_name, column_type in reconstruction_required_columns.items():
        if column_name not in reconstruction_columns:
            connection.execute(
                f"""
                ALTER TABLE reconstructions
                ADD COLUMN {column_name} {column_type}
                """
            )

    connection.commit()
    connection.close()