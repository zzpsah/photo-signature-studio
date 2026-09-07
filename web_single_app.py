"""Single-file student document workflow for Photo, Signature and OCR."""
from __future__ import annotations

import io
from pathlib import Path

import fitz
import streamlit as st
from PIL import Image, ImageOps

import web_app as base
from core.asset_processing import process_photo_asset, process_signature_asset
from core.gemini_crop import GeminiCropError, crop_box, get_gemini_key, locate_region
from core.google_drive import GoogleDriveError, get_folder_id, upload_bytes


def _secrets():
    try:
        return st.secrets
    except Exception:
        return None


def _pages_from_upload(name: str, raw: bytes) -> list[tuple[int, Image.Image]]:
    if name.lower().endswith(".pdf"):
        pages = base.pdf_to_images(raw)
        return [(i + 1, page) for i, page in enumerate(pages)]
    return [(1, ImageOps.exif_transpose(Image.open(io.BytesIO(raw)).convert("RGB")))]


def _find_region(image: Image.Image, target: str, api_key: str):
    bio = io.BytesIO()
    image.convert("RGB").save(bio, "JPEG", quality=88, optimize=True)
    return locate_region(bio.getvalue(), target, api_key, "image/jpeg")


def _extract_page(image: Image.Image, page_no: int, stem: str, gemini_key: str, want_photo: bool, want_signature: bool):
    photo = signature = None
    photo_detection = signature_detection = None

    if gemini_key and want_photo:
        try:
            photo_detection = _find_region(
                image,
                "the ACTUAL student's passport photograph/photo box on this form; ignore logos, printed sample portraits, ID-card graphics, stamps, and other images; return only the student photo region",
                gemini_key,
            )
            if photo_detection.get("found"):
                photo = crop_box(image, photo_detection["box_2d"], padding=0.012)
        except GeminiCropError as exc:
            st.warning(f"Photo AI detection on page {page_no}: {exc}")

    if gemini_key and want_signature:
        try:
            signature_detection = _find_region(
                image,
                "the ACTUAL student's handwritten signature specimen on this form; ignore printed text, signature labels, lines, stamps, logos and other marks; return only the signature region",
                gemini_key,
            )
            if signature_detection.get("found"):
                signature = crop_box(image, signature_detection["box_2d"], padding=0.012)
        except GeminiCropError as exc:
            st.warning(f"Signature AI detection on page {page_no}: {exc}")

    # Direct-photo fallback: face detection in the original image.
    if want_photo and photo is None:
        try:
            fallback = base.detect_face_box(image)
            if fallback:
                photo = image.crop(fallback)
        except Exception:
            pass

    photo_output = process_photo_asset(photo, (200, 230)) if photo is not None else None
    signature_output = process_signature_asset(signature, (140, 60)) if signature is not None else None
    prefix = Path(stem).stem
    if page_no > 1 or stem.lower().endswith(".pdf"):
        prefix = f"{prefix}_page_{page_no}"
    return photo_output, signature_output, photo_detection, signature_detection, prefix


def _drive_uploads(photo_bytes, signature_bytes, stem: str):
    folder_id = get_folder_id(_secrets())
    if not folder_id:
        st.error("GOOGLE_DRIVE_FOLDER_ID is missing in Streamlit Secrets.")
        return
    if not (photo_bytes or signature_bytes):
        st.warning("There are no extracted assets to upload.")
        return
    uploaded = []
    items = []
    if photo_bytes:
        items.append((f"{stem}_photo.jpg", photo_bytes))
    if signature_bytes:
        items.append((f"{stem}_signature.jpg", signature_bytes))
    progress = st.progress(0)
    for index, (filename, payload) in enumerate(items):
        try:
            uploaded.append(upload_bytes(filename, payload, "image/jpeg", folder_id=folder_id, secrets=_secrets()))
        except GoogleDriveError as exc:
            st.error(str(exc))
            return
        progress.progress((index + 1) / len(items))
    st.success(f"Uploaded {len(uploaded)} asset(s) to Google Drive.")


def _ocr(file_name: str, raw: bytes, prepared_image: Image.Image | None, api_key: str):
    if file_name.lower().endswith(".pdf"):
        return base.run_chandra_ocr(file_name, raw, api_key)
    bio = io.BytesIO()
    (prepared_image or Image.open(io.BytesIO(raw))).save(bio, "JPEG", quality=92)
    return base.run_chandra_ocr(f"{Path(file_name).stem}_prepared.jpg", bio.getvalue(), api_key)


