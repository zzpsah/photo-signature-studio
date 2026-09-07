@echo off
setlocal
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --onefile --windowed --name PhotoSignatureStudio main.py
if errorlevel 1 exit /b 1
echo BUILD COMPLETE: dist\PhotoSignatureStudio.exe
