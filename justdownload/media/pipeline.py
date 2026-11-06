from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from justdownload.config import FFMPEG_TIMEOUT_SECONDS, app_data_dir, locate_binary
from justdownload.core.filename import non_conflicting_path, with_extension
from justdownload.media.probe import MediaInfo, MediaProbeError, probe_media
from justdownload.media.remote import RemoteInspection, download_remote


@dataclass(frozen=True)
class JobRequest:
    source_kind: str  # local | remote
    source: str
    remote_inspection: RemoteInspection | None
    profile: str
    output_dir: Path
    output_name: str


@dataclass(frozen=True)
class JobEvent:
    job_id: str
    state: str
    stage: str
    message: str
    percent: float | None = None
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    speed_bytes_per_second: float | None = None
    eta_seconds: int | None = None
    result_path: Path | None = None
    error: str | None = None


@dataclass(frozen=True)
class JobResult:
    path: Path
    size_bytes: int
    sha256: str
    media: MediaInfo


class PipelineError(RuntimeError):
    pass


PROFILES = {
    "original": {"extension": None, "label": "Original file"},
    "mp3": {"extension": ".mp3", "label": "MP3 · High quality"},
    "m4a": {"extension": ".m4a", "label": "M4A · AAC 192 kb/s"},
    "wav": {"extension": ".wav", "label": "WAV · PCM"},
    "mp4": {"extension": ".mp4", "label": "MP4 · H.264 + AAC"},
}


def _emit(callback: Callable[[JobEvent], None], event: JobEvent) -> None:
    callback(event)


def _run_ffmpeg(command: list[str], duration: float | None, cancel_event, callback, job_id: str) -> None:
    try:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, text=True, bufsize=1,
        )
    except OSError as exc:
        raise PipelineError("FFmpeg could not be started. Install FFmpeg and make sure it is on your PATH.") from exc
    try:
        assert process.stdout is not None
        for line in process.stdout:
            if cancel_event.is_set():
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
                raise InterruptedError("Processing cancelled.")
            key, _, value = line.strip().partition("=")
            if key == "out_time_ms" and duration and duration > 0:
                try:
                    # FFmpeg's progress value is in microseconds despite the historical key name.
                    seconds = int(value) / 1_000_000
                    percent = min(99.0, max(0.0, seconds / duration * 100))
                    _emit(callback, JobEvent(
                        job_id, "converting", "Converting media", "Encoding with FFmpeg…",
                        percent=percent,
                    ))
                except ValueError:
                    pass
            elif key == "progress" and value == "end":
                _emit(callback, JobEvent(job_id, "validating_output", "Verifying output", "Checking the finished media file…", percent=None))
        return_code = process.wait(timeout=FFMPEG_TIMEOUT_SECONDS)
        if return_code != 0:
            raise PipelineError("FFmpeg could not create this output. Try another format or check the source file.")
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.wait()
        raise PipelineError("Media processing exceeded the one-hour safety limit.") from exc
    finally:
        if process.stdout is not None:
            process.stdout.close()
        if process.poll() is None:
            process.kill()
            process.wait()


def _ffmpeg_command(input_path: Path, output_path: Path, profile: str, media: MediaInfo) -> list[str]:
    ffmpeg = locate_binary("ffmpeg")
    if not ffmpeg:
        raise PipelineError("FFmpeg was not found. Install FFmpeg and make sure ffmpeg is on your PATH.")
    base = [ffmpeg, "-hide_banner", "-nostdin", "-y", "-i", str(input_path)]
    if profile == "mp3":
        if not media.has_audio:
            raise PipelineError("This file has no audio stream to convert.")
        return base + ["-map", "0:a:0", "-vn", "-c:a", "libmp3lame", "-q:a", "2", "-map_metadata", "0", "-progress", "pipe:1", "-nostats", str(output_path)]
    if profile == "m4a":
        if not media.has_audio:
            raise PipelineError("This file has no audio stream to convert.")
        return base + ["-map", "0:a:0", "-vn", "-c:a", "aac", "-b:a", "192k", "-map_metadata", "0", "-progress", "pipe:1", "-nostats", str(output_path)]
    if profile == "wav":
        if not media.has_audio:
            raise PipelineError("This file has no audio stream to convert.")
        return base + ["-map", "0:a:0", "-vn", "-c:a", "pcm_s16le", "-map_metadata", "0", "-progress", "pipe:1", "-nostats", str(output_path)]
    if profile == "mp4":
        if not media.has_video:
            raise PipelineError("MP4 video output requires a video stream.")
        command = base + ["-map", "0:v:0", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]
        if media.has_audio:
            command += ["-c:a", "aac", "-b:a", "192k"]
        return command + ["-movflags", "+faststart", "-progress", "pipe:1", "-nostats", str(output_path)]
    raise PipelineError("The selected output format is not supported.")


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_profile(media: MediaInfo, profile: str) -> None:
    if profile == "mp3" and media.audio_codec != "mp3":
        raise PipelineError("The output validation failed: the result is not an MP3 audio stream.")
    if profile == "m4a" and media.audio_codec != "aac":
        raise PipelineError("The output validation failed: the result does not contain AAC audio.")
    if profile == "wav" and not (media.format_name.lower().find("wav") >= 0 and media.has_audio):
        raise PipelineError("The output validation failed: the result is not a readable WAV file.")
    if profile == "mp4" and (not media.has_video or media.video_codec != "h264"):
        raise PipelineError("The output validation failed: the result does not contain H.264 video.")


