@echo off
setlocal
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

rem OpenCV Haar cascade XML files are data files and are not reliably bundled by PyInstaller.
rem Include the complete cv2/data directory so automatic face detection works in the EXE.
for /f "delims=" %%i in ('python -c "import cv2; print(cv2.data.haarcascades)"') do set "CV2_HAAR=%%i"
if not exist "%CV2_HAAR%haarcascade_frontalface_default.xml" exit /b 1

python -m PyInstaller --noconfirm --clean --onefile --windowed --add-data "%CV2_HAAR%;cv2\data" --name PhotoSignatureStudio main.py
if errorlevel 1 exit /b 1
echo BUILD COMPLETE: dist\PhotoSignatureStudio.exe
