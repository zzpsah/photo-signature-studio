# Photo & Signature Studio

A **photo, signature, and student-document processing system** for preparing portal-ready student assets, extracting information from hardcopy forms, and supporting registration workflows.

> **Product priority:** Photo, Signature, and OCR are the main features. Supabase reference matching, Google Drive upload, and BSEB portal automation are supporting/automation features around them.

> **Privacy:** Local image processing is designed to keep source documents, photos, signatures, and extracted data on the user's computer unless an explicit web/external workflow is used.

## 1. Product direction

The project has evolved from a photo/signature utility into a **record-based student document preparation and verification system**.

```text
Hardcopy / Scan / Photo / PDF
            |
            v
     Single-file Upload
            |
      +-----+-----+
      |           |
      v           v
   Gemini      Chandra OCR
   Vision          |
      |            v
      v        OCR / fields
 Photo region       |
      |             |
      v             |
Photo processing   |
      |             |
      +------+------+ 
             |
      Signature processing
             |
             v
     Portal-ready assets
             |
       +-----+------+
       |            |
       v            v
 Google Drive   Supabase reference
                   matching
                     |
                     v
              Verified data/assets
                     |
                     v
             BSEB preparation
                     |
                     v
                Human review
                     |
                     v
                  Submit
```

### Source-of-truth rule

- **Hardcopy/form = current student-provided information.**
- **Supabase `public.Class_X_reg_2026_2027` = reference/target batch data.**
- Reference data is used for field-by-field verification; disagreements must never be silently overwritten.
- **BSEB portal = actual destination.** Portal requirements must be verified against the live destination before submission.

Every managed desktop record has a stable **Record ID** connecting source documents, OCR, photo, signature, supporting documents, and future portal information.

## 2. Current online workflow

The current Streamlit workflow is intentionally **single-file**: upload one complete student form, scan, image, or PDF rather than separately uploading photo, signature, and OCR inputs.

Current web entry point:

`web/app.py` → `web_single_app.py`

Current online application:

`https://photo-signature-studio-gwwj5igdeszojvajhd44sz.streamlit.app/`

Workflow:

```text
ONE student form/photo/PDF
          |
          +----> Gemini finds actual student photo
          |             |
          |             v
          |       OpenCV/Pillow processing
          |
          +----> Gemini finds actual handwritten signature
          |             |
          |             v
          |       OpenCV/Pillow processing
          |
          +----> Datalab Chandra OCR
                        |
                        v
                  Human review
                        |
             +----------+----------+
             |                     |
             v                     v
       Download assets       Optional Drive upload
             |
             v
      Future verification / BSEB workflow
```

Current web presets are **300×400 photo** and **300×100 signature**, with JPEG size-target optimization. These are application presets, not universal portal specifications.

## 3. Current capabilities

### Input

- Clipboard images using **Ctrl+V** in the Windows application
- Windows Snipping Tool / Print Screen screenshots
- Images copied from browsers, PDF viewers, scanners, or editors
- Clipboard file paths where supported by Windows
- JPG / JPEG
- PNG
- WebP
- BMP
- TIFF
- PDF

### Photo

- Gemini-assisted student-photo region detection in the web workflow
- OpenCV face-detection fallback where appropriate
- Conservative/deterministic crop processing
- White-background processing
- Exact output dimensions
- Light enhancement
- JPEG KB-target optimization
- PNG output in the desktop workflow

### Signature

- Gemini-assisted handwritten-signature region detection
- Dark-ink detection and normalization
- Whitespace/ink cropping
- White background
- Exact output dimensions
- JPEG/PNG output in the desktop workflow

### OCR

- Datalab Chandra OCR is the current primary document OCR integration for the web workflow.
- The architecture keeps OCR provider logic separate from the UI.
- OCR results can be displayed/downloaded and are intended for human verification before downstream use.

### PDF

- Local PDF page rendering
- Multi-page processing
- Page-by-page photo/signature extraction
- Complete-PDF OCR through Chandra in the web workflow

### Google Drive

- Optional upload of generated photo/signature assets
- Shared Drive-compatible upload helper
- Destination controlled through deployment configuration

### Supabase reference matching

- REST client for the Class X registration reference batch
- Field-by-field hardcopy/OCR/reference comparison logic
- Matching is supporting functionality and does not replace human verification

## 4. Record-based local file management

The managed local workspace uses one directory per Record ID.

```text
data/
├── studio.db
└── records/
    └── APP-YYYYMMDD-XXXXXXXX/
        ├── source/
        │   ├── application.pdf
        │   └── screenshot.png
        ├── ocr/
        │   ├── raw_text.txt
        │   └── extracted.json
        ├── photo/
        │   └── photo_*.jpg
        ├── signature/
        │   └── signature_*.jpg
        ├── documents/
        ├── exports/
        └── portal_manifest.json
```

