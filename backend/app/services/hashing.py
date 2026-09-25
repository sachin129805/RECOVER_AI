import hashlib
from pathlib import Path


def calculate_sha256(
    file_path: str,
    chunk_size: int = 1024 * 1024
) -> str:
    """
    Calculate SHA-256 hash of a file.

    Files are processed in chunks so large evidence files
    do not need to be loaded entirely into memory.
    """

    sha256 = hashlib.sha256()

    with Path(file_path).open("rb") as file:
        while True:
            chunk = file.read(chunk_size)

            if not chunk:
                break

            sha256.update(chunk)

    return sha256.hexdigest()
