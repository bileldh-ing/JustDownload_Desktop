# JustDownload Desktop

A native desktop adaptation of the supplied JustDownload product brief. It provides a premium dark desktop interface for inspecting **direct audio/video file URLs**, converting local media, and producing verified output files.

> Use only media you own or are authorized to download or convert. JustDownload does not extract media from website pages or streaming platforms and does not bypass DRM, paywalls, authentication, private-account restrictions, or other access controls.

## What works

- Native desktop UI built with Python's Tkinter; no browser or local web server is required.
- Local audio/video file inspection using FFprobe.
- Direct HTTP(S) media URL inspection using validated HTTP headers. URL inspection does not download the entire file; duration and stream details are verified after the user starts processing.
- Real direct-file downloads with byte-based progress and a configurable 2 GiB default source limit.
- Real FFmpeg outputs: original file, MP3 (VBR quality setting), M4A/AAC (192 kb/s), WAV (PCM), and MP4 (H.264 video with AAC audio when present).
- Output verification with FFprobe before the file is placed in the selected output folder.
- Background worker, cancellation, safe filenames, collision-safe output names, temporary workspace cleanup, SHA-256 result checksum.
- Local-first processing. Source and output files remain on the user's computer.

## Requirements

- Python 3.12 or newer (Python 3.13 is supported by the project).
- FFmpeg and FFprobe installed and available on `PATH` for media conversion and verification. The UI reports if either is missing.
- Windows: Python's standard Tkinter component must be installed (included in the standard python.org Windows installer).

The app uses Python standard-library modules at runtime. PyInstaller 6.22.3 is only needed to create a packaged executable.

## Run from source

```bash
python app.py
```

## Build on Windows

1. Install Python 3.12+ and FFmpeg/FFprobe.
2. Add the FFmpeg `bin` folder to `PATH`, then reopen the terminal.
3. Double-click `build_windows.bat` or run it from Command Prompt.
4. The app is created at `dist\JustDownload.exe`.

For a self-contained FFmpeg package, place properly licensed and verified `ffmpeg.exe` and `ffprobe.exe` in `vendor\ffmpeg\` before building. The build script includes that directory when both executables are present. Review the exact FFmpeg build's licensing terms before redistributing it.

A Windows build workflow is provided at `.github/workflows/build-windows.yml`. Run it from GitHub Actions on a Windows runner to produce a Windows artifact.

## Build on Linux

```bash
./build_linux.sh
```

This creates a Linux executable under `dist/`; it does not create a Windows `.exe`.

## Tests

```bash
python -m unittest discover -s tests -v
```

The media integration test uses the locally installed FFmpeg to generate a short synthetic WAV fixture, performs an actual MP3 conversion, and validates the resulting stream with FFprobe.

## Supported source policy

| Source | Inspection | Processing |
|---|---|---|
| Local audio/video file | Full FFprobe inspection | Original, MP3/M4A/WAV when audio exists, MP4 when video exists |
| Direct HTTP(S) audio/video file URL | Header-level inspection; actual streams checked after acquisition | Same outputs, after download and FFprobe validation |
| Website pages / streaming platform URLs | Not supported | Not supported |
| DRM, private, login-protected or paywalled media | Not supported | Not supported |

The URL inspector rejects non-HTTP schemes, embedded credentials, non-standard ports, localhost and non-public IP destinations, and revalidates redirect targets. This desktop utility is not a substitute for OS-level network isolation; see `docs/SECURITY.md` before exposing it to untrusted workflows.

## Output behavior

- **Original file** copies the verified source into the chosen output folder without re-encoding.
- **MP3** extracts the first audio stream and encodes it with FFmpeg's `libmp3lame` VBR quality value `2`.
- **M4A** encodes AAC audio at 192 kb/s.
- **WAV** encodes 16-bit PCM audio.
- **MP4** transcodes the first video stream to H.264 using `libx264` and encodes audio to AAC when audio is present.

Conversion cannot restore quality absent from the source. MP4 output is a re-encode, not a lossless remux. Progress is shown only when actual download bytes or FFmpeg time progress is available; otherwise the app shows an indeterminate stage.

## Configuration

- `JUSTDOWNLOAD_MAX_REMOTE_BYTES`: maximum bytes accepted from a direct remote URL. Default: `2147483648` (2 GiB).
- Output directory default: `~/Downloads/JustDownload`.
- Temporary job files are stored in the current user's application-data directory and deleted when a job ends.

## Project structure

```text
app.py
justdownload/
  config.py
  core/          # job coordination, filenames, URL policy
  media/         # direct URL inspection, FFprobe, FFmpeg pipeline
  ui/            # native Tkinter desktop interface
tests/
docs/
.github/workflows/
build_windows.bat
build_linux.sh
```

## Known limitations

- No scraping or extraction adapters for YouTube, Facebook, TikTok, or other website/platform pages are included. Only direct media file URLs and local files are supported.
- Remote URL inspection is header-only by design. Full codec, duration, and stream information becomes available only after the user starts processing and the file is acquired.
- Only one local job is processed at a time in this first desktop release.
- FFmpeg/FFprobe are external requirements unless the operator adds an appropriately licensed build to `vendor/ffmpeg/`.
- The desktop client relies on local DNS validation and redirect checks. For stronger protection in managed environments, run it with OS/firewall egress restrictions.
- Before public commercial distribution, obtain qualified legal review of provider use, copyright handling, privacy notices, and the exact FFmpeg build/licensing configuration.
