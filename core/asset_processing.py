"""Deterministic post-processing for AI-isolated student photo/signature regions."""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


def _face_box(image: Image.Image):
    rgb = np.asarray(ImageOps.exif_transpose(image.convert("RGB")))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    if cascade.empty():
        return None
    h, w = gray.shape[:2]
    faces = cascade.detectMultiScale(gray, 1.08, 5, minSize=(max(28, w // 12), max(28, h // 12)))
    if len(faces) == 0:
        return None
    return max(faces, key=lambda r: r[2] * r[3])


def _tight_portrait(image: Image.Image) -> Image.Image:
    """When a Gemini crop still contains form margins, tighten around the detected face."""
    face = _face_box(image)
    if face is None:
        return image
    x, y, fw, fh = [int(v) for v in face]
    cx = x + fw / 2
    left = max(0, int(cx - fw * 1.55))
    right = min(image.width, int(cx + fw * 1.55))
    top = max(0, int(y - fh * 0.85))
    bottom = min(image.height, int(y + fh * 2.25))
    if right - left < fw * 1.8 or bottom - top < fh * 2.4:
        return image
    return image.crop((left, top, right, bottom))


def white_background(image: Image.Image) -> Image.Image:
    """Replace the portrait background with clean white when segmentation is reliable."""
    image = ImageOps.exif_transpose(image.convert("RGB"))
    arr = np.asarray(image).copy()
    h, w = arr.shape[:2]
    if min(h, w) < 80:
        return image

    face = _face_box(image)
    if face is None:
        # Only normalize pixels that are already nearly white; never invent a foreground mask.
        result = arr.copy()
        result[np.all(arr >= 242, axis=2)] = 255
        return Image.fromarray(result, "RGB")

    x, y, fw, fh = [int(v) for v in face]
    mask = np.full((h, w), cv2.GC_PR_BGD, np.uint8)
    border = max(3, min(h, w) // 60)
    mask[:border, :] = cv2.GC_BGD
    mask[-border:, :] = cv2.GC_BGD
    mask[:, :border] = cv2.GC_BGD
    mask[:, -border:] = cv2.GC_BGD

    # Definite foreground: face plus a conservative head/upper-body seed.
    cv2.ellipse(
        mask,
        (x + fw // 2, y + int(fh * 1.45)),
        (max(int(fw * 1.15), 1), max(int(fh * 1.65), 1)),
        0,
        0,
        360,
        cv2.GC_FGD,
        -1,
    )
    # Probable foreground around the expected portrait silhouette.
    cv2.ellipse(
        mask,
        (x + fw // 2, min(h - 1, y + int(fh * 1.8))),
        (max(int(fw * 2.0), 1), max(int(fh * 2.8), 1)),
        0,
        0,
        360,
        cv2.GC_PR_FGD,
        -1,
    )

    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(arr, mask, None, bgd, fgd, 6, cv2.GC_INIT_WITH_MASK)
    except cv2.error:
        return image

    fg = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    fg = cv2.GaussianBlur(fg, (3, 3), 0)
    alpha = fg.astype(np.float32) / 255.0
    result = (arr * alpha[..., None] + 255.0 * (1.0 - alpha[..., None])).clip(0, 255).astype(np.uint8)
    return Image.fromarray(result, "RGB")


def process_photo_asset(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    image = ImageOps.exif_transpose(image.convert("RGB"))
    image = _tight_portrait(image)
    image = white_background(image)
    image = ImageEnhance.Brightness(image).enhance(1.02)
    image = ImageEnhance.Contrast(image).enhance(1.03)
    image = ImageEnhance.Sharpness(image).enhance(1.08)
    return ImageOps.fit(image, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.43))


def process_signature_asset(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Extract handwritten ink from an AI-isolated signature region onto white."""
    image = ImageOps.exif_transpose(image.convert("RGB"))
    rgb = np.asarray(image)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    # Correct uneven illumination before thresholding.
    background = cv2.GaussianBlur(gray, (0, 0), 15)
    normalized = cv2.divide(gray, np.maximum(background, 1), scale=255)
    ink = cv2.adaptiveThreshold(
        normalized,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        8,
    )
    ink = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))

    # Remove long straight box edges before connected-component selection.
    horizontal = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(12, image.width // 5), 1)))
    vertical = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(12, image.height // 5))))
    ink = cv2.subtract(ink, cv2.bitwise_or(horizontal, vertical))

    n, labels, stats, _ = cv2.connectedComponentsWithStats(ink, 8)
    clean = np.zeros_like(ink)
    min_area = max(4, int(ink.size * 0.000015))
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area < min_area:
            continue
        # Tiny edge-connected marks are usually form borders rather than handwriting.
        if x <= 1 or y <= 1 or x + w >= ink.shape[1] - 1 or y + h >= ink.shape[0] - 1:
            continue
        clean[labels == i] = 255

    ys, xs = np.where(clean > 0)
    canvas = Image.new("RGB", size, "white")
    if len(xs) < 12:
        return canvas

    pad = max(5, int(min(image.size) * 0.04))
    left = max(0, int(xs.min()) - pad)
    top = max(0, int(ys.min()) - pad)
    right = min(image.width, int(xs.max()) + pad + 1)
    bottom = min(image.height, int(ys.max()) + pad + 1)
    ink_crop = clean[top:bottom, left:right]
    ys2, xs2 = np.where(ink_crop > 0)
    if len(xs2) < 12:
        return canvas

    ink_rgb = np.full((ink_crop.shape[0], ink_crop.shape[1], 3), 255, np.uint8)
    ink_rgb[ink_crop > 0] = (20, 20, 20)
    cropped = Image.fromarray(ink_rgb, "RGB").crop((int(xs2.min()), int(ys2.min()), int(xs2.max()) + 1, int(ys2.max()) + 1))
    cropped = cropped.filter(ImageFilter.UnsharpMask(radius=1, percent=110, threshold=2))
    cropped.thumbnail((size[0] - 12, size[1] - 12), Image.Resampling.LANCZOS)
    canvas.paste(cropped, ((size[0] - cropped.width) // 2, (size[1] - cropped.height) // 2))
    return canvas
