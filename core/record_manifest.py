"""Portable manifest linking OCR data and portal upload assets to one record."""

import json
from pathlib import Path


def write_manifest(record_dir: str | Path, record_uid: str, data: dict) -> Path:
    path = Path(record_dir) / "portal_manifest.json"
    payload = {
        "record_uid": record_uid,
        "person": data.get("person", {}),
        "source_documents": data.get("source_documents", []),
        "ocr": data.get("ocr", {}),
        "photo": data.get("photo", {}),
        "signature": data.get("signature", {}),
        "portal": data.get("portal", {}),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
