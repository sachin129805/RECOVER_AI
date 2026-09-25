from pathlib import Path

from PIL import Image


def extract_metadata(file_path: str) -> dict:
    path = Path(file_path)

    metadata = {
        "filename": path.name,
        "extension": path.suffix.lower(),
        "size_bytes": path.stat().st_size,
        "file_type": "unknown",
    }

    # Attempt image metadata extraction.
    try:
        with Image.open(path) as image:
            metadata.update(
                {
                    "file_type": image.format or "unknown",
                    "width": image.width,
                    "height": image.height,
                    "mode": image.mode,
                }
            )
    except Exception:
        pass

    return metadata
