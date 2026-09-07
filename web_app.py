from __future__ import annotations

import io
import os
import time
import zipfile
from pathlib import Path

import cv2
import numpy as np
import requests
import streamlit as st
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from core.supabase_client import DEFAULT_TABLE, SupabaseClient, SupabaseError

APP_TITLE = "Photo & Signature Studio — Web"
DATALAB_BASE = "https://www.datalab.to/api/v1"
PHOTO_PRESETS = {"Photo 200×230 px / 50 KB": (200, 230, 50), "Photo 300×400 px / 100 KB": (300, 400, 100)}
SIGNATURE_PRESETS = {"Signature 140×60 px / 20 KB": (140, 60, 20), "Signature 300×100 px / 50 KB": (300, 100, 50)}


def encode_jpeg_under_kb(image: Image.Image, max_kb: int) -> bytes:
    limit, lo, hi, best = max_kb * 1024, 10, 96, None
    while lo <= hi:
        quality = (lo + hi) // 2
        bio = io.BytesIO()
        image.save(bio, "JPEG", quality=quality, optimize=True, subsampling=0)
        payload = bio.getvalue()
        if len(payload) <= limit:
            best, lo = payload, quality + 1
        else:
            hi = quality - 1
    if best is not None:
        return best
    bio = io.BytesIO()
    image.save(bio, "JPEG", quality=10, optimize=True)
    return bio.getvalue()


def detect_face_box(image: Image.Image):
    gray = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
    cascade = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml"))
    if cascade.empty():
        return None
    faces = cascade.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
    cx = x + w / 2
    return (max(0, int(cx - w * 1.45)), max(0, int(y - h * 0.70)), min(image.width, int(cx + w * 1.45)), min(image.height, int(y + h * 2.2)))


def process_photo(image: Image.Image, width: int, height: int, face_crop: bool) -> Image.Image:
    image = ImageOps.exif_transpose(image.convert("RGB"))
    image = ImageEnhance.Contrast(image).enhance(1.03)
    image = ImageEnhance.Sharpness(image).enhance(1.05)
    if face_crop:
        box = detect_face_box(image)
        if box:
            image = image.crop(box)
    return ImageOps.fit(image, (width, height), method=Image.Resampling.LANCZOS, centering=(0.5, 0.42))


