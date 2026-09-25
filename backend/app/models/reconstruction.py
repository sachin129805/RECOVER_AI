from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReconstructionCandidate:
    evidence_id: str
    fragment_ids: list[str] = field(default_factory=list)
    status: str = "UNABLE_TO_RECOVER"
    reconstruction_type: str | None = None
    verified_bytes: int = 0
    inferred_bytes: int = 0
    missing_bytes: int = 0
    structural_integrity: float | None = None
    recovery_confidence: float | None = None
    reasons: list[str] = field(default_factory=list)
    missing_regions: list[dict[str, Any]] = field(default_factory=list)
    output_path: str | None = None
    output_filename: str | None = None
    reconstructed_size: int = 0
    sha256: str | None = None