def process_job(request: JobRequest, cancel_event, callback: Callable[[JobEvent], None], job_id: str | None = None) -> JobResult:
    job_id = job_id or uuid.uuid4().hex
    work_root = app_data_dir() / "work"
    work_root.mkdir(parents=True, exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(prefix=f"{job_id[:8]}-", dir=work_root))
    source_path: Path | None = None
    partial_output: Path | None = None
    try:
        if request.profile not in PROFILES:
            raise PipelineError("Unsupported output selection.")
        if request.source_kind == "remote":
            if not request.remote_inspection:
                raise PipelineError("Inspect the media URL again before processing it.")
            source_path = work_dir / "source.download"
            _emit(callback, JobEvent(job_id, "downloading", "Downloading source", "Connecting to the direct media file…"))
            def on_download(done: int, total: int | None, speed: float) -> None:
                percent = min(99.0, done / total * 100) if total else None
                eta = int((total - done) / speed) if total and speed > 0 else None
                _emit(callback, JobEvent(job_id, "downloading", "Downloading source", "Receiving media data…", percent, done, total, speed, eta))
            download_remote(request.remote_inspection, source_path, cancel_event, on_download)
        elif request.source_kind == "local":
            source_path = Path(request.source)
            if not source_path.is_file():
                raise PipelineError("The selected local file is no longer available.")
        else:
            raise PipelineError("Unknown source type.")
        if cancel_event.is_set():
            raise InterruptedError("Processing cancelled.")
        _emit(callback, JobEvent(job_id, "inspecting", "Inspecting media", "Reading the actual audio and video streams…"))
        try:
            source_info = probe_media(source_path)
        except MediaProbeError as exc:
            raise PipelineError(str(exc)) from exc
        if request.profile in {"mp3", "m4a", "wav"} and not source_info.has_audio:
            raise PipelineError("This source has no audio stream. Choose original file or a video output.")
        if request.profile == "mp4" and not source_info.has_video:
            raise PipelineError("This source has no video stream. Choose an audio output instead.")
        if cancel_event.is_set():
            raise InterruptedError("Processing cancelled.")
        if request.profile == "original":
            if request.source_kind == "remote" and request.remote_inspection:
                extension = Path(request.remote_inspection.filename).suffix or ".media"
            else:
                extension = source_path.suffix or ".media"
            filename = request.output_name
            if Path(filename).suffix.lower() != extension.lower():
                filename = with_extension(filename, extension)
            partial_output = work_dir / f"output{extension}"
            _emit(callback, JobEvent(job_id, "copying", "Preparing original file", "Copying the verified source file…"))
            total = source_path.stat().st_size
            done = 0
            started = time.monotonic()
            with source_path.open("rb") as inp, partial_output.open("wb") as out:
                while True:
                    if cancel_event.is_set():
                        raise InterruptedError("Processing cancelled.")
                    chunk = inp.read(1024 * 512)
                    if not chunk:
                        break
                    out.write(chunk)
                    done += len(chunk)
                    elapsed = max(time.monotonic() - started, 0.001)
                    speed = done / elapsed
                    _emit(callback, JobEvent(job_id, "copying", "Preparing original file", "Copying verified media…", min(99.0, done / max(total, 1) * 100), done, total, speed, int((total-done)/speed) if speed else None))
        else:
            extension = str(PROFILES[request.profile]["extension"])
            filename = with_extension(request.output_name, extension)
            partial_output = work_dir / f"output{extension}"
            _emit(callback, JobEvent(job_id, "converting", "Converting media", f"Creating {PROFILES[request.profile]['label']}…"))
            command = _ffmpeg_command(source_path, partial_output, request.profile, source_info)
            _run_ffmpeg(command, source_info.duration, cancel_event, callback, job_id)
        if cancel_event.is_set():
            raise InterruptedError("Processing cancelled.")
        _emit(callback, JobEvent(job_id, "validating_output", "Verifying output", "Checking streams, file size and media integrity…"))
        if not partial_output or not partial_output.is_file() or partial_output.stat().st_size <= 0:
            raise PipelineError("The output file was not created correctly.")
        try:
            output_info = probe_media(partial_output)
        except MediaProbeError as exc:
            raise PipelineError(f"The finished output could not be verified: {exc}") from exc
        _verify_profile(output_info, request.profile)
        output_path = non_conflicting_path(request.output_dir, filename)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(partial_output, output_path)
        size = output_path.stat().st_size
        checksum = _hash_file(output_path)
        result = JobResult(output_path, size, checksum, output_info)
        _emit(callback, JobEvent(job_id, "ready", "Ready to download", "Your verified media file is ready.", 100.0, result_path=output_path))
        return result
    except InterruptedError:
        _emit(callback, JobEvent(job_id, "cancelled", "Cancelled", "The operation was cancelled. Temporary files were removed."))
        raise
    except Exception as exc:
        _emit(callback, JobEvent(job_id, "failed", "Could not finish", str(exc), error=str(exc)))
        raise
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
