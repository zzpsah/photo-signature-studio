# Photo & Signature Studio

A **local/offline Windows desktop utility** for converting photos, signatures, scanned documents, screenshots, and PDF pages into portal-ready image files with exact pixel dimensions, white backgrounds, and configurable file-size limits.

> **Privacy:** Processing is designed to happen locally on the computer. The application does not upload identity documents, photographs, or signatures to a cloud service.

## 1. What the application does

The current MVP handles photo/signature preparation. The architecture is being extended toward a record-based document processing system:

```text
PDF / Image / Clipboard / Screenshot
                  |
                  v
             Input Inbox
                  |
          +-------+--------+
          |                |
          v                v
       Document          Photo / Signature
          |                |
          v                v
    Future OCR          Image Processing
    + Chandra OCR            |
          |                  |
          +--------+---------+
                   v
              Record / ID
                   |
        +----------+----------+
        |          |          |
      Data       Assets     Files
        |          |          |
        +----------+----------+
                   |
             Future Web
              Automation
```

### Supported input

- Clipboard images using **Ctrl+V**
- Windows Snipping Tool / Print Screen screenshots copied to the clipboard
- Images copied from browsers, PDF viewers, scanners, or image editors
- Clipboard file paths where supported by Windows
- JPG / JPEG
- PNG
- WebP
- BMP
- TIFF
- PDF
- Drag-and-drop is planned for a future release

### Photo processing

- Face detection using OpenCV Haar cascade
- Conservative portrait crop around the detected face
- White background canvas
- Exact output width and height in pixels
- Optional brightness/contrast/sharpness enhancement
- JPEG compression to meet a maximum KB target
- PNG output option

### Signature processing

- Detects dark ink on scanned paper
- Reduces light paper/background areas
- Crops unnecessary whitespace
- Places the result on a white background
- Exact output width and height
- JPEG/PNG output

### PDF processing

- Opens PDF files locally
- Renders PDF pages for processing
- Supports selecting a page from a multi-page PDF

## 2. Clipboard screenshot workflow

A screenshot copied to the Windows clipboard is treated as an image input. The current application can receive it through **Ctrl+V** without requiring the screenshot to be saved first.

```text
Snipping Tool / Print Screen / browser / PDF viewer
                         |
                    Copy screenshot
                         |
                       Ctrl+V
                         |
                  Photo & Signature Studio
                         |
              Process / OCR / Extract later
```

This is deliberately part of the input model because some workflows provide information only through a visible screen rather than a directly downloadable file.

## 3. Record-based data and file management

Future document/OCR features will use a stable **Record ID** instead of relying on filenames to determine relationships.

Example:

```text
APP-2026-000125/
├── source/
│   ├── application.pdf
│   └── screenshot.png
├── ocr/
│   ├── raw_text.txt
│   └── extracted.json
├── identity/
│   ├── photo.jpg
│   └── signature.jpg
├── processed/
│   ├── photo_200x230.jpg
│   └── signature_140x60.jpg
└── documents/
```

The record database will maintain relationships such as:

```text
Record
  |
  +-- Source document
  |      +-- Page
  |      +-- OCR result
  |      +-- Photo region -> photo asset
  |      +-- Signature region -> signature asset
  |
  +-- Extracted person/data fields
  |
  +-- Processed photo
  +-- Processed signature
  +-- Generated documents
```

This prevents accidental mixing when files have generic names such as `scan.pdf`, `photo.jpg`, or `signature.jpg`.

## 4. Local data architecture

A local SQLite database is being introduced as the metadata/relationship layer. Binary documents and images remain in local record folders.

Current foundation modules:

```text
core/
├── __init__.py
├── database.py       SQLite schema and record metadata
└── records.py        Record-linked local folder layout

oCR/
├── __init__.py
└── interface.py      Provider-neutral OCR interface

automation/
└── __init__.py       Future browser/web automation boundary
```

The database schema provides foundations for:

- Records
- Source documents
- OCR results
- Extracted assets
- Photo/signature relationships
- Source page and region references

The database foundation is present now; the full record-management UI and automatic linking workflow are planned enhancements.

