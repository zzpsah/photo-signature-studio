"""Enhanced Streamlit entrypoint layered over the existing web application."""
from __future__ import annotations

import io
from pathlib import Path

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


def _gemini_crop(image: Image.Image, target: str, api_key: str):
    if not api_key:
        return image, None
    bio = io.BytesIO()
    image.convert("RGB").save(bio, "JPEG", quality=88, optimize=True)
    result = locate_region(bio.getvalue(), target, api_key, "image/jpeg")
    if result.get("found"):
        return crop_box(image, result["box_2d"], padding=0.015), result
    return image, result


def process_media_for_assets(uploaded, processor, label: str, width: int, height: int, max_kb: int, face_crop: bool = False, ai_crop: bool = True, gemini_key: str = ""):
    raw = uploaded.getvalue()
    if uploaded.name.lower().endswith(".pdf"):
        pages = base.pdf_to_images(raw)
        page = st.number_input(f"{label} PDF page", 1, len(pages), 1, key=f"{label}_pdf_page_{uploaded.name}")
        image = pages[int(page) - 1]
    else:
        image = Image.open(io.BytesIO(raw))
    image = ImageOps.exif_transpose(image.convert("RGB"))
    detection = None
    if ai_crop and gemini_key:
        target = "the student's passport photograph/photo box" if label == "Photo" else "the student's handwritten/signature specimen box"
        try:
            image, detection = _gemini_crop(image, target, gemini_key)
            if detection and detection.get("found"):
                st.success(f"AI auto-crop: {detection.get('label', label)} — confidence {detection.get('confidence', 0):.0%}")
            elif detection:
                st.warning(f"AI could not confidently locate the {label.lower()} on this page; using fallback processing.")
        except GeminiCropError as exc:
            st.warning(f"Gemini auto-crop unavailable: {exc}")
    if label == "Photo":
        result = processor(image, width, height, face_crop and not bool(detection and detection.get("found")))
    else:
        result = processor(image, width, height)
    filename = f"{Path(uploaded.name).stem}_page_{page}_{label.lower()}.jpg" if uploaded.name.lower().endswith(".pdf") else f"{Path(uploaded.name).stem}_{label.lower()}.jpg"
    return [(filename, base.encode_jpeg_under_kb(result, max_kb))]


def _drive_controls(kind: str, outputs: list[tuple[str, bytes]]):
    folder_id = get_folder_id(_secrets())
    enabled = st.checkbox(f"☁ Upload {kind.lower()} to Google Drive", False, key=f"drive_{kind.lower()}")
    if not enabled:
        return
    if not folder_id:
        st.info("Google Drive is not configured yet. Add GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON and GOOGLE_DRIVE_FOLDER_ID to Streamlit Secrets.")
        return
    if st.button(f"UPLOAD {kind.upper()} TO DRIVE", type="secondary", key=f"upload_{kind.lower()}"):
        progress = st.progress(0)
        uploaded = []
        for index, (filename, payload) in enumerate(outputs):
            try:
                meta = upload_bytes(filename, payload, "image/jpeg", folder_id=folder_id, secrets=_secrets())
                uploaded.append(meta)
            except GoogleDriveError as exc:
                st.error(str(exc))
                break
            progress.progress((index + 1) / len(outputs))
        if uploaded:
            st.success(f"Uploaded {len(uploaded)} {kind.lower()} file(s) to Google Drive.")
            for item in uploaded:
                if item.get("webViewLink"):
                    st.write(item["webViewLink"])


