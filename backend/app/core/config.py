from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent

STORAGE_DIR = BASE_DIR / "storage"
EVIDENCE_DIR = STORAGE_DIR / "evidence"
FRAGMENTS_DIR = STORAGE_DIR / "fragments"
RECOVERED_DIR = STORAGE_DIR / "recovered"

for directory in (
    EVIDENCE_DIR,
    FRAGMENTS_DIR,
    RECOVERED_DIR,
):
    directory.mkdir(parents=True, exist_ok=True)
