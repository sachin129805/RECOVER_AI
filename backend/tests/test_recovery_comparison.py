import json

from app.services.recovery_comparison_service import (
    compare_recovery_artifacts,
    summarize_range_statuses,
)


def test_no_reference_available(tmp_path):
    source = tmp_path / "source.bin"
    recovered = tmp_path / "recovered.bin"
    source.write_bytes(b"abcd1234")
    recovered.write_bytes(b"abcd5678")

    result = compare_recovery_artifacts(
        evidence_id="EVD-TEST-NOREF",
        reconstruction_id="RC-TEST-NOREF",
        source_path=str(source),
        recovered_path=str(recovered),
        reconstruction={
            "reconstruction_id": "RC-TEST-NOREF",
            "status": "STRUCTURAL_REPAIR",
            "verified_bytes": 4,
            "inferred_bytes": 4,
            "missing_bytes": 0,
            "structural_integrity": 68.0,
        },
    )

    assert result["reference"]["available"] is False
    assert result["recovered_matches_reference"] is None
    assert result["source_size_bytes"] == 8
    assert result["recovered_size_bytes"] == 8
    assert result["comparison_status"] in {"SOURCE_RECONSTRUCTION_COMPARISON", "NO_REFERENCE_AVAILABLE"}


def test_exact_reference_match(tmp_path):
    source = tmp_path / "source.bin"
    recovered = tmp_path / "recovered.bin"
    reference = tmp_path / "reference.bin"
    payload = b"ABCDEF"
    source.write_bytes(payload)
    recovered.write_bytes(payload)
    reference.write_bytes(payload)

    result = compare_recovery_artifacts(
        evidence_id="EVD-TEST-REFMATCH",
        reconstruction_id="RC-TEST-REFMATCH",
        source_path=str(source),
        recovered_path=str(recovered),
        reference_path=str(reference),
        reconstruction={
            "reconstruction_id": "RC-TEST-REFMATCH",
            "status": "VERIFIED_RECOVERY",
            "verified_bytes": 6,
            "inferred_bytes": 0,
            "missing_bytes": 0,
            "structural_integrity": 99.0,
        },
    )

    assert result["reference"]["available"] is True
    assert result["recovered_matches_reference"] is True
    assert result["identical_bytes"] == 6
    assert result["changed_bytes"] == 0
    assert result["coverage_ratio"] == 1.0


def test_different_recovered_artifact(tmp_path):
    source = tmp_path / "source.bin"
    recovered = tmp_path / "recovered.bin"
    reference = tmp_path / "reference.bin"
    source.write_bytes(b"ABCDEFGH")
    recovered.write_bytes(b"ABCXFGH")
    reference.write_bytes(b"ABCDEFGH")

    result = compare_recovery_artifacts(
        evidence_id="EVD-TEST-DIFF",
        reconstruction_id="RC-TEST-DIFF",
        source_path=str(source),
        recovered_path=str(recovered),
        reference_path=str(reference),
        reconstruction={
            "reconstruction_id": "RC-TEST-DIFF",
            "status": "STRUCTURAL_REPAIR",
            "verified_bytes": 4,
            "inferred_bytes": 4,
            "missing_bytes": 0,
            "structural_integrity": 74.0,
        },
    )

    assert result["recovered_matches_reference"] is False
    assert result["changed_bytes"] >= 1
    assert any(item["comparison"] == "DIFFERENT" for item in result["regions"])


def test_missing_region_detection(tmp_path):
    source = tmp_path / "source.bin"
    recovered = tmp_path / "recovered.bin"
    reference = tmp_path / "reference.bin"
    source.write_bytes(b"abcdefghij")
    recovered.write_bytes(b"abcde")
    reference.write_bytes(b"abcdefghij")

    result = compare_recovery_artifacts(
        evidence_id="EVD-TEST-MISSING",
        reconstruction_id="RC-TEST-MISSING",
        source_path=str(source),
        recovered_path=str(recovered),
        reference_path=str(reference),
        reconstruction={
            "reconstruction_id": "RC-TEST-MISSING",
            "status": "INFERRED_RECONSTRUCTION",
            "verified_bytes": 5,
            "inferred_bytes": 5,
            "missing_bytes": 5,
            "structural_integrity": 60.0,
        },
    )

    assert result["missing_bytes"] >= 5
    assert any(item["comparison"] == "MISSING" for item in result["regions"])