The Record ID, rather than a generic filename such as `photo.jpg`, is the relationship key connecting the student's source material and generated assets.

## 5. Repository architecture

```text
photo-signature-studio/
│
├── app.py                         # Windows Photo/Signature Studio
├── main.py                        # Desktop launcher
├── web_app.py                     # Shared web processing/OCR utilities
├── web_single_app.py              # Current single-file Streamlit workflow
├── web/
│   ├── app.py                     # Streamlit Cloud entrypoint
│   └── requirements.txt
│
├── core/
│   ├── asset_processing.py        # Deterministic photo/signature processing
│   ├── database.py                # SQLite metadata/relationships
│   ├── records.py                 # Record directory layout
│   ├── storage.py                 # Managed file storage
│   ├── record_service.py          # High-level record operations
│   ├── record_manifest.py         # Portal manifest
│   ├── student_matcher.py         # Hardcopy/reference comparison
│   ├── supabase_client.py         # Supabase REST reference access
│   ├── gemini_crop.py             # Gemini region detection
│   └── google_drive.py             # Google Drive upload helper
│
├── ocr/
│   └── interface.py               # Provider-neutral OCR boundary
│
├── automation/
│   └── __init__.py                # Future browser/web automation boundary
│
├── KNOWLEDGE_BASE.md              # Environment troubleshooting/runbook
├── requirements.txt
├── build_windows.bat
├── README.md
└── .github/workflows/windows-build.yml
```

## 6. OCR architecture

```text
                 OCR Manager / Web Workflow
                           |
                    Datalab Chandra OCR
                           |
                           v
                  OCR text + document layout
                           |
                           v
                  Structured/verified data
                           |
                           v
                         Record
```

Chandra is currently integrated into the online single-file workflow. The provider-neutral OCR boundary remains useful for future engines and desktop integration.

## 7. Gemini Vision architecture

Gemini is used for **region detection**, not as a replacement for deterministic image processing.

```text
Full student form
       |
       v
Gemini Vision
       |
       +--> actual student photo box
       |
       +--> actual handwritten signature box
       |
       v
OpenCV / Pillow deterministic processing
       |
       v
Portal-ready asset
```

Detection requests use structured JSON with normalized `[ymin, xmin, ymax, xmax]` coordinates. The prompts explicitly exclude logos, seals, sample portraits, printed signature lines, stamps, and decorative graphics.

## 8. Supabase reference workflow

Reference data is supporting data, not the source of the current hardcopy information.

```text
Hardcopy / OCR current values
             |
             v
      Field-by-field compare
             ^
             |
Supabase Class_X_reg_2026_2027
             |
             v
       Match / Close / Mismatch
             |
             v
        Human verification
```

The desktop/web client must not expose Supabase secret/service-role credentials. Access should use the appropriate public/publishable configuration with database grants and RLS controlling access.

## 9. BSEB workflow

The preferred workflow is:

```text
Prepare
  ↓
OCR / extract
  ↓
Compare with reference
  ↓
Verify student information
  ↓
Prepare photo + signature
  ↓
Fill portal
  ↓
Upload assets
  ↓
Review
  ↓
USER CONFIRMS SUBMISSION
```

Authentication, CAPTCHA, OTP, and other portal security controls must not be bypassed.

## 10. Important troubleshooting knowledge

### OpenCV EXE: `CascadeClassifier::detectMultiScale` assertion

Known error:

```text
error: (-215:Assertion failed) !empty() in function 'cv::CascadeClassifier::detectMultiScale'
```

Cause: OpenCV Haar-cascade XML data was missing from the packaged Windows executable even though the source installation worked.

Recorded fix:

`423b5b6ccd8f939f1a57fc73b86b8c3d2c36aa12` — **Fix packaged OpenCV face detection data**.

Rule: when source works but the packaged EXE fails inside OpenCV cascade loading, inspect PyInstaller data files before changing the detection algorithm.

### Streamlit Secrets / TOML

Keep each assignment on one line:

```toml
DATALAB_API_KEY = "YOUR_DATALAB_KEY"
GEMINI_API_KEY = "YOUR_GEMINI_KEY"
GOOGLE_DRIVE_FOLDER_ID = "YOUR_FOLDER_ID"
```

Never commit actual keys.

### Google Drive

The service account must have access to the destination folder/Shared Drive. `GOOGLE_DRIVE_FOLDER_ID` identifies the destination; the service-account JSON is secret configuration.

### Gemini detection

