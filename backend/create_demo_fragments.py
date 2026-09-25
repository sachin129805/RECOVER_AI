from pathlib import Path
import hashlib
import json
import shutil


# ============================================================
# CONFIGURATION
# ============================================================

BACKEND_DIR = Path(__file__).resolve().parent

EVIDENCE_DIR = BACKEND_DIR / "storage" / "evidence"

DEMO_DIR = BACKEND_DIR / "storage" / "demo" / "fragmented_pdf"

SOURCE_FILENAME = "412sss.pdf"


# ============================================================
# HELPERS
# ============================================================

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_fragment(path: Path, data: bytes):
    path.write_bytes(data)

    return {
        "filename": path.name,
        "size_bytes": len(data),
        "sha256": sha256_bytes(data),
    }


# ============================================================
# FIND ORIGINAL EVIDENCE
# ============================================================

candidate_paths = list(EVIDENCE_DIR.glob("*/" + SOURCE_FILENAME))

if not candidate_paths:
    raise FileNotFoundError(
        f"Could not find {SOURCE_FILENAME} inside {EVIDENCE_DIR}"
    )

# Use the newest copy.
source_path = max(
    candidate_paths,
    key=lambda p: p.stat().st_mtime
)


# ============================================================
# READ ORIGINAL
# ============================================================

original = source_path.read_bytes()

original_size = len(original)

print()
print("=" * 60)
print("RECOVERAI CONTROLLED FRAGMENT DATASET")
print("=" * 60)
print()
print(f"Source:       {source_path}")
print(f"Original size: {original_size:,} bytes")
print()


# ============================================================
# RESET DEMO DIRECTORY
# ============================================================

if DEMO_DIR.exists():
    shutil.rmtree(DEMO_DIR)

DEMO_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# CREATE CONTROLLED FRAGMENTS
# ============================================================

# We deliberately split the original into several regions.
#
# This gives the reconstruction engine known ground truth.
#
# Fragment 1:
#   Beginning of PDF
#
# Fragment 2:
#   Middle section
#
# Fragment 3:
#   Another section
#
# Fragment 4:
#   Final section
#
# We also create a "missing" region in the ground-truth map.
# The actual original bytes remain available for evaluation,
# but the recovery dataset does not contain those bytes.


boundaries = [
    0,
    int(original_size * 0.20),
    int(original_size * 0.45),
    int(original_size * 0.70),
    original_size,
]


# Missing region deliberately selected from the middle.
missing_start = int(original_size * 0.45)
missing_end = int(original_size * 0.55)


regions = [
    (
        "fragment_001.bin",
        0,
        missing_start,
    ),
    (
        "fragment_002.bin",
        missing_end,
        int(original_size * 0.70),
    ),
    (
        "fragment_003.bin",
        int(original_size * 0.70),
        int(original_size * 0.85),
    ),
    (
        "fragment_004.bin",
        int(original_size * 0.85),
        original_size,
    ),
]


fragments = []

for filename, start, end in regions:

    data = original[start:end]

    path = DEMO_DIR / filename

    info = write_fragment(
        path,
        data
    )

    info.update(
        {
            "ground_truth_offset": start,
            "ground_truth_end": end,
            "source_file": SOURCE_FILENAME,
        }
    )

    fragments.append(info)


# ============================================================
# GROUND TRUTH
# ============================================================

ground_truth = {
    "dataset": "RECOVERAI Controlled Fragmented PDF",
    "source_file": SOURCE_FILENAME,
    "source_sha256": sha256_bytes(original),
    "original_size_bytes": original_size,

    "missing_region": {
        "start": missing_start,
        "end": missing_end,
        "size_bytes": missing_end - missing_start,
    },

    "fragments": fragments,

    "ground_truth_notes": [
        "Fragments are deterministic slices of the original file.",
        "The original source file is preserved.",
        "The missing region is intentionally excluded from the recovery dataset.",
        "Ground truth is used only for evaluating the prototype.",
        "AI-inferred bytes must never be presented as verified original bytes.",
    ],
}


ground_truth_path = DEMO_DIR / "ground_truth.json"

ground_truth_path.write_text(
    json.dumps(
        ground_truth,
        indent=4
    ),
    encoding="utf-8"
)


# ============================================================
# MANIFEST
# ============================================================

manifest = {
    "dataset": "RECOVERAI Controlled Fragmented PDF",
    "source": SOURCE_FILENAME,
    "fragment_count": len(fragments),
    "missing_bytes": missing_end - missing_start,
    "original_bytes": original_size,
    "files": [
        fragment["filename"]
        for fragment in fragments
    ],
}


manifest_path = DEMO_DIR / "manifest.json"

manifest_path.write_text(
    json.dumps(
        manifest,
        indent=4
    ),
    encoding="utf-8"
)


# ============================================================
# OUTPUT
# ============================================================

print("Created controlled fragments:")
print()

for fragment in fragments:

    print(
        f"{fragment['filename']:20}"
        f"{fragment['size_bytes']:>12,} bytes"
        f"  offset "
        f"{fragment['ground_truth_offset']:,}"
        f"-"
        f"{fragment['ground_truth_end']:,}"
    )

print()

print(
    f"Missing region: "
    f"{missing_start:,}"
    f"-"
    f"{missing_end:,}"
    f" "
    f"({missing_end - missing_start:,} bytes)"
)

print()

print(f"Demo directory:")
print(DEMO_DIR)

print()

print("Ground truth:")
print(ground_truth_path)

print()
print("=" * 60)
print("DATASET CREATED")
print("=" * 60)