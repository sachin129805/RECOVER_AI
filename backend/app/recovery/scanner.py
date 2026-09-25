from pathlib import Path
import math


SIGNATURES = {
    "JPEG": {
        "signature": b"\xFF\xD8\xFF",
        "mime_type": "image/jpeg",
    },
    "PNG": {
        "signature": b"\x89PNG\r\n\x1a\n",
        "mime_type": "image/png",
    },
    "PDF": {
        "signature": b"%PDF-",
        "mime_type": "application/pdf",
    },
    "ZIP": {
        "signature": b"PK\x03\x04",
        "mime_type": "application/zip",
    },
    "GIF": {
        "signature": b"GIF8",
        "mime_type": "image/gif",
    },
    "RIFF": {
        "signature": b"RIFF",
        "mime_type": "application/octet-stream",
    },
    "EXE": {
        "signature": b"MZ",
        "mime_type": "application/vnd.microsoft.portable-executable",
    },
}


def calculate_entropy(data: bytes) -> float:
    if not data:
        return 0.0

    frequencies = [0] * 256

    for byte in data:
        frequencies[byte] += 1

    entropy = 0.0
    length = len(data)

    for count in frequencies:
        if count == 0:
            continue

        probability = count / length
        entropy -= probability * math.log2(probability)

    return round(entropy, 4)


def detect_file_format(path: Path) -> str | None:
    """
    Identify the format of a normal uploaded file from its
    beginning bytes.

    This prevents embedded byte patterns inside an already
    recognized file from being treated as independent files.
    """

    try:
        with path.open("rb") as file:
            header = file.read(16)
    except OSError:
        return None

    for file_type, info in SIGNATURES.items():
        if header.startswith(info["signature"]):
            return file_type

    return None


def scan_binary_file(
    path: Path,
    chunk_size: int = 1024 * 1024,
    allow_embedded_signatures: bool = False,
) -> list[dict]:

    file_size = path.stat().st_size

    # For ordinary uploaded files, recognize the file itself first.
    # We do not want signatures embedded inside PDFs/images/etc.
    # to automatically become independent recovered files.
    if not allow_embedded_signatures:
        detected_type = detect_file_format(path)

        if detected_type:
            info = SIGNATURES[detected_type]

            with path.open("rb") as file:
                sample = file.read(min(file_size, chunk_size))

            return [
                {
                    "file_type": detected_type,
                    "mime_type": info["mime_type"],
                    "signature": info["signature"].hex(),
                    "offset": 0,
                    "sample_size": len(sample),
                    "entropy": calculate_entropy(sample),
                }
            ]

    detections = []

    overlap = 16
    previous_tail = b""
    absolute_offset = 0

    with path.open("rb") as file:

        while True:

            chunk = file.read(chunk_size)

            if not chunk:
                break

            data = previous_tail + chunk
            base_offset = absolute_offset - len(previous_tail)

            for file_type, info in SIGNATURES.items():

                signature = info["signature"]
                start = 0

                while True:

                    relative_offset = data.find(
                        signature,
                        start,
                    )

                    if relative_offset == -1:
                        break

                    offset = base_offset + relative_offset

                    # Avoid duplicate detections caused by overlap.
                    if offset >= 0:

                        sample_start = relative_offset
                        sample = data[
                            sample_start:
                            sample_start + min(4096, len(data) - sample_start)
                        ]

                        detections.append(
                            {
                                "file_type": file_type,
                                "mime_type": info["mime_type"],
                                "signature": signature.hex(),
                                "offset": offset,
                                "sample_size": len(sample),
                                "entropy": calculate_entropy(sample),
                            }
                        )

                    start = relative_offset + 1

            absolute_offset += len(chunk)
            previous_tail = chunk[-overlap:]

    # Remove duplicate offsets/signatures.
    unique = {}

    for detection in detections:
        key = (
            detection["file_type"],
            detection["offset"],
        )
        unique[key] = detection

    return sorted(
        unique.values(),
        key=lambda item: item["offset"],
    )