## 5. OCR and Chandra OCR roadmap

The intended OCR architecture is provider-neutral:

```text
                 OCR Manager
                     |
          +----------+----------+
          |                     |
     Chandra OCR          Future OCR engine
          |                     |
          +----------+----------+
                     |
              Normalized OCR
                     |
             Structured data
                     |
                Record ID
```

**Chandra OCR is the planned primary OCR/document-understanding integration.** It will be placed behind the `OCREngine` interface so the desktop UI and record-management system do not depend directly on one OCR provider.

Potential capabilities include:

- OCR text extraction
- Structured field extraction
- Document/page classification
- Detection of form fields
- Detection of photo and signature regions
- Linking extracted photo/signature assets back to their source document and page
- OCR-assisted extraction of portal requirements where technically feasible
- Confidence/verification information so uncertain OCR is not silently treated as fact

> **Chandra OCR is not yet implemented in the current MVP.** The current code contains only the integration boundary/foundation.

## 6. Future web automation architecture

The application is intentionally being structured so future web automation can consume the same normalized records instead of reading desktop UI controls directly.

```text
                    Record / Data
                         |
                 Automation Adapter
                         |
              +----------+----------+
              |                     |
        Portal Adapter A      Portal Adapter B
              |                     |
              +----------+----------+
                         |
                  Browser Automation
                         |
              Fill -> Upload -> Review
                         |
                  User confirmation
                         |
                      Submit
```

Portal-specific mappings can eventually look like:

```text
Portal field          Record field
-----------------------------------
Candidate Name    <-  person.name
Father Name       <-  person.father_name
DOB               <-  person.date_of_birth
Photo             <-  linked photo asset
Signature         <-  linked signature asset
```

The preferred safety model is **Prepare → Fill → Review → User Confirmation → Submit**, rather than blind automatic submission.

Web automation is **not implemented in the current MVP**. The `automation/` package marks the architectural boundary for future development.

## 7. Important accuracy note

The application is intended to make image preparation fast, but **portal requirements must always be checked against the destination website/form**.

Do not assume that a preset is an official government specification. Pixel dimensions, KB limits, aspect ratios, file formats, and background rules can change.

Before submitting an important application, visually verify:

- Face is correctly framed
- Entire head is visible where required
- Photo is not stretched
- Background is actually white
- Signature is legible
- Pixel dimensions are correct
- File size is within the portal limit
- File format is accepted
- OCR-extracted data is correct

## 8. Repository file structure

```text
photo-signature-studio/
│
├── app.py
│   └── Main desktop application.
│
├── core/
│   ├── __init__.py
│   ├── database.py
│   │   └── Local SQLite schema for records, documents, OCR and assets.
│   └── records.py
│       └── Record-linked local file/folder management.
│
├── ocr/
│   ├── __init__.py
│   └── interface.py
│       └── Provider-neutral OCR interface; Chandra OCR will plug in here.
│
├── automation/
│   └── __init__.py
│       └── Boundary for future browser/web portal automation.
│
├── requirements.txt
│   └── Python packages required to run/build the application.
│
├── build_windows.bat
│   └── Local Windows build script. Creates the standalone EXE.
│
├── README.md
│   └── Project documentation, architecture and setup instructions.
│
├── .gitignore
│
└── .github/
    └── workflows/
        └── windows-build.yml
            └── GitHub Actions Windows build and artifact upload.
```

## 9. Requirements

### For running from source

- Windows 10/11 recommended
- Python 3.11 or 3.12 recommended
- Internet is required only to install Python packages initially
- After dependencies are installed, image processing can run offline

### Python dependencies

- **Pillow** — image loading, manipulation, clipboard support and output
- **OpenCV** — face/ink detection and image processing
- **NumPy** — numerical image operations
- **PyMuPDF** — local PDF rendering
- **PyInstaller** — standalone Windows executable creation

Exact package versions are maintained in `requirements.txt`.

## 10. Run from source on Windows

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

## 11. Build the standalone Windows EXE

Developer build:

```bat
build_windows.bat
```

Output:

```text
dist\PhotoSignatureStudio.exe
```

