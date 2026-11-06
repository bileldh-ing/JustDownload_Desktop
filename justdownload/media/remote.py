from __future__ import annotations

import mimetypes
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from justdownload.config import MAX_REMOTE_BYTES, NETWORK_TIMEOUT_SECONDS
from justdownload.core.filename import safe_stem
from justdownload.core.url_guard import URLRejected, validate_url


class RemoteMediaError(RuntimeError):
    pass


@dataclass(frozen=True)
class RemoteInspection:
    url: str
    filename: str
    content_type: str
    size_bytes: int | None
    media_kind: str
    status: str
    final_url: str


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        try:
            safe_url = validate_url(urllib.parse.urljoin(req.full_url, newurl))
        except URLRejected as exc:
            raise RemoteMediaError(str(exc)) from exc
        return super().redirect_request(req, fp, code, msg, headers, safe_url)


def _opener() -> urllib.request.OpenerDirector:
    # Ignore desktop proxy settings: proxies can invalidate the local SSRF policy.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _SafeRedirect())


def _content_kind(content_type: str, url: str) -> str:
    major = (content_type or "").split(";", 1)[0].strip().lower()
    if major.startswith("video/"):
        return "video"
    if major.startswith("audio/"):
        return "audio"
    if major and major not in {
        "application/octet-stream", "binary/octet-stream", "application/x-download",
        "application/download", "application/mp4", "application/x-matroska",
    }:
        return "unknown"
    guessed, _ = mimetypes.guess_type(urllib.parse.urlsplit(url).path)
    if guessed and guessed.startswith("video/"):
        return "video"
    if guessed and guessed.startswith("audio/"):
        return "audio"
    extension = Path(urllib.parse.urlsplit(url).path).suffix.lower()
    if extension in {".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi", ".mpeg", ".mpg", ".ts"}:
        return "video"
    if extension in {".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".flac", ".aiff"}:
        return "audio"
    return "unknown"


def _request(url: str, method: str, headers: dict[str, str] | None = None):
    safe_url = validate_url(url)
    request = urllib.request.Request(safe_url, headers=headers or {}, method=method)
    try:
        return _opener().open(request, timeout=NETWORK_TIMEOUT_SECONDS)
    except urllib.error.HTTPError as exc:
        return exc
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
        raise RemoteMediaError("The source could not be reached. Check the URL and try again.") from exc


def inspect_remote(url: str) -> RemoteInspection:
    safe_url = validate_url(url)
    response = _request(safe_url, "HEAD", {"User-Agent": "JustDownloadDesktop/1.0", "Accept": "video/*,audio/*,application/octet-stream;q=0.8,*/*;q=0.1"})
    try:
        status = getattr(response, "status", response.getcode())
        if status in (405, 501) or status >= 400:
            response.close()
            response = _request(safe_url, "GET", {
                "User-Agent": "JustDownloadDesktop/1.0", "Range": "bytes=0-0",
                "Accept": "video/*,audio/*,application/octet-stream;q=0.8,*/*;q=0.1",
            })
            status = getattr(response, "status", response.getcode())
            # Only read a tiny prefix if the origin ignores the Range request.
            if status == 200:
                response.read(1024)
        final_url = validate_url(response.geturl())
        content_type = response.headers.get("Content-Type", "application/octet-stream")
        length_value = response.headers.get("Content-Length")
        size = int(length_value) if length_value and length_value.isdigit() else None
        content_range = response.headers.get("Content-Range", "")
        if status == 206:
            match = re.search(r"/([0-9]+)$", content_range.strip())
            if match:
                size = int(match.group(1))
        if size is not None and size > MAX_REMOTE_BYTES:
            raise RemoteMediaError(f"This source is larger than the configured {MAX_REMOTE_BYTES // (1024 * 1024)} MB limit.")
        kind = _content_kind(content_type, final_url)
        if kind == "unknown":
            raise RemoteMediaError("This link does not look like a direct audio or video file. Website pages and streaming platforms are not supported.")
        if status >= 400:
            raise RemoteMediaError(f"The source server returned HTTP {status}.")
        decoded_path = urllib.parse.unquote(urllib.parse.urlsplit(final_url).path).replace("\\", "/")
        name = decoded_path.rsplit("/", 1)[-1] or "media"
        extension = Path(name).suffix.lower()
        video_extensions = {".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi", ".mpeg", ".mpg", ".ts", ".3gp"}
        audio_extensions = {".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".flac", ".aiff", ".mpga"}
        allowed_extensions = video_extensions if kind == "video" else audio_extensions
        if extension not in allowed_extensions:
            mime_defaults = {
                "video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov",
                "audio/mpeg": ".mp3", "audio/mp4": ".m4a", "audio/aac": ".aac",
                "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/flac": ".flac", "audio/ogg": ".ogg",
            }
            extension = mime_defaults.get(content_type.split(";", 1)[0].strip().lower(), ".mp4" if kind == "video" else ".mp3")
        filename = safe_stem(Path(name).stem or "media") + extension
        return RemoteInspection(
            url=safe_url, filename=filename, content_type=content_type,
            size_bytes=size, media_kind=kind,
            status="Headers inspected; duration and streams will be verified after acquisition.",
            final_url=final_url,
        )
    finally:
        response.close()


def download_remote(
    inspection: RemoteInspection,
    destination: Path,
    cancel_event,
    progress: Callable[[int, int | None, float], None],
) -> None:
    response = _request(inspection.final_url, "GET", {
        "User-Agent": "JustDownloadDesktop/1.0",
        "Accept": "video/*,audio/*,application/octet-stream;q=0.8,*/*;q=0.1",
    })
    try:
        status = getattr(response, "status", response.getcode())
        if status < 200 or status >= 300:
            raise RemoteMediaError(f"The source server returned HTTP {status}.")
        content_type = response.headers.get("Content-Type", "").lower()
        if not (content_type.startswith("video/") or content_type.startswith("audio/") or content_type.startswith("application/octet-stream") or content_type == ""):
            raise RemoteMediaError("The URL no longer points to a direct media file.")
        if content_type.startswith(("video/", "audio/")):
            observed_kind = "video" if content_type.startswith("video/") else "audio"
            if observed_kind != inspection.media_kind:
                raise RemoteMediaError("The source media type changed after inspection. Inspect the link again.")
        length_value = response.headers.get("Content-Length")
        total = int(length_value) if length_value and length_value.isdigit() else inspection.size_bytes
        if total is not None and total > MAX_REMOTE_BYTES:
            raise RemoteMediaError("The source exceeds the configured download-size limit.")
        downloaded = 0
        started = time.monotonic()
        with destination.open("wb") as output:
            while True:
                if cancel_event.is_set():
                    raise InterruptedError("Processing cancelled.")
                chunk = response.read(1024 * 256)
                if not chunk:
                    break
                downloaded += len(chunk)
                if downloaded > MAX_REMOTE_BYTES:
                    raise RemoteMediaError("The source exceeded the configured download-size limit.")
                output.write(chunk)
                elapsed = max(time.monotonic() - started, 0.001)
                progress(downloaded, total, downloaded / elapsed)
        if downloaded == 0:
            raise RemoteMediaError("The source returned an empty file.")
        if total is not None and downloaded < total:
            raise RemoteMediaError("The connection ended before the full file was downloaded.")
    finally:
        response.close()
