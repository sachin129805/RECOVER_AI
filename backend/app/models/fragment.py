from dataclasses import dataclass
from typing import Optional


@dataclass
class Fragment:
    fragment_id: str
    evidence_id: str
    filename: str
    file_type: str
    mime_type: str
    signature: str
    offset: int
    sample_size: int
    entropy: float
    classification_confidence: Optional[float] = None
    integrity_status: str = "Unknown"
    recovery_status: str = "Candidate"