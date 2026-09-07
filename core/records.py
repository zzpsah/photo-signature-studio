"""Record-oriented local file layout.

A record UID is the stable link between source documents, OCR results, photos,
signatures and generated outputs. Filenames are not used as the relationship key.
"""

from pathlib import Path


RECORD_SUBDIRECTORIES = ("source", "ocr", "identity", "processed", "documents")


def record_root(base_dir: str | Path, record_uid: str) -> Path:
    root = Path(base_dir) / record_uid
    for name in RECORD_SUBDIRECTORIES:
        (root / name).mkdir(parents=True, exist_ok=True)
    return root
