# Photo & Signature Studio — Environment Knowledge Base

This document is the operational knowledge base for the **Photo & Signature Studio** environment. It records verified architecture, configuration, troubleshooting findings, deployment notes, and recovery steps so future work can reuse known solutions instead of repeating investigation.

> **Scope:** This knowledge base describes the current project environment. Secrets, API keys, passwords, OTPs, CAPTCHA values, service-account private keys, and private student records must never be committed here.

## 1. Current system architecture

```text
                         STUDENT DOCUMENT WORKFLOW

 Hardcopy / Scan / Photo / PDF
              |
              v
      Single-file Web Upload
              |
       +------+------+
       |             |
       v             v
  Gemini Vision   Chandra OCR
       |             |
       v             v
 Photo region    OCR / layout / text
       |
       v
 OpenCV + Pillow
       |
   +---+---+
   |       |
 Photo   Signature
   |       |
   +---+---+
       |
       v
 Portal-ready assets
       |
       +--------------------+
       |                    |
       v                    v
 Google Drive        Supabase reference
 upload              matching / verification
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

### Feature priority

1. **Photo processing** — main feature
2. **Signature processing** — main feature
3. **OCR / student-form processing** — main feature
4. Supabase reference matching — supporting automation
5. BSEB portal automation — supporting automation
6. Google Drive upload — supporting storage workflow

The original hardcopy/form remains the source of current information. Reference data is used for comparison and verification; discrepancies must not be silently overwritten.

## 2. Current applications and entry points

### Windows desktop

- `app.py` — existing Tkinter Photo & Signature Studio
- `main.py` — desktop launcher for Photo, Signature and registration assistance
- `build_windows.bat` — Windows packaging
- `.github/workflows/windows-build.yml` — GitHub Actions Windows build

### Online / Streamlit

- `web_single_app.py` — current single-file student workflow
- `web/app.py` — Streamlit Community Cloud entrypoint
- `web_app.py` — shared web processing/OCR utilities
- `web/requirements.txt` — web dependencies

Current online application:

`https://photo-signature-studio-gwwj5igdeszojvajhd44sz.streamlit.app/`

## 3. Current single-file workflow

The current web workflow accepts **one complete student form/photo/PDF**. The intended user flow is:

```text
Upload ONE file
      |
      v
Read PDF pages / image
      |
      +----> Gemini detects actual student photo
      |             |
      |             v
      |       Photo processing
      |
      +----> Gemini detects actual handwritten signature
      |             |
      |             v
      |       Signature processing
      |
      +----> Chandra OCR reads complete document
                    |
                    v
             Human review / download
                    |
          +---------+---------+
          |                   |
          v                   v
     Google Drive       Future reference match
                              |
                              v
                       BSEB automation
```

Current portal-ready web presets are **300×400 photo** and **300×100 signature**, with JPEG size targets applied by the web workflow. These are application presets, not universal portal specifications; the destination portal must always be checked.

## 4. Gemini Vision configuration

Gemini is optional but currently used for reliable form-region detection.

Configuration:

```text
GEMINI_API_KEY
```

Set it through the deployment secret/configuration mechanism, not source code.

Current helper:

`core/gemini_crop.py`

It requests a structured JSON response containing:

- `found`
- `label`
- `box_2d`
- `confidence`

The bounding box is normalized to `0..1000` in `[ymin, xmin, ymax, xmax]` order.

### Important detection rule

The prompt must explicitly distinguish the **actual student's photo/signature** from:

- school/government logos
- seals
- sample portraits
- ID-card graphics
- printed signature labels
- form lines
- stamps
- decorative images

If detection is too broad, tighten the target description before changing image-processing code.

## 5. Chandra OCR / Datalab

The web application uses Datalab's managed Chandra OCR as the primary document OCR integration.

Configuration:

```text
DATALAB_API_KEY
```

The key must be stored in deployment secrets/configuration and never committed.

Current workflow:

```text
Original PDF/image
       |
       v
Chandra OCR
       |
       +--> markdown/text
       +--> layout-aware document understanding
       |
       v
Human verification
```

If OCR fails:

1. Confirm `DATALAB_API_KEY` exists in the deployment secrets.
2. Confirm the uploaded file is readable.
3. Confirm the provider response/error in the app output.
4. Do not replace the original document with a failed/preprocessed copy.
5. Retry after configuration/provider correction.

## 6. Google Drive upload

Current helper:

`core/google_drive.py`

Configuration includes:

```text
GOOGLE_DRIVE_FOLDER_ID
GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON
```

The folder ID is not a secret. Service-account credentials are secret.

The helper supports Shared Drive-compatible upload parameters.

### Drive troubleshooting

**Problem: `GOOGLE_DRIVE_FOLDER_ID` missing**

- Add the folder ID to Streamlit Secrets.
- Keep the TOML assignment on one line.
- Example format:

```toml
GOOGLE_DRIVE_FOLDER_ID = "YOUR_FOLDER_ID"
```

**Problem: service-account upload fails**

Check:

1. Service-account JSON is configured securely.
2. The target folder/Shared Drive is accessible to the service account.
3. The folder ID points to the intended destination.
4. Do not put the JSON private key in GitHub source files.

### Earlier environment lesson

Service accounts do not automatically receive normal personal My Drive storage quota. A Shared Drive or an authenticated human OAuth workflow is the robust destination model.

## 7. Streamlit Secrets troubleshooting

A previously encountered configuration problem was invalid TOML caused by splitting assignments across lines.

### Correct

```toml
DATALAB_API_KEY = "YOUR_DATALAB_KEY"
GEMINI_API_KEY = "YOUR_GEMINI_KEY"
GOOGLE_DRIVE_FOLDER_ID = "YOUR_FOLDER_ID"
```

