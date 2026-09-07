from __future__ import annotations

from dataclasses import dataclass
import math

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


@dataclass
class FormEditSettings:
    quarter_turns: int = 0
    fine_angle: float = 0.0
    deskew_angle: float = 0.0
    perspective: bool = False
    crop_left: int = 0
    crop_top: int = 0
    crop_right: int = 100
    crop_bottom: int = 100
    brightness: float = 1.0
    contrast: float = 1.0
    sharpness: float = 1.0
    grayscale: bool = False
    cleanup: bool = True


def rotate(image: Image.Image, angle: float) -> Image.Image:
    if abs(angle) < 0.001:
        return image.copy()
    return image.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC, fillcolor="white")


def _order_points(points: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype=np.float32)
    sums = points.sum(axis=1)
    diffs = np.diff(points, axis=1).ravel()
    rect[0] = points[np.argmin(sums)]
    rect[2] = points[np.argmax(sums)]
    rect[1] = points[np.argmin(diffs)]
    rect[3] = points[np.argmax(diffs)]
    return rect


def detect_document_quad(image: Image.Image) -> np.ndarray | None:
    """Find the large sheet boundary, useful for phone photographs of forms."""
    rgb = np.array(image.convert("RGB"))
    h, w = rgb.shape[:2]
    scale = min(1.0, 1400.0 / max(h, w))
    small = cv2.resize(rgb, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else rgb
    gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 40, 140)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    image_area = small.shape[0] * small.shape[1]
    best = None
    best_score = 0.0
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < image_area * 0.20:
            continue
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.025 * peri, True)
        if len(approx) != 4 or not cv2.isContourConvex(approx):
            continue
        rect = approx.reshape(4, 2).astype(np.float32)
        rect = _order_points(rect)
        width_a = np.linalg.norm(rect[2] - rect[3])
        width_b = np.linalg.norm(rect[1] - rect[0])
        height_a = np.linalg.norm(rect[1] - rect[2])
        height_b = np.linalg.norm(rect[0] - rect[3])
        ratio = max(width_a, width_b) / max(1.0, min(height_a, height_b))
        if ratio < 0.55 or ratio > 2.5:
            continue
        score = area / image_area
        if score > best_score:
            best_score, best = score, rect
    if best is None:
        return None
    return best / scale


def perspective_correct(image: Image.Image) -> tuple[Image.Image, bool]:
    quad = detect_document_quad(image)
    if quad is None:
        return image.copy(), False
    rect = _order_points(quad)
    tl, tr, br, bl = rect
    width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    if width < 200 or height < 200:
        return image.copy(), False
    dst = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(np.array(image.convert("RGB")), matrix, (width, height), borderValue=(255, 255, 255))
    return Image.fromarray(warped), True


def estimate_deskew_angle(image: Image.Image) -> float:
    gray = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(gray, 40, 120)
    h, w = gray.shape
    lines = cv2.HoughLinesP(edges, 1, np.pi / 1800, threshold=max(50, min(h, w) // 5), minLineLength=max(80, min(h, w) // 4), maxLineGap=25)
    if lines is None:
        return 0.0
    candidates = []
    for x1, y1, x2, y2 in lines[:, 0]:
        length = math.hypot(x2 - x1, y2 - y1)
        angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
        if length >= min(h, w) * 0.18 and -12 <= angle <= 12:
            candidates.append((angle, length))
    if not candidates:
        return 0.0
    candidates.sort(key=lambda item: item[1], reverse=True)
    selected = candidates[:30]
    angle = float(np.average([a for a, _ in selected], weights=[l for _, l in selected]))
    return max(-12.0, min(12.0, -angle))


def crop_percent(image: Image.Image, left: int, top: int, right: int, bottom: int) -> Image.Image:
    w, h = image.size
    x1 = int(w * left / 100)
    y1 = int(h * top / 100)
    x2 = max(x1 + 1, int(w * right / 100))
    y2 = max(y1 + 1, int(h * bottom / 100))
    return image.crop((x1, y1, min(w, x2), min(h, y2)))


def cleanup_scan(image: Image.Image) -> Image.Image:
    """Normalize uneven paper lighting while preserving printed and handwritten strokes."""
    arr = np.array(image.convert("RGB"))
    lab = cv2.cvtColor(arr, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    background = cv2.GaussianBlur(l, (0, 0), 21)
    normalized = cv2.divide(l, background, scale=210)
    normalized = cv2.normalize(normalized, None, 0, 255, cv2.NORM_MINMAX)
    normalized = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8)).apply(normalized)
    result = cv2.cvtColor(cv2.merge((normalized, a, b)), cv2.COLOR_LAB2RGB)
    result = cv2.fastNlMeansDenoisingColored(result, None, 3, 3, 7, 21)
    return Image.fromarray(result)


def apply_settings(original: Image.Image, settings: FormEditSettings) -> Image.Image:
    image = ImageOps.exif_transpose(original.convert("RGB"))
    image = image.rotate(-90 * settings.quarter_turns, expand=True, resample=Image.Resampling.BICUBIC, fillcolor="white") if settings.quarter_turns else image.copy()
    if settings.perspective:
        corrected, found = perspective_correct(image)
        if found:
            image = corrected
    total_angle = settings.deskew_angle + settings.fine_angle
    image = rotate(image, total_angle)
    if (settings.crop_left, settings.crop_top, settings.crop_right, settings.crop_bottom) != (0, 0, 100, 100):
        image = crop_percent(image, settings.crop_left, settings.crop_top, settings.crop_right, settings.crop_bottom)
    if settings.brightness != 1.0:
        image = ImageEnhance.Brightness(image).enhance(settings.brightness)
    if settings.contrast != 1.0:
        image = ImageEnhance.Contrast(image).enhance(settings.contrast)
    if settings.sharpness != 1.0:
        image = ImageEnhance.Sharpness(image).enhance(settings.sharpness)
    if settings.grayscale:
        image = ImageOps.grayscale(image).convert("RGB")
    if settings.cleanup:
        image = cleanup_scan(image)
    return image


def prepare_jpeg(image: Image.Image, quality: int = 95) -> bytes:
    import io
    bio = io.BytesIO()
    image.save(bio, "JPEG", quality=quality, optimize=True)
    return bio.getvalue()
