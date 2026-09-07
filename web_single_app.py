"""Single-file AI-assisted workflow for student forms, photo, signature and OCR."""
from __future__ import annotations

import io
import json
from pathlib import Path

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
        return [(i + 1, page) for i, page in enumerate(base.pdf_to_images(raw))]
    return [(1, ImageOps.exif_transpose(Image.open(io.BytesIO(raw)).convert("RGB")))]


def _find_region(image: Image.Image, target: str, api_key: str) -> dict:
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
                "the actual student's passport photograph printed or pasted on this form. Return ONLY the photograph rectangle. Ignore government logos, seals, sample portraits, ID graphics, stamps, and decorative images. The box must include the complete student portrait but as little surrounding form as possible.",
                gemini_key,
            )
            if photo_detection.get("found"):
                photo = crop_box(image, photo_detection["box_2d"], padding=0.008)
        except GeminiCropError as exc:
            st.warning(f"Photo detection on page {page_no}: {exc}")

    if gemini_key and want_signature:
        try:
            signature_detection = _find_region(
                image,
                "the actual student's handwritten signature specimen on this form. Return ONLY the rectangle containing the handwritten ink. Ignore the signature label, printed lines, form borders, stamps, logos, typed names and other marks.",
                gemini_key,
            )
            if signature_detection.get("found"):
                signature = crop_box(image, signature_detection["box_2d"], padding=0.006)
        except GeminiCropError as exc:
            st.warning(f"Signature detection on page {page_no}: {exc}")

    if want_photo and photo is None:
        try:
            box = base.detect_face_box(image)
            if box:
                photo = image.crop(box)
        except Exception:
            pass

    photo_output = process_photo_asset(photo, (300, 400)) if photo is not None else None
    signature_output = process_signature_asset(signature, (300, 100)) if signature is not None else None
    prefix = Path(stem).stem
    if page_no > 1 or stem.lower().endswith(".pdf"):
        prefix = f"{prefix}_page_{page_no}"
    return photo_output, signature_output, photo_detection, signature_detection, prefix


def _drive_uploads(photo_items: list[tuple[str, bytes]], signature_items: list[tuple[str, bytes]]):
    folder_id = get_folder_id(_secrets())
    if not folder_id:
        st.error("GOOGLE_DRIVE_FOLDER_ID is missing in Streamlit Secrets.")
        return
    items = [(name, payload) for name, payload in [*photo_items, *signature_items]]
    if not items:
        st.warning("There are no extracted assets to upload.")
        return
    progress = st.progress(0)
    for index, (filename, payload) in enumerate(items):
        try:
            upload_bytes(filename, payload, "image/jpeg", folder_id=folder_id, secrets=_secrets())
        except GoogleDriveError as exc:
            st.error(str(exc))
            return
        progress.progress((index + 1) / len(items))
    st.success(f"Uploaded {len(items)} asset(s) to Google Drive.")


def _run_ocr(file_name: str, raw: bytes, pages: list[tuple[int, Image.Image]], api_key: str) -> dict:
    """Use Datalab's managed Chandra OCR as the primary document OCR engine."""
    if file_name.lower().endswith(".pdf"):
        return base.run_chandra_ocr(file_name, raw, api_key)
    image = pages[0][1]
    bio = io.BytesIO()
    image.save(bio, "JPEG", quality=94, optimize=True)
    return base.run_chandra_ocr(f"{Path(file_name).stem}.jpg", bio.getvalue(), api_key)


def _ocr_text(result: dict) -> str:
    value = result.get("markdown") or result.get("text") or ""
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)


def _render_outputs(result: dict):
    photos = result.get("photos", [])
    signatures = result.get("signatures", [])
    photo_previews = result.get("photo_previews", [])
    signature_previews = result.get("signature_previews", [])

    st.divider()
    st.subheader("✅ Portal-ready outputs")
    left, right = st.columns(2)
    with left:
        st.markdown("### 📷 Student Photo")
        if photo_previews:
            st.image(photo_previews[0], width=230, caption="AI-cropped • enhanced • white background • 300×400")
            st.download_button("⬇ Download Photo", photos[0][1], photos[0][0], "image/jpeg", use_container_width=True, key="download_single_photo")
            if len(photos) > 1:
                st.download_button("⬇ Download all photos (ZIP)", base.zip_outputs(photos), "photos.zip", "application/zip", use_container_width=True)
        else:
            st.warning("No student photo was confidently detected.")
    with right:
        st.markdown("### ✍ Student Signature")
        if signature_previews:
            st.image(signature_previews[0], width=300, caption="AI-cropped • cleaned • white background • 300×100")
            st.download_button("⬇ Download Signature", signatures[0][1], signatures[0][0], "image/jpeg", use_container_width=True, key="download_single_signature")
            if len(signatures) > 1:
                st.download_button("⬇ Download all signatures (ZIP)", base.zip_outputs(signatures), "signatures.zip", "application/zip", use_container_width=True)
        else:
            st.warning("No student signature was confidently detected.")


