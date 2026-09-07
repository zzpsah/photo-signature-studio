"""Local SQLite storage for record/document/asset relationships.

The database stores metadata and relationships only. Binary files remain in the
managed record folders, preserving a simple local/offline storage model.
"""

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_uid TEXT UNIQUE NOT NULL,
    title TEXT,
    person_name TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    filename TEXT NOT NULL,
    document_type TEXT,
    sha256 TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS ocr_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    engine TEXT NOT NULL,
    status TEXT NOT NULL,
    raw_text_path TEXT,
    structured_data_path TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
    document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
    asset_type TEXT NOT NULL,
    path TEXT NOT NULL,
    source_page INTEGER,
    source_region TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_documents_record ON documents(record_id);
CREATE INDEX IF NOT EXISTS idx_assets_record ON assets(record_id);
CREATE INDEX IF NOT EXISTS idx_ocr_document ON ocr_results(document_id);
"""


class StudioDatabase:
    """Small SQLite repository used by future record-management UI."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self):
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def create_record(self, record_uid: str, title: str = "", person_name: str = "") -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO records(record_uid, title, person_name) VALUES (?, ?, ?)",
                (record_uid, title, person_name),
            )
            return int(cursor.lastrowid)
