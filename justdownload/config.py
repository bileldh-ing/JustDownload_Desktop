from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "JustDownload"
APP_VERSION = "1.0.0"
MAX_REMOTE_BYTES = int(os.environ.get("JUSTDOWNLOAD_MAX_REMOTE_BYTES", str(2 * 1024 * 1024 * 1024)))
NETWORK_TIMEOUT_SECONDS = 25
FFMPEG_TIMEOUT_SECONDS = 60 * 60


def app_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_output_dir() -> Path:
    path = Path.home() / "Downloads" / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def locate_binary(name: str) -> str | None:
    """Find FFmpeg tools in PATH or in the optional bundled tools folder."""
    import shutil

    candidates = [
        Path(__file__).resolve().parents[1] / "vendor" / "ffmpeg" / (name + (".exe" if sys.platform == "win32" else "")),
        Path(sys.executable).resolve().parent / "ffmpeg" / (name + (".exe" if sys.platform == "win32" else "")),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return shutil.which(name)
