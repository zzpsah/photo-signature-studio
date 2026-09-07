"""Enhanced Streamlit entrypoint for automatic photo/signature extraction."""
from __future__ import annotations

import io
from pathlib import Path

import cv2
import numpy as np
import streamlit as st
from PIL import Image, ImageOps

import web_app as base
from core.gemini_crop import GeminiCropError, crop_box, get_gemini_key, locate_region
from core.google_drive import GoogleDriveError, get_folder_id, upload_bytes


def _secrets():
    try:
        return st.secrets
    except Exception:
        return None


def _white_background(image: Image.Image) -> Image.Image:
    """Remove the portrait background as far as practical and replace it with white."""
    image = ImageOps.exif_transpose(image.convert("RGB"))
    arr = np.asarray(image).copy()
    h, w = arr.shape[:2]
    if h < 80 or w < 80:
        return image

    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = cascade.detectMultiScale(gray, 1.08, 5, minSize=(max(24, w // 12), max(24, h // 12))) if not cascade.empty() else ()
    if len(faces) == 0:
        # If the photo already has a near-white background, normalize it to pure white.
        bg = np.all(arr > 235, axis=2)
        result = arr.copy()
        result[bg] = 255
        return Image.fromarray(result, "RGB")

    x, y, fw, fh = max(faces, key=lambda r: r[2] * r[3])
    mask = np.full((h, w), cv2.GC_BGD, np.uint8)
    # The central portrait area is probable foreground; the face is definite foreground.
    cx, cy = x + fw // 2, y + fh // 2
    axes = (max(fw * 2, w // 5), max(fh * 3, h // 3))
    cv2.ellipse(mask, (cx, min(h - 1, cy + int(fh * 1.8))), axes, 0, 0, 360, cv2.GC_PR_FGD, -1)
    cv2.rectangle(mask, (x, y), (min(w - 1, x + fw), min(h - 1, y + fh)), cv2.GC_FGD, -1)
    # Keep the extreme border as background, which helps with photographed forms.
    border = max(2, min(h, w) // 80)
    mask[:border, :] = cv2.GC_BGD
    mask[-border:, :] = cv2.GC_BGD
    mask[:, :border] = cv2.GC_BGD
    mask[:, -border:] = cv2.GC_BGD

    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(arr, mask, None, bgd, fgd, 5, cv2.GC_INIT_WITH_MASK)
        foreground = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
        foreground = cv2.morphologyEx(foreground, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        foreground = cv2.GaussianBlur(foreground, (3, 3), 0)
        white = np.full_like(arr, 255)
        alpha = foreground.astype(np.float32) / 255.0
        result = (arr * alpha[..., None] + white * (1.0 - alpha[..., None])).clip(0, 255).astype(np.uint8)
        return Image.fromarray(result, "RGB")
    except cv2.error:
        return image


def _gemini_crop(image: Image.Image, target: str, api_key: str):
    if not api_key:
        return image, None
    bio = io.BytesIO()
    image.convert("RGB").save(bio, "JPEG", quality=88, optimize=True)
    result = locate_region(bio.getvalue(), target, api_key, "image/jpeg")
    if result.get("found"):
        return crop_box(image, result["box_2d"], padding=0.01), result
    return image, result


def _process_one(image: Image.Image, label: str, width: int, height: int, max_kb: int, face_crop: bool, ai_crop: bool, gemini_key: str):
    image = ImageOps.exif_transpose(image.convert("RGB"))
    detection = None
    if ai_crop and gemini_key:
        target = (
            "the student's passport photograph/photo box. Ignore printed portraits, logos, and all other images; "
            "return only the actual student photo area."
            if label == "Photo" else
            "the student's handwritten signature specimen box. Ignore printed text, logos, stamps, and other images; "
            "return only the actual signature area."
        )
        try:
            image, detection = _gemini_crop(image, target, gemini_key)
        except GeminiCropError as exc:
            st.warning(f"Gemini auto-detection unavailable: {exc}")

    if label == "Photo":
        # AI has already isolated the photo box. Face crop is only a fallback when AI did not find it.
        result = base.process_photo(image, width, height, face_crop and not bool(detection and detection.get("found")))
        result = _white_background(result)
    else:
        result = base.process_signature(image, width, height)

    return result, detection


def process_media_for_assets(uploaded, label: str, width: int, height: int, max_kb: int, face_crop: bool, ai_crop: bool, gemini_key: str, all_pdf_pages: bool = True):
    """Process every uploaded image, or every page of a PDF when batch mode is enabled."""
    raw = uploaded.getvalue()
    is_pdf = uploaded.name.lower().endswith(".pdf")
    sources: list[tuple[int | None, Image.Image]] = []
    if is_pdf:
        pages = base.pdf_to_images(raw)
        if all_pdf_pages:
            sources = [(i + 1, page) for i, page in enumerate(pages)]
        else:
            page = st.number_input(f"{label} PDF page", 1, len(pages), 1, key=f"{label}_pdf_page_{uploaded.name}")
            sources = [(int(page), pages[int(page) - 1])]
    else:
        sources = [(None, Image.open(io.BytesIO(raw)))]

    outputs: list[tuple[str, bytes]] = []
    for page_no, image in sources:
        result, detection = _process_one(image, label, width, height, max_kb, face_crop, ai_crop, gemini_key)
        # In PDF batch mode, a page without a detected photo/signature should not create a fake asset.
        if is_pdf and ai_crop and gemini_key and not (detection and detection.get("found")):
            continue
        suffix = f"_page_{page_no}" if page_no is not None else ""
        filename = f"{Path(uploaded.name).stem}{suffix}_{label.lower()}.jpg"
        outputs.append((filename, base.encode_jpeg_under_kb(result, max_kb)))
    return outputs


def _drive_controls(kind: str, outputs: list[tuple[str, bytes]]):
    folder_id = get_folder_id(_secrets())
    enabled = st.checkbox(f"☁ Upload {kind.lower()} to Google Drive", False, key=f"drive_{kind.lower()}")
    if not enabled:
        return
    if not folder_id:
        st.info("Add GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON and GOOGLE_DRIVE_FOLDER_ID to Streamlit Secrets.")
        return
    if st.button(f"UPLOAD {kind.upper()} TO DRIVE", type="secondary", key=f"upload_{kind.lower()}"):
        progress = st.progress(0)
        uploaded = []
        for index, (filename, payload) in enumerate(outputs):
            try:
                uploaded.append(upload_bytes(filename, payload, "image/jpeg", folder_id=folder_id, secrets=_secrets()))
            except GoogleDriveError as exc:
                st.error(str(exc))
                break
            progress.progress((index + 1) / len(outputs))
        if uploaded:
            st.success(f"Uploaded {len(uploaded)} {kind.lower()} file(s) to Google Drive.")


def main():
    st.set_page_config(page_title=base.APP_TITLE, page_icon="📷", layout="wide")
    st.title("📷 Photo & Signature Studio")
    st.caption("Automatic photo/signature extraction from images and forms, batch PDF processing, OCR, verification and Drive export.")
    tabs = st.tabs(["📷 Photo", "✍ Signature", "📄 Student Form / OCR", "🔎 Reference Match"])
    gemini_key = get_gemini_key(_secrets())

    with tabs[0]:
        st.subheader("Photo processing")
        preset = st.selectbox("Preset", list(base.PHOTO_PRESETS), key="photo_preset_auto")
        width, height, max_kb = base.PHOTO_PRESETS[preset]
        face_crop = st.checkbox("Automatic face crop fallback", True, key="photo_face_auto")
        ai_crop = st.checkbox("🤖 Automatically find ONLY the student photo section", True, key="photo_ai_crop")
        all_pdf_pages = st.checkbox("📚 For PDF batches, scan all pages automatically", True, key="photo_all_pdf_pages")
        if ai_crop and not gemini_key:
            st.warning("GEMINI_API_KEY is not configured. AI photo-section detection is disabled; direct photos can still use face crop.")
        files = st.file_uploader("Upload student photos or form PDFs", type=["pdf", "jpg", "jpeg", "png", "webp", "bmp", "tif", "tiff"], accept_multiple_files=True, key="photos_auto")
        if files and st.button("PROCESS PHOTOS", type="primary", key="process_photos_auto"):
            outputs, progress = [], st.progress(0)
            for index, uploaded in enumerate(files):
                outputs.extend(process_media_for_assets(uploaded, "Photo", width, height, max_kb, face_crop, ai_crop, gemini_key, all_pdf_pages))
                progress.progress((index + 1) / len(files))
            st.success(f"Processed {len(outputs)} photo asset(s).")
            if outputs:
                st.image(Image.open(io.BytesIO(outputs[0][1])), caption=outputs[0][0], width=220)
                st.download_button("⬇ Download all photos (ZIP)", base.zip_outputs(outputs), "photos_processed.zip", "application/zip")
                _drive_controls("Photos", outputs)
            else:
                st.warning("No student photo section was detected in the uploaded PDF pages.")

    with tabs[1]:
        st.subheader("Signature processing")
        preset = st.selectbox("Preset", list(base.SIGNATURE_PRESETS), key="signature_preset_auto")
        width, height, max_kb = base.SIGNATURE_PRESETS[preset]
        ai_crop = st.checkbox("🤖 Automatically find ONLY the student signature section", True, key="signature_ai_crop")
        all_pdf_pages = st.checkbox("📚 For PDF batches, scan all pages automatically", True, key="signature_all_pdf_pages")
        files = st.file_uploader("Upload signatures or form PDFs", type=["pdf", "jpg", "jpeg", "png", "webp", "bmp", "tif", "tiff"], accept_multiple_files=True, key="signatures_auto")
        if files and st.button("PROCESS SIGNATURES", type="primary", key="process_signatures_auto"):
            outputs, progress = [], st.progress(0)
            for index, uploaded in enumerate(files):
                outputs.extend(process_media_for_assets(uploaded, "Signature", width, height, max_kb, False, ai_crop, gemini_key, all_pdf_pages))
                progress.progress((index + 1) / len(files))
            st.success(f"Processed {len(outputs)} signature asset(s).")
            if outputs:
                st.image(Image.open(io.BytesIO(outputs[0][1])), caption=outputs[0][0], width=300)
                st.download_button("⬇ Download all signatures (ZIP)", base.zip_outputs(outputs), "signatures_processed.zip", "application/zip")
                _drive_controls("Signatures", outputs)

    with tabs[2]:
        base_form_tab()
    with tabs[3]:
        base_reference_tab()


def base_form_tab():
    st.subheader("Student Form → Prepare → Chandra OCR")
    st.info("Use the document editor for photographed/scanned BSEB-style forms. Correct the page before OCR; then compare extracted values with the Supabase reference record. No value is silently overwritten.")
    api_key = base.get_datalab_key() or st.text_input("Datalab API key", type="password")
    form_file = st.file_uploader("Upload hardcopy scan / phone photo / PDF", type=["pdf", "jpg", "jpeg", "png", "webp"], key="form_auto")
    if not form_file:
        st.caption("Recommended flow: scan → automatic correction → Chandra OCR → field verification → photo/signature processing → BSEB preparation.")
        return
    raw = form_file.getvalue()
    if form_file.name.lower().endswith(".pdf"):
        document = base.fitz.open(stream=raw, filetype="pdf")
        page_count = len(document)
        document.close()
        st.success(f"PDF detected: {page_count} page(s).")
        page_no = st.number_input("Page to edit", min_value=1, max_value=page_count, value=1, step=1)
        page_image = base.render_pdf_page(raw, int(page_no) - 1)
        prepared, edit_summary = base.form_editor(page_image, f"{form_file.name}:{page_no}:{len(raw)}")
        st.divider()
        b1, b2 = st.columns(2)
        if b1.button("OCR THIS PREPARED PAGE", type="primary", use_container_width=True):
            if not api_key:
                st.error("Enter a Datalab API key first.")
            else:
                with st.spinner("Sending prepared page to Chandra OCR…"):
                    try:
                        result = base.run_chandra_ocr(f"{Path(form_file.name).stem}_page_{page_no}.jpg", prepared, api_key)
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
                        result = base.run_chandra_ocr(form_file.name, raw, api_key)
                        markdown = result.get("markdown") or ""
                        st.success("Complete PDF OCR completed.")
                        st.markdown(markdown or "No markdown text returned.")
                        st.download_button("⬇ Download full OCR Markdown", markdown, f"{Path(form_file.name).stem}_ocr.md", "text/markdown")
                    except Exception as exc:
                        st.error(f"OCR failed: {exc}")
    else:
        prepared, edit_summary = base.form_editor(ImageOps.exif_transpose(Image.open(io.BytesIO(raw)).convert("RGB")), f"{form_file.name}:{len(raw)}")
        if st.button("RUN CHANDRA OCR ON PREPARED FORM", type="primary"):
            if not api_key:
                st.error("Enter a Datalab API key first.")
            else:
                with st.spinner("Sending prepared form to Chandra OCR…"):
                    try:
                        result = base.run_chandra_ocr(f"{Path(form_file.name).stem}.jpg", prepared, api_key)
                        markdown = result.get("markdown") or ""
                        st.success(f"OCR completed — {edit_summary}")
                        st.markdown(markdown or "No markdown text returned.")
                        st.download_button("⬇ Download OCR Markdown", markdown, f"{Path(form_file.name).stem}_ocr.md", "text/markdown")
                    except Exception as exc:
                        st.error(f"OCR failed: {exc}")


def base_reference_tab():
    st.subheader("Supabase Class X reference lookup")
    query = st.text_input("Application No / Name / Father Name / Mother Name", key="reference_query_auto")
    if st.button("FIND STUDENT", key="find_student_auto"):
        if not query.strip():
            st.warning("Enter a search value.")
        else:
            try:
                rows = base.SupabaseClient().search_students(query.strip(), limit=20)
                if rows:
                    st.dataframe(rows, use_container_width=True)
                else:
                    st.info("No matching reference record found.")
            except base.SupabaseError as exc:
                st.error(str(exc))
    st.caption(f"Reference table: {base.DEFAULT_TABLE}. Hardcopy/OCR data remains separate until verified.")


if __name__ == "__main__":
    main()