def main():
    st.set_page_config(page_title="Photo & Signature Studio", page_icon="📷", layout="wide")
    st.title("📷 Student Document Studio")
    st.caption("Upload ONE student form/photo/PDF. The same file is used to extract Photo + Signature and run OCR.")

    gemini_key = get_gemini_key(_secrets())
    datalab_key = base.get_datalab_key()
    uploaded = st.file_uploader(
        "Upload one student file",
        type=["pdf", "jpg", "jpeg", "png", "webp", "bmp", "tif", "tiff"],
        accept_multiple_files=False,
        help="Upload one photographed/scanned form, one PDF, or one direct student photo.",
    )

    if not uploaded:
        st.info("Start here: upload one BSEB/student form. No separate photo, signature or OCR upload is required.")
        st.markdown("**Pipeline:** Upload → find photo → white background → find signature → clean signature → Chandra OCR → review/download.")
        return

    raw = uploaded.getvalue()
    pages = _pages_from_upload(uploaded.name, raw)
    st.success(f"Loaded {len(pages)} page(s) from **{uploaded.name}**.")

    with st.expander("Processing options", expanded=True):
        want_photo = st.checkbox("Extract student photo", True)
        want_signature = st.checkbox("Extract student signature", True)
        want_ocr = st.checkbox("Run Chandra OCR", True)
        use_ai = st.checkbox("Use Gemini to locate photo/signature sections", True)
        if use_ai and not gemini_key:
            st.warning("GEMINI_API_KEY is not available, so region detection will use local fallback where possible.")
        if want_ocr and not datalab_key:
            st.warning("DATALAB_API_KEY is not configured; OCR will be skipped until a key is added.")

    if st.button("🚀 PROCESS THIS FILE", type="primary", use_container_width=True):
        all_photos: list[tuple[str, bytes]] = []
        all_signatures: list[tuple[str, bytes]] = []
        photo_previews = []
        signature_previews = []
        prepared_for_ocr = pages[0][1]
        progress = st.progress(0)

        for index, (page_no, image) in enumerate(pages):
            photo, signature, photo_detection, signature_detection, prefix = _extract_page(
                image, page_no, uploaded.name, gemini_key if use_ai else "", want_photo, want_signature
            )
            if photo is not None:
                bio = io.BytesIO(); photo.save(bio, "JPEG", quality=92)
                payload = base.encode_jpeg_under_kb(photo, 50)
                all_photos.append((f"{prefix}_photo.jpg", payload)); photo_previews.append(photo)
            if signature is not None:
                bio = io.BytesIO(); signature.save(bio, "JPEG", quality=92)
                payload = base.encode_jpeg_under_kb(signature, 20)
                all_signatures.append((f"{prefix}_signature.jpg", payload)); signature_previews.append(signature)
            progress.progress((index + 1) / len(pages))

        st.session_state.single_result = {
            "photos": all_photos,
            "signatures": all_signatures,
            "photo_previews": photo_previews,
            "signature_previews": signature_previews,
        }

        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.subheader(f"📷 Photos ({len(all_photos)})")
            if photo_previews:
                st.image(photo_previews[0], caption="Extracted photo — white background", width=220)
                st.download_button("⬇ Download photo ZIP", base.zip_outputs(all_photos), "photos.zip", "application/zip", use_container_width=True)
            else:
                st.warning("No student photo region was detected.")
        with col2:
            st.subheader(f"✍ Signatures ({len(all_signatures)})")
            if signature_previews:
                st.image(signature_previews[0], caption="Extracted signature — white background", width=300)
                st.download_button("⬇ Download signature ZIP", base.zip_outputs(all_signatures), "signatures.zip", "application/zip", use_container_width=True)
            else:
                st.warning("No student signature region was detected.")

        if want_ocr and datalab_key:
            with st.spinner("Sending the uploaded file to Chandra OCR…"):
                try:
                    result = _ocr(uploaded.name, raw, prepared_for_ocr, datalab_key)
                    markdown = result.get("markdown") or ""
                    st.subheader("📄 OCR result")
                    if markdown:
                        st.markdown(markdown)
                        st.download_button("⬇ Download OCR Markdown", markdown, f"{Path(uploaded.name).stem}_ocr.md", "text/markdown")
                    else:
                        st.warning("Chandra returned no markdown text.")
                except Exception as exc:
                    st.error(f"OCR failed: {exc}")

    result = st.session_state.get("single_result")
    if result and (result.get("photos") or result.get("signatures")):
        st.divider()
        if st.checkbox("☁ Upload extracted Photo + Signature to Google Drive"):
            if st.button("UPLOAD EXTRACTED ASSETS TO DRIVE", type="secondary"):
                photo_bytes = result["photos"][0][1] if result.get("photos") else None
                signature_bytes = result["signatures"][0][1] if result.get("signatures") else None
                _drive_uploads(photo_bytes, signature_bytes, Path(uploaded.name).stem)

    st.caption("Original upload is never modified. Extraction creates new output assets only.")


if __name__ == "__main__":
    main()