def main():
    st.set_page_config(page_title=base.APP_TITLE, page_icon="📷", layout="wide")
    st.title("📷 Photo & Signature Studio")
    st.caption("Online version — automatic crop, PDF extraction, OCR, photo/signature processing, Drive upload, and student verification.")
    tabs = st.tabs(["📷 Photo", "✍ Signature", "📄 Student Form / OCR", "🔎 Reference Match"])
    gemini_key = get_gemini_key(_secrets())

    with tabs[0]:
        st.subheader("Photo processing")
        preset = st.selectbox("Preset", list(base.PHOTO_PRESETS), key="photo_preset_auto")
        width, height, max_kb = base.PHOTO_PRESETS[preset]
        face_crop = st.checkbox("Automatic face crop fallback", True, key="photo_face_auto")
        ai_crop = st.checkbox("🤖 AI auto-detect & crop photo from form/PDF", True, key="photo_ai_crop")
        if ai_crop and not gemini_key:
            st.caption("Add GEMINI_API_KEY in Streamlit Secrets to enable AI region detection. Normal face-crop still works without it.")
        files = st.file_uploader("Upload student photo or form PDF", type=["pdf", "jpg", "jpeg", "png", "webp", "bmp", "tif", "tiff"], accept_multiple_files=True, key="photos_auto")
        if files and st.button("PROCESS PHOTOS", type="primary", key="process_photos_auto"):
            outputs, progress = [], st.progress(0)
            for index, uploaded in enumerate(files):
                outputs.extend(process_media_for_assets(uploaded, base.process_photo, "Photo", width, height, max_kb, face_crop, ai_crop, gemini_key))
                progress.progress((index + 1) / len(files))
            st.success(f"Processed {len(outputs)} photo asset(s).")
            if outputs:
                st.image(Image.open(io.BytesIO(outputs[0][1])), caption=outputs[0][0], width=220)
                st.download_button("⬇ Download photos (ZIP)", base.zip_outputs(outputs), "photos_processed.zip", "application/zip")
                _drive_controls("Photos", outputs)

    with tabs[1]:
        st.subheader("Signature processing")
        preset = st.selectbox("Preset", list(base.SIGNATURE_PRESETS), key="signature_preset_auto")
        width, height, max_kb = base.SIGNATURE_PRESETS[preset]
        ai_crop = st.checkbox("🤖 AI auto-detect & crop signature from form/PDF", True, key="signature_ai_crop")
        files = st.file_uploader("Upload signature image or form PDF", type=["pdf", "jpg", "jpeg", "png", "webp", "bmp", "tif", "tiff"], accept_multiple_files=True, key="signatures_auto")
        if files and st.button("PROCESS SIGNATURES", type="primary", key="process_signatures_auto"):
            outputs, progress = [], st.progress(0)
            for index, uploaded in enumerate(files):
                outputs.extend(process_media_for_assets(uploaded, base.process_signature, "Signature", width, height, max_kb, False, ai_crop, gemini_key))
                progress.progress((index + 1) / len(files))
            st.success(f"Processed {len(outputs)} signature asset(s).")
            if outputs:
                st.image(Image.open(io.BytesIO(outputs[0][1])), caption=outputs[0][0], width=300)
                st.download_button("⬇ Download signatures (ZIP)", base.zip_outputs(outputs), "signatures_processed.zip", "application/zip")
                _drive_controls("Signatures", outputs)

    with tabs[2]:
        base_form_tab()
    with tabs[3]:
        base_reference_tab()


def base_form_tab():
    st.subheader("Student Form → Prepare → Chandra OCR")
    st.info("Use the document editor for photographed/scanned BSEB-style forms. Correct the page before OCR; then compare extracted values with the Supabase reference record. No value is silently overwritten.")
    api_key = base.get_datalab_key() or st.text_input("Datalab API key", type="password", help="For testing only. Do not commit this key to GitHub.")
    form_file = st.file_uploader("Upload hardcopy scan / phone photo / PDF", type=["pdf", "jpg", "jpeg", "png", "webp"], key="form_auto")
    if not form_file:
        st.caption("Recommended flow: photograph/scan → automatic correction → Chandra OCR → field verification → photo/signature processing → BSEB preparation.")
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
        st.divider()
        if st.button("RUN CHANDRA OCR ON PREPARED FORM", type="primary"):
            if not api_key:
                st.error("Enter a Datalab API key first.")
            else:
                with st.spinner("Sending prepared form to Chandra OCR…"):
                    try:
                        result = base.run_chandra_ocr(f"{Path(form_file.name).stem}.jpg", prepared, api_key)
                        markdown = result.get("markdown") or ""
                        st.success(f"OCR completed — {edit_summary}")
                        st.metric("Pages", result.get("page_count", 1))
                        if result.get("parse_quality_score") is not None:
                            st.metric("Parse quality", result["parse_quality_score"])
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
