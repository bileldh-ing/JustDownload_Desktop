from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from justdownload.config import locate_binary


class MediaProbeError(RuntimeError):
    pass


@dataclass(frozen=True)
class MediaInfo:
    path: Path
    title: str
    duration: float | None
    size_bytes: int
    format_name: str
    format_long_name: str
    video_codec: str | None
    audio_codec: str | None
    width: int | None
    height: int | None
    frame_rate: str | None
    has_video: bool
    has_audio: bool

    @property
    def summary(self) -> str:
        bits: list[str] = []
        if self.has_video and self.width and self.height:
            bits.append(f"{self.width} × {self.height}")
        if self.duration is not None:
            total = int(self.duration)
            bits.append(f"{total // 60:02d}:{total % 60:02d}")
        if self.audio_codec:
            bits.append(self.audio_codec.upper())
        if self.video_codec:
            bits.append(self.video_codec.upper())
        return "  ·  ".join(bits) or "Media stream detected"


def probe_media(path: Path, timeout: int = 45) -> MediaInfo:
    ffprobe = locate_binary("ffprobe")
    if not ffprobe:
        raise MediaProbeError("FFprobe was not found. Install FFmpeg and make sure ffprobe is on your PATH.")
    if not path.is_file() or path.stat().st_size <= 0:
        raise MediaProbeError("The media file is missing or empty.")
    command = [
        ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise MediaProbeError("Media inspection timed out.") from exc
    except OSError as exc:
        raise MediaProbeError("FFprobe could not be started. Check your FFmpeg installation.") from exc
    if completed.returncode != 0:
        raise MediaProbeError("This file is not a supported or readable media file.")
    try:
        payload: dict[str, Any] = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise MediaProbeError("FFprobe returned invalid media information.") from exc
    streams = payload.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video" and not (s.get("disposition") or {}).get("attached_pic")), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not video and not audio:
        raise MediaProbeError("No audio or video stream was found in this file.")
    fmt = payload.get("format") or {}
    duration_raw = fmt.get("duration")
    try:
        duration = float(duration_raw) if duration_raw not in (None, "N/A") else None
        if duration is not None and (duration < 0 or duration > 7 * 24 * 3600):
            duration = None
    except (TypeError, ValueError):
        duration = None
    width = int(video["width"]) if video and video.get("width") else None
    height = int(video["height"]) if video and video.get("height") else None
    size = path.stat().st_size
    tags = fmt.get("tags") or {}
    title = str(tags.get("title") or path.stem).strip()[:300] or path.stem
    return MediaInfo(
        path=path,
        title=title,
        duration=duration,
        size_bytes=size,
        format_name=str(fmt.get("format_name") or path.suffix.lstrip(".") or "unknown"),
        format_long_name=str(fmt.get("format_long_name") or "Media file"),
        video_codec=video.get("codec_name") if video else None,
        audio_codec=audio.get("codec_name") if audio else None,
        width=width,
        height=height,
        frame_rate=(video.get("avg_frame_rate") or video.get("r_frame_rate")) if video else None,
        has_video=video is not None,
        has_audio=audio is not None,
    )


def format_bytes(value: int | None) -> str:
    if value is None:
        return "Size not reported"
    units = ["B", "KB", "MB", "GB", "TB"]
    amount = float(value)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return f"{amount:.1f} TB"
