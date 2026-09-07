# Photo & Signature Studio

A **local/offline Windows desktop utility** for converting photos, signatures, scanned documents, and PDF pages into portal-ready image files with exact pixel dimensions, white backgrounds, and configurable file-size limits.

> **Privacy:** Processing is designed to happen locally on the computer. The application does not upload identity documents, photographs, or signatures to a cloud service.

## 1. What the application does

The main workflow is:

```text
PDF / Image / Clipboard
          |
          v
    Input Processor
          |
          +------------------+
          |                  |
          v                  v
       PHOTO             SIGNATURE
          |                  |
    Face detection      Ink detection
    Portrait crop       Background cleanup
    White background    White background
    Exact dimensions    Exact dimensions
          |                  |
          +--------+---------+
                   |
                   v
            JPEG/PNG output
                   |
                   v
          KB-size optimization
```

### Supported input

- Clipboard image (`Ctrl+V`)
- JPG / JPEG
- PNG
- WebP
- BMP
- TIFF
- PDF
- Drag-and-drop can be added to the UI in a future release

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

## 2. Important accuracy note

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

## 3. Repository file structure

```text
photo-signature-studio/
│
├── app.py
│   └── Main desktop application.
│       Tkinter UI, clipboard handling, file selection,
│       PDF rendering, photo processing, signature processing,
│       preview, resizing and output generation.
│
├── requirements.txt
│   └── Python packages required to run the application.
│
├── build_windows.bat
│   └── Local Windows build script. Creates the standalone EXE
│       using PyInstaller.
│
├── README.md
│   └── Project documentation, setup instructions and architecture.
│
├── .gitignore
│   └── Prevents Python caches, virtual environments and build
│       output from being committed.
│
└── .github/
    └── workflows/
        └── windows-build.yml
            └── GitHub Actions workflow that installs dependencies,
                builds the Windows EXE and uploads it as an artifact.
```

### Generated directories

These are **not source files** and should not normally be committed:

```text
.venv/       Python virtual environment
__pycache__/ Python bytecode cache
build/       PyInstaller temporary build files
 dist/       Final Windows executable
```

## 4. Requirements

### For running from source

- Windows 10/11 recommended
- Python 3.11 or 3.12 recommended
- Internet is required only to install Python packages initially
- After dependencies are installed, image processing itself can run offline

### Python dependencies

The project uses:

- **Pillow** — image loading, manipulation, clipboard support and output
- **OpenCV** — face/ink detection and image processing
- **NumPy** — numerical image operations
- **PyMuPDF** — local PDF rendering
- **PyInstaller** — standalone Windows executable creation

Exact package versions are maintained in `requirements.txt`.

## 5. Run from source on Windows

Open **Command Prompt** in the project directory.

### Create virtual environment

```bat
python -m venv .venv
```

### Activate it

```bat
.venv\Scripts\activate
```

### Install dependencies

```bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Start the application

```bat
python app.py
```

The desktop window should open.

## 6. Build the standalone Windows EXE

The easiest method is:

```bat
build_windows.bat
```

The script installs the required packages and runs PyInstaller.

The resulting file is:

```text
dist\PhotoSignatureStudio.exe
```

The application is built as a windowed standalone executable, so the end user does not need to open a Python terminal.

## 7. Build manually

If you prefer to run the commands yourself:

```bat
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --onefile --windowed --name PhotoSignatureStudio app.py
```

Output:

```text
dist\PhotoSignatureStudio.exe
```

## 8. GitHub Actions Windows build

The repository contains:

```text
.github/workflows/windows-build.yml
```

The workflow:

1. Checks out the repository
2. Installs Python 3.12
3. Installs `requirements.txt`
4. Runs PyInstaller
5. Creates `PhotoSignatureStudio.exe`
6. Uploads the EXE as a GitHub Actions artifact

### Running the build

A push to `main` triggers the workflow. It can also be started manually from the GitHub Actions tab using **Run workflow**.

The artifact is named:

```text
PhotoSignatureStudio-Windows
```

Inside the artifact:

```text
PhotoSignatureStudio.exe
```

## 9. Basic usage

### A. Paste a photo

1. Copy an image from a browser, PDF viewer, image editor, scanner application, etc.
2. Open Photo & Signature Studio.
3. Press **Ctrl+V**.
4. Select **Photo** mode.
5. Choose a preset or enter Custom dimensions.
6. Set the maximum KB value if required.
7. Process/export the result.

### B. Open an image

1. Click the image/file open control.
2. Select JPG, PNG, WebP, BMP or TIFF.
3. Select Photo or Signature mode.
4. Configure dimensions and KB.
5. Process and save.

### C. Process a PDF

1. Open the PDF.
2. Select the required PDF page.
3. The selected page is rendered locally as an image.
4. Select Photo or Signature mode.
5. Process and export.

### D. Signature

1. Scan or copy the signature image.
2. Paste with `Ctrl+V` or open the image/PDF.
3. Select Signature mode.
4. Set exact width and height.
5. Set maximum KB if required.
6. Process and inspect the result.

## 10. Presets and Custom mode

Presets are convenience configurations, **not authoritative specifications**.

For a form that says, for example:

```text
Photo: 200 × 230 pixels
Maximum size: 50 KB
Format: JPG
```

enter:

```text
Width:  200
Height: 230
Max KB: 50
Format: JPG
```

For a signature requirement:

```text
Width:  140
Height: 60
Max KB: 20
Format: JPG/PNG
```

Use the exact values stated by the target portal.

## 11. Output-size optimization

When a maximum KB value is specified, the application attempts to reduce JPEG quality until the resulting file is at or below the requested limit.

Very small KB limits can noticeably reduce image quality. If the destination portal allows a larger file, prefer the larger limit.

PNG is not suitable for every KB-constrained photograph because PNG compression is lossless and may produce a larger file than JPEG.

## 12. Privacy and security

The intended processing model is local:

```text
Your computer
    |
    +-- Photo
    +-- Signature
    +-- PDF
    |
    v
Photo & Signature Studio
    |
    v
Output file
```

There is no application server required for normal processing.

Do not place sensitive identity documents in public GitHub issues, commits, screenshots, or test fixtures.

## 13. Development architecture

The current implementation intentionally keeps the architecture simple so it can be packaged reliably for Windows:

```text
Tkinter UI
   |
   +-- Clipboard / file input
   |
   +-- PDF rendering (PyMuPDF)
   |
   +-- Image processing (Pillow + OpenCV + NumPy)
   |
   +-- Photo pipeline
   |
   +-- Signature pipeline
   |
   +-- Resize / compression
   |
   +-- Preview / export
   |
   +-- PyInstaller packaging
```

## 14. Planned enhancements

The current repository is the foundation for a fuller production application. Potential next modules include:

- Modern Windows UI
- Drag-and-drop support
- Better AI/ML portrait segmentation and background removal
- More accurate passport composition and head-position rules
- Manual crop editor with draggable guides
- Automatic photo/signature classification
- Batch processing
- A4 and 4×6 print-sheet generation
- Photo + signature application kits
- Multiple configurable portal presets
- Hindi/English interface
- EXIF orientation handling
- Undo/redo
- Side-by-side original/result comparison
- Installation package (`Setup.exe`)
- Versioned releases
- Automated unit and image-processing tests

## 15. Troubleshooting

### `python` is not recognized

Install Python and ensure **Add Python to PATH** is enabled, then reopen Command Prompt.

### Tkinter error

Use the standard Windows Python installer. Tkinter is included with the normal CPython Windows distribution.

### PDF does not open

Reinstall dependencies:

```bat
python -m pip install -r requirements.txt --upgrade
```

### OpenCV cannot find the face

Face detection is dependent on image quality, lighting, angle and face size. Use the manual/custom crop workflow and verify the output visually.

### Signature has unwanted background

Use a clean, high-resolution scan with strong contrast between ink and paper. The automatic signature cleanup is intentionally conservative and should be inspected before submission.

### EXE is missing after build

Check:

```text
dist\PhotoSignatureStudio.exe
```

If it is not present, run the build from Command Prompt rather than double-clicking the batch file so that errors remain visible.

## 16. Project status

**Current:** Functional offline MVP / foundation

The repository is structured so the processing engine can be improved independently from the desktop UI and packaging system.

## License

Add the project's chosen license before public redistribution. Until a license is added, GitHub users should not assume permission to redistribute or commercially reuse the source.
