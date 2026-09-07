# Photo & Signature Studio

A **local/offline Windows desktop utility** for converting photos, signatures, scanned documents, screenshots, and PDF pages into portal-ready image files with exact pixel dimensions, white backgrounds, and configurable file-size limits.

> **Privacy:** Normal image processing is local. The application is designed so identity documents, photos, signatures, and extracted data remain on the user's computer unless the user explicitly uses a future external/web workflow.

## 1. Product direction

The project is evolving from a photo/signature utility into a **record-based document preparation system**:

```text
Screenshot / Clipboard / PDF / Image
                |
                v
           Input Inbox
                |
                v
            Record ID
                |
       +--------+--------+
       |        |        |
     Source    OCR     Assets
     Files     Data      |
       |        |    +---+---+
       |        |   Photo  Signature
       |        |      |      |
       +--------+------+------+
                |
         Portal-ready files
                |
       Future web automation
```

Every application/person/document set gets a stable **Record ID**. The Record ID, not a filename, is the relationship key connecting the original document, OCR data, extracted photo, extracted signature, processed assets, and future portal data.

## 2. Current capabilities

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

### Photo processing

- OpenCV Haar-cascade face detection
- Conservative portrait crop
- White background canvas
- Exact output width/height
- Optional light enhancement
- JPEG KB-target optimization
- PNG output

### Signature processing

- Dark-ink detection
- Background normalization
- Whitespace cropping
- White background
- Exact output dimensions
- JPEG/PNG output

### PDF processing

- Local PDF opening
- Local page rendering
- Multi-page selection

## 3. Clipboard screenshot workflow

A screenshot copied to the Windows clipboard can be pasted directly with **Ctrl+V**. It does not need to be saved first.

```text
Snipping Tool / Print Screen / Browser / PDF Viewer
                         |
                     Copy image
                         |
                       Ctrl+V
                         |
                Photo & Signature Studio
                         |
              Record / Process / OCR later
```

This input route is important for information that is visible on screen but not conveniently downloadable.

## 4. Record-based file management

The managed local workspace uses one directory per Record ID. Portal-ready photo and signature files are kept in dedicated directories so they can be selected directly for upload.

Example:

```text
data/
├── studio.db
└── records/
    └── APP-20260907-A1B2C3D4/
        ├── source/
        │   ├── application.pdf
        │   └── screenshot.png
        ├── ocr/
        │   ├── raw_text.txt
        │   └── extracted.json
        ├── photo/
        │   └── photo_200x230.jpg
        ├── signature/
        │   └── signature_140x60.jpg
        ├── documents/
        │   └── supporting_document.pdf
        ├── exports/
        └── portal_manifest.json
```

### Why this layout matters

The user can open the record folder and immediately find:

- **Photo** → ready to upload to a portal
- **Signature** → ready to upload to a portal
- **OCR data** → structured data available for form filling
- **Source files** → original evidence
- **Documents** → supporting files
- **Manifest** → machine-readable relationship information

The system does not depend on filenames such as `photo.jpg` or `signature.jpg` to decide which person they belong to. The Record ID provides that relationship.

## 5. Local database and storage layer

SQLite stores metadata and relationships; binary files stay in the record folders.

Current foundation modules:

```text
core/
├── database.py
│   └── Records, documents, OCR results and assets
├── records.py
│   └── Standard Record ID folder layout
├── storage.py
│   └── Managed source/photo/signature/document directories
└── record_service.py
    └── High-level creation, source-file, portal-asset and OCR storage

oCR/
└── interface.py
    └── Provider-neutral OCR interface

automation/
└── __init__.py
    └── Boundary for future browser/web automation
```

The service layer can store:

```text
Record
  ├── source document
  ├── OCR text
  ├── structured OCR JSON
  ├── photo asset
  ├── signature asset
  ├── supporting documents
  └── portal-ready outputs
```

## 6. OCR and Chandra OCR

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

**Chandra OCR is the planned primary OCR/document-understanding integration.** It will plug into the OCR interface rather than being embedded throughout the UI.

Potential capabilities:

- OCR text extraction
- Structured field extraction
- Document/page classification
- Form-field detection
- Photo-region detection
- Signature-region detection
- Extraction of photo/signature from scanned documents
- Linking extracted assets to source document/page/region
- OCR-assisted extraction of portal requirements
- Confidence/verification information

> **Chandra OCR is not yet implemented.** The repository currently contains the provider-neutral OCR boundary and storage architecture needed for the integration.

## 7. Future portal/web automation

The normalized Record should become the single source of truth for future web automation.