If the wrong image is detected, first tighten the region-detection prompt and inspect the AI detection details. Do not compensate with arbitrary cropping that could cut off the student's photo/signature.

### OCR failure

Check the Datalab key, input readability, provider response, and deployment configuration. Keep the original upload unchanged.

### PDF failure

Determine whether the failure is PDF rendering, page selection, AI detection, or OCR. Diagnose the specific layer instead of changing unrelated processing code.

A detailed, reusable runbook is maintained in **[KNOWLEDGE_BASE.md](KNOWLEDGE_BASE.md)**.

## 11. Windows build

Developer build:

```bat
build_windows.bat
```

Output:

```text
dist\PhotoSignatureStudio.exe
```

GitHub Actions produces the `PhotoSignatureStudio-Windows` artifact.

Web-only changes should not require a Windows build where the workflow path filters permit avoiding it.

## 12. Requirements

### Source / Windows

- Windows 10/11 recommended
- Python 3.11 or 3.12 recommended
- Python dependencies from `requirements.txt`

### Main dependencies

- **Pillow** — image/clipboard processing
- **OpenCV** — face/ink detection and image processing
- **NumPy** — numerical image operations
- **PyMuPDF** — PDF rendering
- **PyInstaller** — Windows packaging

### Web dependencies

The Streamlit web environment additionally uses requests, `opencv-python-headless`, Google API/auth libraries and the configured external OCR/AI integrations.

## 13. Run from source

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

## 14. Current project status

### Working / implemented

- Windows desktop Photo & Signature Studio
- Clipboard screenshot/image workflow
- Image and PDF input
- Photo processing
- Signature processing
- Exact output dimensions
- JPEG size optimization
- Standalone Windows build
- GitHub Actions Windows build
- Record-oriented SQLite/storage foundation
- Single-file online student workflow
- Gemini-assisted photo/signature region detection
- Datalab Chandra OCR web integration
- Google Drive upload helper
- Supabase Class X reference matching foundation
- Environment troubleshooting knowledge base

### Still evolving

- More reliable form-specific extraction across diverse BSEB layouts
- Full record-management UI
- Structured OCR field verification UI
- Batch processing
- More portal-specific presets
- Portal automation adapters
- Pre-submission validation and audit logs

## 15. Known important commits

| Commit | Purpose |
|---|---|
| `423b5b6ccd8f939f1a57fc73b86b8c3d2c36aa12` | Fix packaged OpenCV face detection data |
| `780a9306dabe9c1293edd9f89df93b2878a8f8` | Add hardcopy-to-reference student matching logic |
| `efbb6f9610221098205a556d11b270946a32e456` | Add Supabase REST client |
| `fdfa7a0c7dba68226cac97d44c799d32cc65afb7` | Add deterministic photo/signature asset processing |
| `f258c19e4f6ee6d518a24d12bf1dce94d7a26b7` | Add single-file AI-assisted student workflow |
| `380b7199cb7e7a11b635cac008fa79996514920` | Point Streamlit entrypoint to single-file workflow |
| `b58e58e8e6e38d48b9dc12d8daf6a4ce49cc5035` | Enable PDF input for photo/signature processing |
| `8d078b4c7aac9dd2ed635f7ec4a4219eccba1c53` | Add enhanced AI/PDF/Drive workflow wrapper |
| `de8eb306ed816e4c27eea9c5231fb42b208f5e6e` | Add Shared Drive-compatible upload support |
| `3e975583fb6345c99ec399f687823ede0ac6de4a` | Add environment knowledge base |

## 16. Security and change control

- Never commit API keys, passwords, OTPs, CAPTCHA values, service-account private keys, or confidential student data.
- If a secret is exposed, revoke/rotate it immediately.
- Do not use Supabase service-role/secret keys in public clients.
- Treat the hardcopy as the current-data source and reference databases as verification sources.
- Do not bypass BSEB authentication/CAPTCHA/OTP controls.
- Test changes in staging/development before production.
- Preserve the original uploaded document; generated assets are separate outputs.

## 17. Knowledge-base maintenance

Every verified environment-specific troubleshooting discovery should be added to **[KNOWLEDGE_BASE.md](KNOWLEDGE_BASE.md)** using this pattern:

```text
### YYYY-MM-DD — Short problem title

Environment:
- ...

Symptom:
- ...

Root cause:
- ...

Fix:
- ...

Verification:
- ...

Commit:
- ...

Future prevention:
- ...
```

Record verified facts, not guesses. Never store secrets or confidential student information in the knowledge base.

## License

Add the project's chosen license before public redistribution. Until a license is added, GitHub users should not assume permission to redistribute or commercially reuse the source.
