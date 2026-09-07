"""Google Drive upload helper using a service account stored in deployment secrets."""
from __future__ import annotations

import io
import json
import os
from typing import Any


class GoogleDriveError(RuntimeError):
    pass


def _credentials_from_secrets(secrets: Any = None):
    raw = ""
    if secrets is not None:
        try:
            raw = secrets.get("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON", "")
        except Exception:
            pass
    raw = raw or os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON", "")
    if not raw:
        raise GoogleDriveError("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON is not configured")
    try:
        info = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError as exc:
        raise GoogleDriveError("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON is not valid JSON") from exc

    try:
        from google.oauth2.service_account import Credentials
    except ImportError as exc:
        raise GoogleDriveError("Google Drive dependencies are not installed") from exc
    return Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/drive.file"],
    )


def get_folder_id(secrets: Any = None) -> str:
    value = ""
    if secrets is not None:
        try:
            value = secrets.get("GOOGLE_DRIVE_FOLDER_ID", "")
        except Exception:
            pass
    return str(value or os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")).strip()


def upload_bytes(filename: str, payload: bytes, mime_type: str = "image/jpeg", folder_id: str = "", secrets: Any = None) -> dict:
    """Upload bytes into a configured Drive folder and return file metadata."""
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseUpload
    except ImportError as exc:
        raise GoogleDriveError("Google Drive dependencies are not installed") from exc

    folder_id = folder_id or get_folder_id(secrets)
    if not folder_id:
        raise GoogleDriveError("GOOGLE_DRIVE_FOLDER_ID is not configured")
    credentials = _credentials_from_secrets(secrets)
    service = build("drive", "v3", credentials=credentials, cache_discovery=False)
    metadata = {"name": filename, "parents": [folder_id]}
    media = MediaIoBaseUpload(io.BytesIO(payload), mimetype=mime_type, resumable=False)
    try:
        return service.files().create(
            body=metadata,
            media_body=media,
            fields="id,name,mimeType,size,webViewLink,webContentLink",
        ).execute()
    except Exception as exc:
        raise GoogleDriveError(f"Google Drive upload failed: {exc}") from exc
