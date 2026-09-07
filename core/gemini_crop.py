"""Optional Gemini Vision helper for locating photo/signature regions on forms."""
from __future__ import annotations

import base64
import json
import os
from typing import Any

import requests

GEMINI_MODEL = os.getenv("GEMINI_CROP_MODEL", "gemini-3.7-flash")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiCropError(RuntimeError):
    pass


def get_gemini_key(secrets: Any = None) -> str:
    if secrets is not None:
        try:
            value = secrets.get("GEMINI_API_KEY", "")
            if value:
                return str(value)
        except Exception:
            pass
    return os.getenv("GEMINI_API_KEY", "")


def _schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "found": {"type": "boolean"},
            "label": {"type": "string"},
            "box_2d": {
                "type": "array",
                "items": {"type": "integer"},
                "minItems": 4,
                "maxItems": 4,
            },
            "confidence": {"type": "number"},
        },
        "required": ["found", "label", "box_2d", "confidence"],
    }


def locate_region(image_bytes: bytes, target: str, api_key: str, mime_type: str = "image/jpeg") -> dict:
    """Locate one target region. Coordinates are [ymin,xmin,ymax,xmax] in 0..1000."""
    if not api_key:
        raise GeminiCropError("GEMINI_API_KEY is not configured")
    prompt = (
        f"Find the {target} in this student/BSEB registration document. "
        "Return ONLY the requested JSON object. "
        "The box_2d must tightly surround the actual target, not the whole page, "
        "and must be [ymin,xmin,ymax,xmax] normalized to 0-1000. "
        "If the target is absent, set found=false and box_2d=[0,0,0,0]."
    )
    body = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode("ascii")}},
            ]
        }],
        "generationConfig": {
            "response_mime_type": "application/json",
            "response_schema": _schema(),
        },
    }
    response = requests.post(
        GEMINI_URL.format(model=GEMINI_MODEL),
        params={"key": api_key},
        json=body,
        timeout=90,
    )
    if response.status_code >= 400:
        raise GeminiCropError(f"Gemini request failed ({response.status_code}): {response.text[:500]}")
    payload = response.json()
    try:
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
        result = json.loads(text)
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise GeminiCropError(f"Gemini returned an unexpected response: {payload}") from exc
    box = result.get("box_2d") or [0, 0, 0, 0]
    if not result.get("found") or len(box) != 4:
        return {"found": False, "label": target, "box_2d": [0, 0, 0, 0], "confidence": 0.0}
    box = [max(0, min(1000, int(v))) for v in box]
    if box[2] <= box[0] or box[3] <= box[1]:
        return {"found": False, "label": target, "box_2d": [0, 0, 0, 0], "confidence": 0.0}
    return {"found": True, "label": result.get("label", target), "box_2d": box, "confidence": float(result.get("confidence", 0.0))}


def crop_box(image, box_2d: list[int], padding: float = 0.02):
    """Crop a 0..1000 Gemini box from a PIL image, with small proportional padding."""
    width, height = image.size
    ymin, xmin, ymax, xmax = box_2d
    pad_x = int(width * padding)
    pad_y = int(height * padding)
    left = max(0, int(xmin / 1000 * width) - pad_x)
    top = max(0, int(ymin / 1000 * height) - pad_y)
    right = min(width, int(xmax / 1000 * width) + pad_x)
    bottom = min(height, int(ymax / 1000 * height) + pad_y)
    return image.crop((left, top, right, bottom))
