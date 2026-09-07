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

PHOTO_PRESETS = {
    "Photo 200×230 px / 50 KB": (200, 230, 50),
    "Photo 300×400 px / 100 KB": (300, 400, 100),
}
SIGNATURE_PRESETS = {
    "Signature 140×60 px / 20 KB": (140, 60, 20),
    "Signature 300×100 px / 50 KB": (300, 100, 50),
}


def encode_jpeg_under_kb(image: Image.Image, max_kb: int) -> bytes:
    limit = max_kb * 1024
    lo, hi = 10, 96
    best = None
    while lo <= hi:
        quality = (lo + hi) // 2
        bio = io.BytesIO()
        image.save(bio, "JPEG", quality=quality, optimize=True, subsampling=0)
        payload = bio.getvalue()
        if len(payload) <= limit:
            best = payload
            lo = quality + 1
        else:
            hi = quality - 1
    if best is None:
        bio = io.BytesIO()
        image.save(bio, "JPEG", quality=10, optimize=True)
        return bio.getvalue()
    return best


def detect_face_box(image: Image.Image):
    gray = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
    cascade_path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
    cascade = cv2.CascadeClassifier(cascade_path)
    if cascade.empty():
        return None
    faces = cascade.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
    cx = x + w / 2
    return (
        max(0, int(cx - w * 1.45)),
        max(0, int(y - h * 0.70)),
        min(image.width, int(cx + w * 1.45)),
        min(image.height, int(y + h * 2.2)),
    )


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
        crop = image.crop((
            max(0, int(xs.min()) - pad),
            max(0, int(ys.min()) - pad),
            min(image.width, int(xs.max()) + pad + 1),
            min(image.height, int(ys.max()) + pad + 1),
        ))
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
    response = requests.post(
        f"{DATALAB_BASE}/convert",
        headers=headers,
        files={"file": (file_name, payload, mime)},
        data={"output_format": "markdown", "mode": "balanced", "paginate": "true"},
        timeout=120,
    )
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


def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="📷", layout="wide")
    st.title("📷 Photo & Signature Studio")
    st.caption("Browser-first test version — batch processing without waiting for a Windows/Android build.")

    tabs = st.tabs(["📷 Photo", "✍ Signature", "📄 Student Form / OCR", "🔎 Reference Match"])

    with tabs[0]:
        st.subheader("Batch photo processing")
        preset = st.selectbox("Preset", list(PHOTO_PRESETS))
        width, height, max_kb = PHOTO_PRESETS[preset]
        face_crop = st.checkbox("Automatic face crop", True)
        files = st.file_uploader("Upload one or more student photos", type=["jpg", "jpeg", "png", "webp", "bmp", "tif", "tiff"], accept_multiple_files=True, key="photos")
        if files and st.button("PROCESS PHOTOS", type="primary"):
            outputs = []
            progress = st.progress(0)
            for index, uploaded in enumerate(files):
                image = Image.open(uploaded)
                result = process_photo(image, width, height, face_crop)
                payload = encode_jpeg_under_kb(result, max_kb)
                stem = Path(uploaded.name).stem
                outputs.append((f"{stem}_photo.jpg", payload))
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
            outputs = []
            progress = st.progress(0)
            for index, uploaded in enumerate(files):
                result = process_signature(Image.open(uploaded), width, height)
                payload = encode_jpeg_under_kb(result, max_kb)
                outputs.append((f"{Path(uploaded.name).stem}_signature.jpg", payload))
                progress.progress((index + 1) / len(files))
            st.success(f"Processed {len(outputs)} signature(s).")
            if outputs:
                st.image(Image.open(io.BytesIO(outputs[0][1])), caption=outputs[0][0], width=300)
                st.download_button("⬇ Download all signatures (ZIP)", zip_outputs(outputs), "signatures_processed.zip", "application/zip")

    with tabs[2]:
        st.subheader("Student Form → Chandra OCR")
        st.info("The OCR key is kept server-side. The form is sent to Datalab/Chandra only when you press Run OCR.")
        api_key = get_datalab_key()
        if not api_key:
            api_key = st.text_input("Datalab API key", type="password", help="For testing only. Do not commit this key to GitHub.")
        form_file = st.file_uploader("Upload hardcopy scan / photo / PDF", type=["pdf", "jpg", "jpeg", "png", "webp"], key="form")
        if form_file and st.button("RUN CHANDRA OCR", type="primary"):
            if not api_key:
                st.error("Enter a Datalab API key first.")
            else:
                with st.spinner("Sending form to Chandra OCR and waiting for result…"):
                    try:
                        result = run_chandra_ocr(form_file.name, form_file.getvalue(), api_key)
                        markdown = result.get("markdown") or ""
                        st.success("OCR completed.")
                        st.metric("Pages", result.get("page_count", "—"))
                        if result.get("parse_quality_score") is not None:
                            st.metric("Parse quality", result["parse_quality_score"])
                        st.markdown(markdown or "No markdown text returned.")
                        st.download_button("⬇ Download OCR Markdown", markdown, f"{Path(form_file.name).stem}_ocr.md", "text/markdown")
                    except Exception as exc:
                        st.error(f"OCR failed: {exc}")
        st.caption("Next step after this web test: map the OCR result into verified student fields and compare them with the Supabase Class X reference record. No value will be silently overwritten.")

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
        st.caption(f"Reference table: {DEFAULT_TABLE}. This is reference data; hardcopy/OCR data remains separate until verified.")


if __name__ == "__main__":
    main()