### Avoid

```toml
DATALAB_API_KEY =
"YOUR_DATALAB_KEY"
```

After changing secrets, restart/redeploy the Streamlit application when required by the platform.

### Security incident lesson

If an API key is ever pasted into a public chat, screenshot, issue, repository, or other exposed location, treat it as compromised: revoke/rotate it and replace the deployment secret. Never copy the exposed value into source code.

## 8. Windows OpenCV packaged EXE troubleshooting

### Known error

```text
OpenCV(...)
error: (-215:Assertion failed) !empty() in function 'cv::CascadeClassifier::detectMultiScale'
```

### Cause

The packaged Windows executable did not include OpenCV's Haar-cascade XML data. The Python source could work while the PyInstaller EXE failed because the runtime data file was missing.

### Recorded fix

Commit:

`423b5b6ccd8f939f1a57fc73b86b8c3d2c36aa12`

Message:

`Fix packaged OpenCV face detection data`

### Future rule

When a Python application works from source but a packaged OpenCV EXE fails around `CascadeClassifier`, inspect packaged data files before changing detection logic.

## 9. Photo-processing troubleshooting

### Photo is not detected

Order of checks:

1. Confirm the source contains a visible student portrait.
2. Confirm Gemini is configured if the source is a full form.
3. Check Gemini detection details in the app.
4. If Gemini is unavailable, local face detection can be used as a fallback for direct/clear portraits.
5. Do not use a generic image crop as the final student photo unless the user verifies it.

### Photo contains form borders/background

Use the AI region detector first. Tighten the Gemini target prompt if the wrong image is selected. Then use deterministic processing for sizing, background and enhancement.

### Photo background is not clean

The current processing uses deterministic image processing after region detection. Do not assume a white canvas is the same as true subject segmentation. For portal use, visually verify the result.

## 10. Signature-processing troubleshooting

### Signature is not detected

1. Confirm the form page actually contains the student's handwritten signature.
2. Use Gemini detection for full-form documents.
3. Ensure the prompt excludes printed signature lines/labels/stamps.
4. Check the AI detection details.
5. Review the cleaned output before portal submission.

### Signature contains too much whitespace

The deterministic signature processor crops around detected ink and creates a white-background output. If the source contains heavy printed material near the signature, improve region detection rather than blindly increasing crop aggressiveness.

## 11. PDF troubleshooting

The web workflow renders PDF pages before AI region processing.

If a PDF does not process:

1. Confirm it is a valid PDF.
2. Check whether the PDF contains image pages or unusual encryption.
3. Try a single-page export for diagnosis.
4. Keep the original PDF unchanged.
5. If the PDF renders correctly but detection fails, troubleshoot Gemini/page selection rather than PDF parsing.

For multi-page student forms, review which page contains the actual photo and signature. The current workflow can process all rendered pages, but the useful output should still be verified as belonging to the same student record.

## 12. Supabase reference matching

Supabase is a **supporting verification feature**, not the primary product.

Reference table:

```text
public.Class_X_reg_2026_2027
```

It represents the target Class X registration batch/reference data.

The intended comparison is:

```text
Hardcopy / OCR current data
          |
          v
     Field-by-field
       comparison
          ^
          |
Supabase reference data
```

Important rule:

> Never silently overwrite hardcopy/current information with reference data when fields disagree.

Relevant matching fields include name, father name, mother name, DOB, school/application identifiers and Aadhaar where legitimately available.

RLS and Data API permissions must be verified before assuming the desktop/web client can read the table.

## 13. BSEB workflow troubleshooting

BSEB portal automation is a supporting workflow.

Preferred sequence:

```text
OCR / verified data
       |
       v
Reference comparison
       |
       v
Photo + signature ready
       |
       v
BSEB portal preparation
       |
       v
User login / CAPTCHA / OTP as required
       |
       v
Field filling + uploads
       |
       v
Review screen
       |
       v
USER CONFIRMS SUBMISSION
```

Do not bypass CAPTCHA, OTP, authentication or other portal security controls.

Portal field names and requirements can change. Verify the live destination portal before implementing or relying on mappings.

## 14. Repository architecture lessons

The project intentionally separates responsibilities:

```text
UI
 |
 +--> Photo/Signature processing
 +--> OCR integration
 +--> Record/storage layer
 +--> Reference matching
 +--> External upload helpers
 +--> Future portal automation
```

Avoid putting provider-specific API calls throughout the UI. Keep external services behind focused helpers so they can be tested/replaced independently.

## 15. Deployment boundaries

### Windows build

The GitHub Actions workflow is configured to limit Windows builds to Windows-app changes where possible. Web-only changes should not require a Windows build.

### Streamlit web deployment

`web/app.py` is the Community Cloud entrypoint and currently delegates to `web_single_app.py`.

### Production safety

Before changing production:

1. Make the change in staging/development.
2. Test the affected workflow.
3. Review the diff.
4. Confirm no secrets or private data were introduced.
5. Promote only after explicit approval.

## 16. Safe troubleshooting checklist

When something fails, record:

- Date/time
- Environment: Windows / Streamlit / GitHub Actions
- File type: image / PDF
- Exact error text
- Input characteristics
- API/provider involved
- Whether the issue occurs from source and/or packaged build
- Last known working commit
- Fix applied
- Verification result

Use this format for future entries:

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

## 17. Known important commits

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

## 18. Change-control rule

This knowledge base should be updated whenever a troubleshooting session discovers a **verified environment-specific fact or reusable fix**.

Do not record guesses as facts. Mark unresolved items as unresolved until verified.

The knowledge base itself must never contain secrets or confidential student information.
