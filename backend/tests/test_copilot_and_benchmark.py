import json
from unittest.mock import patch

from app.api.copilot import copilot_query
from app.api.benchmarks import run_benchmark
from app.services.ollama_service import ask_ollama


class DummyResponse:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False
    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_ollama_unavailable():
    with patch("app.services.ollama_service.request.urlopen", side_effect=Exception("down")):
        try:
            ask_ollama("test", {"evidence_id": "EVD-123"})
        except Exception as exc:
            assert "failed" in str(exc).lower()


def test_valid_grounded_question():
    context = {
        "evidence_id": "EVD-TEST",
        "evidence_references": ["Evidence EVD-TEST"],
        "limitations": ["Reference unavailable"],
        "fragments": [{"fragment_id": "F-1", "offset": 0, "sample_size": 10}],
    }
    with patch("app.services.ollama_service.request.urlopen", return_value=DummyResponse({"response": "The evidence contains one fragment and no reference was supplied."})):
        result = ask_ollama("What fragments exist?", context)
        assert result["grounded"] is True
        assert "fragment" in result["answer"].lower()


def test_unsupported_question():
    context = {"evidence_id": "EVD-TEST", "evidence_references": []}
    with patch("app.services.ollama_service.request.urlopen", return_value=DummyResponse({"response": "Insufficient evidence to answer this from the current investigation."})):
        result = ask_ollama("Who is the suspect?", context)
        assert "insufficient evidence" in result["answer"].lower()


def test_benchmark_run_registration():
    payload = {
        "evidence_id": "EVD-1",
        "reconstructed_path": "/tmp/recovered.bin",
        "reference_size": 100,
        "recovered_size": 90,
        "correctly_recovered_bytes": 80,
        "incorrectly_recovered_bytes": 10,
        "missing_bytes": 10,
        "verified_bytes": 80,
        "inferred_bytes": 10,
        "precision": 0.8,
        "recall": 0.8,
        "f1": 0.8,
        "coverage": 0.9,
        "exact_sha256_match": True,
        "structural_validity": 1.0,
        "missing_region_accuracy": 0.8,
        "relationship_accuracy": 0.7,
    }
    response = run_benchmark(payload)
    assert response["status"] == "registered"
    assert "benchmark_id" in response