def main():
    st.set_page_config(page_title="BSEB Photo & Signature AI", page_icon="📷", layout="wide")
    st.title("📷 BSEB Photo & Signature AI")
    st.caption("One student form in → AI finds the student's photo and signature → cleans and enhances them → Chandra OCR reads the form.")

    gemini_key = get_gemini_key(_secrets())
    datalab_key = base.get_datalab_key()
    uploaded = st.file_uploader(
        "Upload ONE student form, scan or PDF",
        type=["pdf", "jpg", "jpeg", "png", "webp", "bmp", "tif", "tiff"],
        accept_multiple_files=False,
        help="Use the original scanned/photographed BSEB form. Do not crop the form first.",
    )

    if not uploaded:
        st.info("Upload one complete student form. No separate photo, signature or OCR upload is required.")
        c1, c2, c3 = st.columns(3)
        c1.markdown("**1. AI detection**\n\nGemini locates the actual student photo and handwritten signature.")
        c2.markdown("**2. Image processing**\n\nOpenCV/Pillow crops, cleans, enhances and makes the photo background white.")
        c3.markdown("**3. Chandra OCR**\n\nDatalab Chandra reads the complete form and preserves document layout.")
        return

    raw = uploaded.getvalue()
    pages = _pages_from_upload(uploaded.name, raw)
    st.success(f"Loaded **{uploaded.name}** • {len(pages)} page(s)")

    with st.expander("Advanced processing", expanded=False):
        want_photo = st.checkbox("Extract student photo", True, key="single_want_photo")
        want_signature = st.checkbox("Extract student signature", True, key="single_want_signature")
        want_ocr = st.checkbox("Run Chandra OCR", True, key="single_want_ocr")
        use_ai = st.checkbox("Use Gemini AI detection", True, key="single_use_gemini")
        if not gemini_key and use_ai:
            st.warning("Gemini is not configured; photo extraction can fall back to local face detection, but form-region detection will be limited.")
        if want_ocr and not datalab_key:
            st.error("DATALAB_API_KEY is not configured, so Chandra OCR cannot run yet.")

    if st.button("🚀 PROCESS STUDENT FILE", type="primary", use_container_width=True):
        all_photos: list[tuple[str, bytes]] = []
        all_signatures: list[tuple[str, bytes]] = []
        photo_previews: list[Image.Image] = []
        signature_previews: list[Image.Image] = []
        detections = []
        progress = st.progress(0)

        for index, (page_no, image) in enumerate(pages):
            photo, signature, photo_detection, signature_detection, prefix = _extract_page(image, page_no, uploaded.name, gemini_key if use_ai else "", want_photo, want_signature)
            detections.append({"page": page_no, "photo": photo_detection, "signature": signature_detection})
            if photo is not None:
                all_photos.append((f"{prefix}_photo.jpg", base.encode_jpeg_under_kb(photo, 100)))
                photo_previews.append(photo)
            if signature is not None:
                all_signatures.append((f"{prefix}_signature.jpg", base.encode_jpeg_under_kb(signature, 50)))
                signature_previews.append(signature)
            progress.progress((index + 1) / len(pages))

        ocr_result = None
        if want_ocr and datalab_key:
            with st.spinner("Reading the complete form with Datalab Chandra OCR…"):
                try:
                    ocr_result = _run_ocr(uploaded.name, raw, pages, datalab_key)
                except Exception as exc:
                    st.error(f"Chandra OCR failed: {exc}")

        st.session_state.single_result = {
            "photos": all_photos,
            "signatures": all_signatures,
            "photo_previews": photo_previews,
            "signature_previews": signature_previews,
            "detections": detections,
            "ocr": ocr_result,
            "source_name": uploaded.name,
        }

    result = st.session_state.get("single_result")
    if not result:
        return

    _render_outputs(result)

    detections = result.get("detections", [])
    if detections:
        with st.expander("🔎 AI detection details", expanded=False):
            for item in detections:
                st.write(f"Page {item['page']}")
                st.json(item)

    ocr_result = result.get("ocr")
    if ocr_result:
        st.divider()
        st.subheader("📄 Chandra OCR — complete form")
        markdown = _ocr_text(ocr_result)
        if markdown:
            st.markdown(markdown)
            st.download_button("⬇ Download OCR result", markdown, f"{Path(result['source_name']).stem}_chandra.md", "text/markdown", use_container_width=False)
        else:
            st.warning("Chandra completed but returned no readable text.")

    if result.get("photos") or result.get("signatures"):
        st.divider()
        st.subheader("☁ Optional Google Drive upload")
        if st.button("UPLOAD ALL EXTRACTED ASSETS TO DRIVE", type="secondary", use_container_width=True):
            _drive_uploads(result.get("photos", []), result.get("signatures", []))

    st.success("Original form remains unchanged. The downloaded photo and signature are newly generated portal-ready assets.")


if __name__ == "__main__":
    main()
