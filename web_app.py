from __future__ import annotations

import io
import os
import time
import zipfile
from pathlib import Path

import cv2
import fitz
import numpy as np
import requests
import streamlit as st
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from core.form_editor import FormEditSettings, apply_settings, estimate_deskew_angle, perspective_correct, prepare_jpeg
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


def render_pdf_page(payload: bytes, page_index: int) -> Image.Image:
    document = fitz.open(stream=payload, filetype="pdf")
    try:
        page = document.load_page(page_index)
        pix = page.get_pixmap(matrix=fitz.Matrix(2.2, 2.2), alpha=False)
        return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    finally:
        document.close()


def form_editor(original: Image.Image, editor_key: str) -> tuple[bytes, str]:
    if st.session_state.get("form_editor_key") != editor_key:
        st.session_state.form_editor_key = editor_key
        st.session_state.form_editor_settings = FormEditSettings()

    settings: FormEditSettings = st.session_state.form_editor_settings
    st.markdown("#### 🛠 Document editor — prepare before OCR")
    st.caption("This mode is designed for photographed/scanned forms: rotate, straighten, detect the paper boundary, remove borders, and clean uneven lighting before OCR. The uploaded original is never changed.")

    c1, c2, c3, c4, c5 = st.columns(5)
    if c1.button("↶ Left", use_container_width=True, key=f"left_{editor_key}"):
        settings.quarter_turns -= 1
        st.rerun()
    if c2.button("↷ Right", use_container_width=True, key=f"right_{editor_key}"):
        settings.quarter_turns += 1
        st.rerun()
    if c3.button("📐 Auto deskew", use_container_width=True, key=f"deskew_{editor_key}"):
        working = original
        if settings.perspective:
            working, _ = perspective_correct(working)
        settings.deskew_angle = estimate_deskew_angle(working)
        st.rerun()
    if c4.button("▱ Detect page", use_container_width=True, key=f"perspective_{editor_key}"):
        settings.perspective = True
        st.rerun()
    if c5.button("↺ Reset", use_container_width=True, key=f"reset_{editor_key}"):
        st.session_state.form_editor_settings = FormEditSettings()
        st.rerun()

    st.write(f"**Current correction:** quarter turns {settings.quarter_turns % 4}, deskew {settings.deskew_angle:+.2f}°, fine rotation {settings.fine_angle:+.1f}°")
    settings.fine_angle = st.slider("Fine rotation / straighten", -15.0, 15.0, float(settings.fine_angle), 0.1, key=f"fine_{editor_key}")

    st.markdown("**Crop unwanted paper/background**")
    a, b = st.columns(2)
    settings.crop_left = a.slider("Left edge", 0, 40, int(settings.crop_left), key=f"crop_l_{editor_key}")
    settings.crop_right = b.slider("Right edge", 60, 100, int(settings.crop_right), key=f"crop_r_{editor_key}")
    c, d = st.columns(2)
    settings.crop_top = c.slider("Top edge", 0, 40, int(settings.crop_top), key=f"crop_t_{editor_key}")
    settings.crop_bottom = d.slider("Bottom edge", 60, 100, int(settings.crop_bottom), key=f"crop_b_{editor_key}")
    if settings.crop_right <= settings.crop_left or settings.crop_bottom <= settings.crop_top:
        st.error("Crop edges must leave a positive page area.")
        settings.crop_left, settings.crop_top, settings.crop_right, settings.crop_bottom = 0, 0, 100, 100

    a, b, c = st.columns(3)
    settings.brightness = a.slider("Brightness", 0.6, 1.6, float(settings.brightness), 0.05, key=f"bright_{editor_key}")
    settings.contrast = b.slider("Contrast", 0.6, 1.8, float(settings.contrast), 0.05, key=f"contrast_{editor_key}")
    settings.sharpness = c.slider("Sharpness", 0.6, 1.8, float(settings.sharpness), 0.05, key=f"sharp_{editor_key}")
    a, b = st.columns(2)
    settings.grayscale = a.checkbox("Grayscale", bool(settings.grayscale), key=f"gray_{editor_key}")
    settings.cleanup = b.checkbox("Uneven-lighting / scan cleanup", bool(settings.cleanup), key=f"clean_{editor_key}")

    preview = apply_settings(original, settings)
    st.image(preview, caption=f"Prepared OCR preview — {preview.width} × {preview.height}px", width="stretch")
    prepared = prepare_jpeg(preview)
    summary = f"quarter turns {settings.quarter_turns % 4}, deskew {settings.deskew_angle:+.2f}°, fine {settings.fine_angle:+.1f}°, page detection {'on' if settings.perspective else 'off'}"
    st.download_button("⬇ Download prepared page", prepared, "prepared_form.jpg", "image/jpeg", key=f"download_{editor_key}")
    return prepared, summary


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
        st.info("Use the document editor for photographed/scanned BSEB-style forms. Correct the page before OCR; then compare extracted values with the Supabase reference record. No value is silently overwritten.")
        api_key = get_datalab_key() or st.text_input("Datalab API key", type="password", help="For testing only. Do not commit this key to GitHub.")
        form_file = st.file_uploader("Upload hardcopy scan / phone photo / PDF", type=["pdf", "jpg", "jpeg", "png", "webp"], key="form")
        if form_file:
            raw = form_file.getvalue()
            is_pdf = form_file.name.lower().endswith(".pdf")
            if is_pdf:
                document = fitz.open(stream=raw, filetype="pdf")
                page_count = len(document)
                document.close()
                st.success(f"PDF detected: {page_count} page(s). You can prepare a page individually or send the complete PDF to Chandra.")
                page_no = st.number_input("Page to edit", min_value=1, max_value=page_count, value=1, step=1)
                page_image = render_pdf_page(raw, int(page_no) - 1)
                prepared, edit_summary = form_editor(page_image, f"{form_file.name}:{page_no}:{len(raw)}")
                st.divider()
                b1, b2 = st.columns(2)
                if b1.button("OCR THIS PREPARED PAGE", type="primary", use_container_width=True):
                    if not api_key:
                        st.error("Enter a Datalab API key first.")
                    else:
                        with st.spinner("Sending prepared page to Chandra OCR…"):
                            try:
                                result = run_chandra_ocr(f"{Path(form_file.name).stem}_page_{page_no}.jpg", prepared, api_key)
                                markdown = result.get("markdown") or ""
                                st.success(f"OCR completed — {edit_summary}")
                                st.markdown(markdown or "No markdown text returned.")
                                st.download_button("⬇ Download OCR Markdown", markdown, f"{Path(form_file.name).stem}_page_{page_no}_ocr.md", "text/markdown")
                            except Exception as exc:
                                st.error(f"OCR failed: {exc}")
                if b2.button("OCR COMPLETE ORIGINAL PDF", use_container_width=True):
                    if not api_key:
                        st.error("Enter a Datalab API key first.")
                    else:
                        with st.spinner("Sending complete PDF to Chandra OCR…"):
                            try:
                                result = run_chandra_ocr(form_file.name, raw, api_key)
                                markdown = result.get("markdown") or ""
                                st.success("Complete PDF OCR completed.")
                                st.markdown(markdown or "No markdown text returned.")
                                st.download_button("⬇ Download full OCR Markdown", markdown, f"{Path(form_file.name).stem}_ocr.md", "text/markdown")
                            except Exception as exc:
                                st.error(f"OCR failed: {exc}")
            else:
                prepared, edit_summary = form_editor(ImageOps.exif_transpose(Image.open(io.BytesIO(raw)).convert("RGB")), f"{form_file.name}:{len(raw)}")
                st.divider()
                if st.button("RUN CHANDRA OCR ON PREPARED FORM", type="primary"):
                    if not api_key:
                        st.error("Enter a Datalab API key first.")
                    else:
                        with st.spinner("Sending prepared form to Chandra OCR…"):
                            try:
                                result = run_chandra_ocr(f"{Path(form_file.name).stem}.jpg", prepared, api_key)
                                markdown = result.get("markdown") or ""
                                st.success(f"OCR completed — {edit_summary}")
                                st.metric("Pages", result.get("page_count", 1))
                                if result.get("parse_quality_score") is not None:
                                    st.metric("Parse quality", result["parse_quality_score"])
                                st.markdown(markdown or "No markdown text returned.")
                                st.download_button("⬇ Download OCR Markdown", markdown, f"{Path(form_file.name).stem}_ocr.md", "text/markdown")
                            except Exception as exc:
                                st.error(f"OCR failed: {exc}")
        st.caption("Recommended flow for this type of form: photograph/scan → document correction → Chandra OCR → field-by-field verification → photo/signature processing → BSEB preparation.")

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