def process_signature(image: Image.Image, width: int, height: int) -> Image.Image:
    image = ImageOps.exif_transpose(image.convert("RGB"))
    gray = np.array(image.convert("L"))
    smooth = cv2.GaussianBlur(gray, (0, 0), sigmaX=15)
    normalized = cv2.divide(gray, smooth, scale=255)
    _, ink = cv2.threshold(normalized, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    ink = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))
    ys, xs = np.where(ink > 0)
    if len(xs) > 25:
        pad = max(4, int(min(image.size) * 0.015))
        crop = image.crop((max(0, int(xs.min()) - pad), max(0, int(ys.min()) - pad), min(image.width, int(xs.max()) + pad + 1), min(image.height, int(ys.max()) + pad + 1)))
    else:
        crop = image
    crop = crop.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3))
    crop.thumbnail((width, height), Image.Resampling.LANCZOS)
    result = Image.new("RGB", (width, height), "white")
    result.paste(crop, ((width - crop.width) // 2, (height - crop.height) // 2))
    return result


def zip_outputs(outputs: list[tuple[str, bytes]]) -> bytes:
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename, payload in outputs:
            archive.writestr(filename, payload)
    return bio.getvalue()


def get_datalab_key() -> str:
    try:
        configured = st.secrets.get("DATALAB_API_KEY", "")
    except Exception:
        configured = ""
    return configured or os.getenv("DATALAB_API_KEY", "")


def run_chandra_ocr(file_name: str, payload: bytes, api_key: str) -> dict:
    headers = {"X-API-Key": api_key}
    mime = "application/pdf" if file_name.lower().endswith(".pdf") else "image/jpeg"
    response = requests.post(f"{DATALAB_BASE}/convert", headers=headers, files={"file": (file_name, payload, mime)}, data={"output_format": "markdown", "mode": "balanced", "paginate": "true"}, timeout=120)
    response.raise_for_status()
    submitted = response.json()
    if not submitted.get("success", True):
        raise RuntimeError(submitted.get("error") or "Chandra OCR request failed")
    check_url = submitted.get("request_check_url") or f"{DATALAB_BASE}/convert/{submitted['request_id']}"
    for _ in range(90):
        result = requests.get(check_url, headers=headers, timeout=60)
        result.raise_for_status()
        data = result.json()
        if data.get("status") == "complete":
            return data
        if data.get("status") in {"failed", "error"}:
            raise RuntimeError(data.get("error") or "Chandra OCR processing failed")
        time.sleep(2)
    raise TimeoutError("Chandra OCR did not finish within 3 minutes")


def rotate_image(image: Image.Image, angle: float) -> Image.Image:
    return image.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC, fillcolor="white")


def auto_deskew(image: Image.Image) -> tuple[Image.Image, float]:
    gray = cv2.GaussianBlur(np.array(image.convert("L")), (3, 3), 0)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 1800, threshold=max(60, min(gray.shape) // 4), minLineLength=max(80, min(gray.shape) // 3), maxLineGap=20)
    if lines is None:
        return image, 0.0
    angles = []
    for x1, y1, x2, y2 in lines[:, 0]:
        angle = float(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
        if -15 <= angle <= 15:
            angles.append(angle)
    if not angles:
        return image, 0.0
    correction = -float(np.median(angles))
    return (rotate_image(image, correction), correction) if abs(correction) >= 0.15 else (image, 0.0)


def crop_image(image: Image.Image, left: int, top: int, right: int, bottom: int) -> Image.Image:
    w, h = image.size
    return image.crop((int(w * left / 100), int(h * top / 100), int(w * right / 100), int(h * bottom / 100)))


def form_editor(uploaded) -> tuple[bytes, str]:
    """Prepare a scanned form in-browser before sending the edited copy to OCR."""
    original = ImageOps.exif_transpose(Image.open(uploaded).convert("RGB"))
    key = f"form_editor_{uploaded.name}_{getattr(uploaded, 'size', 0)}"
    if st.session_state.get("editor_key") != key:
        st.session_state.editor_key = key
        st.session_state.editor_image = original

    base = st.session_state.editor_image
    st.markdown("#### 🛠 Form editor — prepare before OCR")
    st.caption("Correct orientation, straighten the page, crop borders, and improve readability here. The original upload is never modified.")
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("↶ Rotate left", use_container_width=True):
        base = base.rotate(90, expand=True)
    if c2.button("↷ Rotate right", use_container_width=True):
        base = base.rotate(-90, expand=True)
    if c3.button("✨ Auto deskew", use_container_width=True):
        base, correction = auto_deskew(base)
        st.toast(f"Deskew correction: {correction:+.2f}°")
    if c4.button("↺ Reset", use_container_width=True):
        base = original.copy()

    angle = st.slider("Fine rotation / straighten", -15.0, 15.0, 0.0, 0.1)
    crop_enabled = st.checkbox("Crop page / remove unwanted borders", False)
    if crop_enabled:
        a, b = st.columns(2)
        left = a.slider("Left", 0, 40, 0)
        right = b.slider("Right", 60, 100, 100)
        c, d = st.columns(2)
        top = c.slider("Top", 0, 40, 0)
        bottom = d.slider("Bottom", 60, 100, 100)
        if right > left and bottom > top:
            base = crop_image(base, left, top, right, bottom)

    c1, c2, c3 = st.columns(3)
    brightness = c1.slider("Brightness", 0.6, 1.6, 1.0, 0.05)
    contrast = c2.slider("Contrast", 0.6, 1.8, 1.0, 0.05)
    sharpness = c3.slider("Sharpness", 0.6, 1.8, 1.0, 0.05)
    grayscale = st.checkbox("Grayscale", False)
    clean = st.checkbox("Light scan cleanup", True)

    image = rotate_image(base, angle) if angle else base.copy()
    if brightness != 1:
        image = ImageEnhance.Brightness(image).enhance(brightness)
    if contrast != 1:
        image = ImageEnhance.Contrast(image).enhance(contrast)
    if sharpness != 1:
        image = ImageEnhance.Sharpness(image).enhance(sharpness)
    if grayscale:
        image = ImageOps.grayscale(image).convert("RGB")
    if clean:
        image = Image.fromarray(cv2.fastNlMeansDenoisingColored(np.array(image), None, 4, 4, 7, 21))
        image = ImageEnhance.Contrast(image).enhance(1.06)

    st.session_state.editor_image = image
    st.image(image, caption=f"OCR preview — {image.width} × {image.height}px", width="stretch")
    bio = io.BytesIO()
    image.save(bio, "JPEG", quality=95)
    summary = f"rotation {angle:+.1f}°, crop {'on' if crop_enabled else 'off'}, grayscale {'on' if grayscale else 'off'}"
    return bio.getvalue(), summary


def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="📷", layout="wide")
    st.title("📷 Photo & Signature Studio")
    st.caption("Online version — prepare forms, OCR them, process photos/signatures, and verify student data.")
    tabs = st.tabs(["📷 Photo", "✍ Signature", "📄 Student Form / OCR", "🔎 Reference Match"])

    with tabs[0]:
        st.subheader("Batch photo processing")
        preset = st.selectbox("Preset", list(PHOTO_PRESETS))
        width, height, max_kb = PHOTO_PRESETS[preset]
        face_crop = st.checkbox("Automatic face crop", True)
        files = st.file_uploader("Upload one or more student photos", type=["jpg", "jpeg", "png", "webp", "bmp", "tif", "tiff"], accept_multiple_files=True, key="photos")
        if files and st.button("PROCESS PHOTOS", type="primary"):
            outputs, progress = [], st.progress(0)
            for index, uploaded in enumerate(files):
                result = process_photo(Image.open(uploaded), width, height, face_crop)
                outputs.append((f"{Path(uploaded.name).stem}_photo.jpg", encode_jpeg_under_kb(result, max_kb)))
                progress.progress((index + 1) / len(files))
            st.success(f"Processed {len(outputs)} photo(s).")
            if outputs:
                st.image(Image.open(io.BytesIO(outputs[0][1])), caption=outputs[0][0], width=220)
                st.download_button("⬇ Download all photos (ZIP)", zip_outputs(outputs), "photos_processed.zip", "application/zip")

    with tabs[1]:
        st.subheader("Batch signature processing")
        preset = st.selectbox("Preset", list(SIGNATURE_PRESETS))
        width, height, max_kb = SIGNATURE_PRESETS[preset]
        files = st.file_uploader("Upload one or more signature images", type=["jpg", "jpeg", "png", "webp", "bmp", "tif", "tiff"], accept_multiple_files=True, key="signatures")
        if files and st.button("PROCESS SIGNATURES", type="primary"):
            outputs, progress = [], st.progress(0)
            for index, uploaded in enumerate(files):
                result = process_signature(Image.open(uploaded), width, height)
                outputs.append((f"{Path(uploaded.name).stem}_signature.jpg", encode_jpeg_under_kb(result, max_kb)))
                progress.progress((index + 1) / len(files))
            st.success(f"Processed {len(outputs)} signature(s).")
            if outputs:
                st.image(Image.open(io.BytesIO(outputs[0][1])), caption=outputs[0][0], width=300)
                st.download_button("⬇ Download all signatures (ZIP)", zip_outputs(outputs), "signatures_processed.zip", "application/zip")

    with tabs[2]:
        st.subheader("Student Form → Prepare → Chandra OCR")
        st.info("Upload the hardcopy scan, correct its rotation/crop/readability in the editor, then send the prepared copy to Chandra. The original remains unchanged.")
        api_key = get_datalab_key() or st.text_input("Datalab API key", type="password", help="For testing only. Do not commit this key to GitHub.")
        form_file = st.file_uploader("Upload hardcopy scan / photo / PDF", type=["pdf", "jpg", "jpeg", "png", "webp"], key="form")
        if form_file:
            if form_file.name.lower().endswith(".pdf"):
                st.warning("PDFs are sent directly to Chandra in this version. For manual editing, upload/export the page as an image first.")
                prepared, edit_summary = form_file.getvalue(), "PDF unchanged"
            else:
                prepared, edit_summary = form_editor(form_file)
            st.divider()
            if st.button("RUN CHANDRA OCR ON PREPARED FORM", type="primary"):
                if not api_key:
                    st.error("Enter a Datalab API key first.")
                else:
                    with st.spinner("Sending prepared form to Chandra OCR…"):
                        try:
                            result = run_chandra_ocr(form_file.name, prepared, api_key)
                            markdown = result.get("markdown") or ""
                            st.success(f"OCR completed — {edit_summary}")
                            st.metric("Pages", result.get("page_count", "—"))
                            if result.get("parse_quality_score") is not None:
                                st.metric("Parse quality", result["parse_quality_score"])
                            st.markdown(markdown or "No markdown text returned.")
                            st.download_button("⬇ Download OCR Markdown", markdown, f"{Path(form_file.name).stem}_ocr.md", "text/markdown")
                        except Exception as exc:
                            st.error(f"OCR failed: {exc}")
        st.caption("Next step: map OCR into verified student fields and compare them with the Supabase Class X reference record. No value is silently overwritten.")

    with tabs[3]:
        st.subheader("Supabase Class X reference lookup")
        query = st.text_input("Application No / Name / Father Name / Mother Name")
        if st.button("FIND STUDENT"):
            if not query.strip():
                st.warning("Enter a search value.")
            else:
                try:
                    rows = SupabaseClient().search_students(query.strip(), limit=20)
                    if rows:
                        st.dataframe(rows, use_container_width=True)
                    else:
                        st.info("No matching reference record found.")
                except SupabaseError as exc:
                    st.error(str(exc))
        st.caption(f"Reference table: {DEFAULT_TABLE}. Hardcopy/OCR data remains separate until verified.")


if __name__ == "__main__":
    main()
