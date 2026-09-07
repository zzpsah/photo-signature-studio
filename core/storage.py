"""Managed local storage for record files and portal-ready assets."""

from pathlib import Path
import re


class RecordStorage:
    """Keeps source files, OCR data, and upload-ready assets together by record UID."""

    def __init__(self, root: str | Path = "data/records"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def safe_uid(record_uid: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", record_uid)

    def record_dir(self, record_uid: str) -> Path:
        path = self.root / self.safe_uid(record_uid)
        for name in ("source", "ocr", "photo", "signature", "documents", "exports"):
            (path / name).mkdir(parents=True, exist_ok=True)
        return path

    def source_dir(self, record_uid: str) -> Path:
        return self.record_dir(record_uid) / "source"

    def ocr_dir(self, record_uid: str) -> Path:
        return self.record_dir(record_uid) / "ocr"

    def photo_dir(self, record_uid: str) -> Path:
        return self.record_dir(record_uid) / "photo"

    def signature_dir(self, record_uid: str) -> Path:
        return self.record_dir(record_uid) / "signature"

    def documents_dir(self, record_uid: str) -> Path:
        return self.record_dir(record_uid) / "documents"

    def exports_dir(self, record_uid: str) -> Path:
        return self.record_dir(record_uid) / "exports"

    def portal_manifest_path(self, record_uid: str) -> Path:
        return self.record_dir(record_uid) / "portal_manifest.json"
