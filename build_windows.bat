@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher was not found. Install Python 3.12 or newer first.
  exit /b 1
)
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,12) else 1)"
if errorlevel 1 (
  echo Python 3.12 or newer is required.
  exit /b 1
)
py -3 -m venv .venv
if errorlevel 1 exit /b 1
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install pyinstaller==6.22.3
if exist vendor\ffmpeg\ffmpeg.exe (
  if exist vendor\ffmpeg\ffprobe.exe (
    pyinstaller --noconfirm --clean --onefile --windowed --name JustDownload --add-data "vendor\ffmpeg;vendor\ffmpeg" app.py
  ) else (
    pyinstaller --noconfirm --clean --onefile --windowed --name JustDownload app.py
  )
) else (
  pyinstaller --noconfirm --clean --onefile --windowed --name JustDownload app.py
)
if errorlevel 1 exit /b 1
echo.
echo Build complete: dist\JustDownload.exe
if exist vendor\ffmpeg\ffmpeg.exe (
  if exist vendor\ffmpeg\ffprobe.exe (
    echo Bundled FFmpeg tools were included.
  ) else (
    echo NOTE: FFprobe is missing. Install FFmpeg/FFprobe and add them to PATH.
  )
) else (
  echo NOTE: FFmpeg/FFprobe must be installed separately and added to PATH.
)
endlocal