```text
Record
  |
  +-- Person data
  +-- OCR data
  +-- Photo file
  +-- Signature file
  +-- Supporting documents
           |
           v
   Portal Automation Adapter
           |
      Browser automation
           |
      Fill -> Upload
           |
         Review
           |
   User confirmation
           |
        Submit
```

Example future mapping:

```text
Portal field             Record source
---------------------------------------
Candidate Name       <-  person.name
Father Name          <-  person.father_name
Date of Birth        <-  person.date_of_birth
Photo upload         <-  photo/photo_*.jpg
Signature upload     <-  signature/signature_*.jpg
Supporting document  <-  documents/*
```

The preferred workflow is **Prepare → Fill → Review → User Confirmation → Submit**, rather than blind submission.

Web automation is not implemented yet.

## 8. Important accuracy note

Portal requirements must always be checked against the actual destination website/form. Presets are convenience configurations, not authoritative specifications.

Before submission, verify:

- Photo framing
- Head visibility where required
- White background where required
- Signature legibility
- Exact pixel dimensions
- File size
- File format
- OCR-extracted data
- Correct Record ID and linked files

## 9. Repository file structure

```text
photo-signature-studio/
│
├── app.py
├── core/
│   ├── __init__.py
│   ├── database.py
│   ├── records.py
│   ├── storage.py
│   └── record_service.py
├── ocr/
│   ├── __init__.py
│   └── interface.py
├── automation/
│   └── __init__.py
├── requirements.txt
├── build_windows.bat
├── README.md
├── .gitignore
└── .github/
    └── workflows/
        └── windows-build.yml
```

## 10. Requirements

### Running from source

- Windows 10/11 recommended
- Python 3.11 or 3.12 recommended
- Internet is initially required to install Python packages
- Normal image processing is local/offline after dependencies are installed

### Python dependencies

- **Pillow** — images and clipboard
- **OpenCV** — face/ink detection
- **NumPy** — image operations
- **PyMuPDF** — PDF rendering
- **PyInstaller** — Windows EXE packaging

## 11. Run from source

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

## 12. Build Windows EXE

Developer build:

```bat
build_windows.bat
```

Output:

```text
dist\PhotoSignatureStudio.exe
```

The `.bat` file is a build tool. End users should run `PhotoSignatureStudio.exe`.

## 13. GitHub Actions Windows build

The workflow in `.github/workflows/windows-build.yml` builds the standalone Windows executable and uploads it as an artifact.

Artifact:

```text
PhotoSignatureStudio-Windows
└── PhotoSignatureStudio.exe
```

## 14. Roadmap

### Phase 1 — Record management

- Record-management UI
- New/open/search records
- Automatic Record ID creation
- Managed source/photo/signature/document folders
- One-click **Open Record Folder**
- One-click **Copy Photo Path** and **Copy Signature Path**
- Record-level export/backup

### Phase 2 — Document intelligence

- Chandra OCR integration
- Structured data extraction
- OCR verification/editing
- Automatic document/page classification
- Photo and signature region detection
- Automatic extraction and linking to the correct Record ID
- Portal requirement extraction where technically feasible

### Phase 3 — Processing productivity

- Batch processing
- Drag-and-drop
- Portal presets
- Application kits
- Duplicate detection
- Hindi/English interface
- Large-file memory controls
- Background processing/progress/cancellation

### Phase 4 — Web automation

- Browser automation framework
- Portal-specific adapters
- Field mapping from Record data to portal fields
- Upload linked photo/signature/document files
- Pre-submission validation
- User review and confirmation
- Automation logs

## 15. Current project status

**Functional offline MVP + record/OCR/storage architecture foundation**

### Implemented now

- Windows desktop GUI
- Clipboard image/screenshot paste with Ctrl+V
- Clipboard file-path support where available
- Image and PDF input
- Photo processing
- Signature cleanup
- Exact pixel dimensions
- KB-target JPEG optimization
- Preview/export
- Standalone Windows build
- GitHub Actions build artifact
- SQLite relationship foundation
- Record-oriented storage layer
- Dedicated photo/signature directories
- OCR storage format
- Provider-neutral OCR interface
- Future automation boundary

### Not yet implemented

- Chandra OCR engine
- Full record-management UI
- Automatic structured data extraction
- Automatic photo/signature extraction from documents
- Browser/web automation
- AI background removal
- Batch processing
- Installer package

## 16. Privacy and security

The application is designed around local processing and local record storage. Sensitive source documents, photos, signatures and OCR data should remain outside public repositories.

Future web automation should be explicit and user-controlled, with a review step before submitting data to an external portal.

## License

Add the project's chosen license before public redistribution. Until a license is added, GitHub users should not assume permission to redistribute or commercially reuse the source.
