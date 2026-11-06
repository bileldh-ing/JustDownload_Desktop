#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv-build
. .venv-build/bin/activate
python -m pip install --upgrade pip
python -m pip install pyinstaller==6.22.3
python -m PyInstaller --noconfirm --clean --windowed --name JustDownload app.py
printf '\nBuild complete: dist/JustDownload/JustDownload\n'
