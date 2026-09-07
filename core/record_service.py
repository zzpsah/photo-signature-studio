"""High-level record service for linking data, source files, photos and signatures."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .database import StudioDatabase
from .storage import RecordStorage


class RecordService:
    """Application-facing service for a record and its managed files."""

    def __init__(self, root: str | Path = "data"):
        self.root = Path(root)
        self.storage = RecordStorage(self.root / "records")
        self.db = StudioDatabase(self.root / "studio.db")

    def create_record(self, title: str = "", person_name: str = "") -> tuple[str, Path]:
        uid = f"APP-{datetime.now():%Y%m%d}-{uuid4().hex[:8].upper()}"
        self.db.create_record(uid, title, person_name)
        return uid, self.storage.record_dir(uid)

    def add_source_file(self, record_uid: str, source_path: str | Path, document_type: str = "") -> Path:
        source = Path(source_path)
        destination = self.storage.source_dir(record_uid) / source.name
        shutil.copy2(source, destination)
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        # Look up the record's integer ID and register the managed copy.
        with self.db.connect() as connection:
            row = connection.execute("SELECT id FROM records WHERE record_uid = ?", (record_uid,)).fetchone()
            if not row:
                raise ValueError(f"Unknown record: {record_uid}")
            connection.execute(
                "INSERT INTO documents(record_id,path,filename,document_type,sha256) VALUES (?,?,?,?,?)",
                (row[0], str(destination), destination.name, document_type, digest),
            )
        return destination

    def save_portal_asset(
        self,
        record_uid: str,
        asset_type: str,
        source_path: str | Path,
        filename: str | None = None,
        document_id: int | None = None,
        source_page: int | None = None,
        source_region: str | None = None,
    ) -> Path:
        """Store a portal-ready photo/signature and register its relationship."""
        if asset_type not in {"photo", "signature", "document"}:
            raise ValueError("asset_type must be photo, signature, or document")
        source = Path(source_path)
        target_dir = {
            "photo": self.storage.photo_dir(record_uid),
            "signature": self.storage.signature_dir(record_uid),
            "document": self.storage.documents_dir(record_uid),
        }[asset_type]
        destination = target_dir / (filename or source.name)
        shutil.copy2(source, destination)
        with self.db.connect() as connection:
            row = connection.execute("SELECT id FROM records WHERE record_uid = ?", (record_uid,)).fetchone()
            if not row:
                raise ValueError(f"Unknown record: {record_uid}")
            connection.execute(
                "INSERT INTO assets(record_id,document_id,asset_type,path,source_page,source_region) VALUES (?,?,?,?,?,?)",
                (row[0], document_id, asset_type, str(destination), source_page, source_region),
            )
        return destination

    def save_ocr(self, record_uid: str, text: str, structured_data: dict, document_id: int | None = None, engine: str = "Chandra OCR") -> tuple[Path, Path]:
        """Persist OCR output in the record folder and register it in SQLite."""
        ocr_dir = self.storage.ocr_dir(record_uid)
        text_path = ocr_dir / "raw_text.txt"
        data_path = ocr_dir / "extracted.json"
        text_path.write_text(text or "", encoding="utf-8")
        data_path.write_text(json.dumps(structured_data or {}, ensure_ascii=False, indent=2), encoding="utf-8")
        if document_id is not None:
            with self.db.connect() as connection:
                connection.execute(
                    "INSERT INTO ocr_results(document_id,engine,status,raw_text_path,structured_data_path) VALUES (?,?,?,?,?)",
                    (document_id, engine, "completed", str(text_path), str(data_path)),
                )
        return text_path, data_path
