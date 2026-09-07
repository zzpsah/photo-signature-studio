# Photo & Signature Studio

A local/offline Windows utility for turning pasted images, PDF pages, and scanned documents into exact-size photo and signature files.

## Features
- Clipboard input with **Ctrl+V**
- Open JPG/JPEG/PNG/WebP/BMP/TIFF
- Open PDF and select any page in multi-page PDFs
- Photo mode with face detection and conservative portrait crop
- White background output and exact pixel dimensions
- Signature mode with ink/background isolation and automatic crop
- Optional light image enhancement
- JPEG compression targeting a maximum KB limit
- PNG output when needed
- Windows standalone `.exe` build with PyInstaller
- GitHub Actions workflow that publishes the Windows executable as a build artifact
- No cloud upload or server-side processing

## Run from source

```bat
python -m venv .venv
.venv\\Scripts\\activate
python -m pip install -r requirements.txt
python app.py
```

## Build standalone EXE

Run `build_windows.bat`. The executable will be `dist\\PhotoSignatureStudio.exe`.

## Notes
Presets are examples. Government portals can change requirements, so use Custom Photo/Custom Signature for the exact pixel and file-size limits shown by the destination portal. Automatic face crop is a convenience feature; visually check the final result before submission.