def test_inferred_region_is_marked_not_verified(tmp_path):
    source = tmp_path / "source.bin"
    recovered = tmp_path / "recovered.bin"
    reference = tmp_path / "reference.bin"
    source.write_bytes(b"123456")
    recovered.write_bytes(b"123456")
    reference.write_bytes(b"123456")

    result = compare_recovery_artifacts(
        evidence_id="EVD-TEST-INFERRED",
        reconstruction_id="RC-TEST-INFERRED",
        source_path=str(source),
        recovered_path=str(recovered),
        reference_path=str(reference),
        reconstruction={
            "reconstruction_id": "RC-TEST-INFERRED",
            "status": "INFERRED_RECONSTRUCTION",
            "verified_bytes": 2,
            "inferred_bytes": 4,
            "missing_bytes": 0,
            "structural_integrity": 50.0,
        },
    )

    assert result["inferred_bytes"] == 4
    assert any("INFERRED" in item.get("recovered_status", "") for item in result["regions"])


def test_overlapping_ranges_detected():
    regions = [
        {"start": 0, "end": 10, "status": "VERIFIED"},
        {"start": 5, "end": 15, "status": "VERIFIED"},
    ]

    summary = summarize_range_statuses(regions)
    assert summary["overlap_count"] >= 1
    assert summary["overlap_bytes"] >= 5


def test_empty_artifact(tmp_path):
    source = tmp_path / "source.bin"
    recovered = tmp_path / "recovered.bin"
    ref = tmp_path / "reference.bin"
    source.write_bytes(b"")
    recovered.write_bytes(b"")
    ref.write_bytes(b"")

    result = compare_recovery_artifacts(
        evidence_id="EVD-TEST-EMPTY",
        reconstruction_id="RC-TEST-EMPTY",
        source_path=str(source),
        recovered_path=str(recovered),
        reference_path=str(ref),
        reconstruction={
            "reconstruction_id": "RC-TEST-EMPTY",
            "status": "UNABLE_TO_RECOVER",
            "verified_bytes": 0,
            "inferred_bytes": 0,
            "missing_bytes": 0,
            "structural_integrity": 0.0,
        },
    )

    assert result["source_size_bytes"] == 0
    assert result["recovered_size_bytes"] == 0
    assert result["reference"]["available"] is True
    assert result["recovered_matches_reference"] is True


def test_missing_artifact_is_explicitly_unknown(tmp_path):
    source = tmp_path / "source.bin"
    source.write_bytes(b"cat")

    result = compare_recovery_artifacts(
        evidence_id="EVD-TEST-MISSING-ARTIFACT",
        reconstruction_id="RC-TEST-MISSING-ARTIFACT",
        source_path=str(source),
        recovered_path=str(tmp_path / "missing.bin"),
        reference_path=str(tmp_path / "reference_missing.bin"),
        reconstruction={
            "reconstruction_id": "RC-TEST-MISSING-ARTIFACT",
            "status": "UNABLE_TO_RECOVER",
            "verified_bytes": 0,
            "inferred_bytes": 0,
            "missing_bytes": 3,
            "structural_integrity": 0.0,
        },
    )

    assert result["recovered_artifact"]["available"] is False
    assert result["reference"]["available"] is False
    assert result["recovered_matches_reference"] is None


def test_chunked_large_file_comparison(tmp_path):
    source = tmp_path / "large.bin"
    recovered = tmp_path / "large_recovered.bin"
    reference = tmp_path / "large_reference.bin"
    payload = b"A" * 200000 + b"B" * 200000
    source.write_bytes(payload)
    recovered.write_bytes(payload)
    reference.write_bytes(payload)

    result = compare_recovery_artifacts(
        evidence_id="EVD-TEST-LARGE",
        reconstruction_id="RC-TEST-LARGE",
        source_path=str(source),
        recovered_path=str(recovered),
        reference_path=str(reference),
        reconstruction={
            "reconstruction_id": "RC-TEST-LARGE",
            "status": "VERIFIED_RECOVERY",
            "verified_bytes": 400000,
            "inferred_bytes": 0,
            "missing_bytes": 0,
            "structural_integrity": 99.0,
        },
        chunk_size=4096,
    )

    assert result["source_size_bytes"] == 400000
    assert result["reference"]["available"] is True
    assert result["recovered_matches_reference"] is True
    assert len(result["regions"]) >= 1
