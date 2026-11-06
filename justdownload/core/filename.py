from __future__ import annotations

import re
import unicodedata
from pathlib import Path

_RESERVED = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_SPACES = re.compile(r"\s+")


def safe_stem(value: str, fallback: str = "media", limit: int = 110) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    value = _RESERVED.sub("_", value)
    value = _SPACES.sub(" ", value).strip(" .")
    value = value[:limit].rstrip(" .")
    if not value or value in {".", ".."}:
        value = fallback
    # Windows device names are reserved even when followed by an extension.
    if value.split(".", 1)[0].upper() in {
        "CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))
    }:
        value = f"_{value}"
    return value


def with_extension(filename: str, extension: str) -> str:
    ext = extension if extension.startswith(".") else f".{extension}"
    stem = safe_stem(Path(filename).stem or filename)
    return f"{stem}{ext.lower()}"


def non_conflicting_path(directory: Path, filename: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem, suffix = candidate.stem, candidate.suffix
    index = 1
    while True:
        next_candidate = directory / f"{stem} ({index}){suffix}"
        if not next_candidate.exists():
            return next_candidate
        index += 1
