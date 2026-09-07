"""Provider-neutral OCR interface.

Chandra OCR will be integrated behind this interface in a future release.
Keeping the interface provider-neutral prevents OCR-specific code from leaking
into the desktop UI and record-management layers.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass
class OCRResult:
    engine: str
    text: str
    structured_data: dict[str, Any]
    confidence: float | None = None


class OCREngine(Protocol):
    name: str

    def extract(self, source: str | Path) -> OCRResult:
        """Extract text and optional structured fields from a source document."""
        ...