> The `.bat` file is a build tool, not the application. End users should run `PhotoSignatureStudio.exe`.

## 12. GitHub Actions Windows build and downloadable EXE

The workflow in `.github/workflows/windows-build.yml` installs Python 3.12, installs dependencies, runs PyInstaller, and uploads the executable as an artifact.

Artifact:

```text
PhotoSignatureStudio-Windows
└── PhotoSignatureStudio.exe
```

A push to `main` triggers the build. It can also be started manually from the GitHub Actions tab.

The EXE is distributed as a build artifact rather than committed directly to the source repository.

## 13. Basic usage

### Paste a photo or screenshot

1. Copy an image, screenshot, or supported clipboard content.
2. Open Photo & Signature Studio.
3. Press **Ctrl+V**.
4. Select Photo or Signature mode.
5. Choose a preset or enter Custom dimensions.
6. Set the maximum KB value if required.
7. Process and save.

### Open an image

1. Open a JPG, PNG, WebP, BMP or TIFF.
2. Select Photo or Signature mode.
3. Configure dimensions and KB.
4. Process and save.

### Process a PDF

1. Open the PDF.
2. Select the required page.
3. Select Photo or Signature mode.
4. Process and export.

## 14. Output-size optimization

When a maximum KB value is specified, the application attempts to reduce JPEG quality until the result is at or below the requested limit.

PNG is not suitable for every KB-constrained photograph because PNG is lossless and may produce a larger file than JPEG.

## 15. Privacy and security

Normal processing is local and does not require an application server.

Future OCR and automation modules should preserve the same privacy-first approach wherever technically practical. Sensitive documents should not be placed in public GitHub issues, commits, screenshots, or test fixtures.

## 16. Troubleshooting

### `.bat` build appears to hang

Run it from **Command Prompt** so installation/build output remains visible. The first build may take time because OpenCV, NumPy, PyMuPDF and PyInstaller are large dependencies. If it remains stuck, capture the last displayed command/output.

### EXE is missing

Check:

```text
dist\PhotoSignatureStudio.exe
```

### OpenCV cannot find the face

Detection depends on image quality, lighting, angle and face size. Verify the result manually.

### Signature has unwanted background

Use a clean, high-resolution scan with strong ink/paper contrast and inspect the result before submission.

## 17. Project status and roadmap

**Current:** Functional offline MVP / foundation

### Implemented now

- Windows desktop GUI
- Clipboard image and screenshot paste with Ctrl+V
- Clipboard file-path support where available
- JPG/JPEG/PNG/WebP/BMP/TIFF input
- Local PDF page rendering
- Photo processing with OpenCV face detection
- Signature cleanup
- Exact pixel dimensions
- JPEG KB-target optimization
- PNG output
- Preview and export
- Standalone Windows EXE build
- GitHub Actions Windows build artifact
- Initial SQLite/record-management architecture
- Provider-neutral OCR interface
- Future automation boundary

### Next development phases

**Phase 1 — Document intelligence**
- Chandra OCR integration
- Structured data extraction
- Record-management UI
- Automatic document/page classification
- Photo/signature region detection
- Source-to-asset linking

**Phase 2 — Productivity**
- Search and filtering
- Batch processing
- Portal presets
- Application kits
- Export/backup packages
- Hindi/English interface
- Duplicate detection

**Phase 3 — Advanced image/document processing**
- AI portrait segmentation/background removal
- Better passport composition rules
- Manual crop editor
- Large-file memory controls
- Background processing, progress and cancellation

**Phase 4 — Web automation**
- Browser automation framework
- Portal-specific adapters
- Field mapping from records to portal forms
- Photo/signature/document uploads
- Pre-submission validation
- Human review/confirmation
- Automation logs

### Not yet implemented

- Chandra OCR engine integration
- Full record-management UI
- Automatic data extraction
- Automatic photo/signature detection from documents
- Browser/web automation
- AI background removal/segmentation
- Drag-and-drop
- Batch processing
- Installer package

## License

Add the project's chosen license before public redistribution. Until a license is added, GitHub users should not assume permission to redistribute or commercially reuse the source.
