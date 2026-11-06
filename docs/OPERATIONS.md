# Operations and maintenance

## Runtime dependencies

- Python 3.12+ for source execution.
- FFmpeg and FFprobe for media processing and verification.
- PyInstaller only for packaging.

The desktop app does not need PostgreSQL, Redis, a web server, or a network service.

## FFmpeg setup

Install a current FFmpeg build from a trusted source and place its `bin` directory on `PATH`. Restart the terminal/session before launching JustDownload. The application checks `ffmpeg` and `ffprobe` at startup and displays their availability. For redistribution, review the exact build's configure flags, linked libraries and LGPL/GPL obligations before placing binaries in `vendor/ffmpeg/`.

## Resource controls

- Remote source limit: 2 GiB by default; configure using `JUSTDOWNLOAD_MAX_REMOTE_BYTES`.
- One active media job per application instance.
- FFmpeg conversion timeout: one hour.
- Temporary workspace is under the current user's application-data directory and deleted on job completion or failure.
- Final outputs default to `~/Downloads/JustDownload`; the user can choose another destination.

## Troubleshooting

- **FFmpeg/FFprobe missing:** install both and add their `bin` directory to `PATH`, or supply the two executables in `vendor/ffmpeg/` before packaging.
- **Direct URL rejected:** check that it is a direct file URL, uses HTTP(S), does not resolve to a private destination and does not redirect to a restricted host.
- **Source metadata unavailable:** URL inspection is header-only; actual stream metadata is read after the source is acquired for processing.
- **Conversion failure:** try Original file or another valid output profile; check the source with FFprobe and ensure the FFmpeg build contains the requested codec.
- **Output already exists:** JustDownload adds a numbered suffix rather than overwriting it.

## Release process

1. Run the unittest suite and manual desktop acceptance checks.
2. Verify FFmpeg/FFprobe versions and binary provenance.
3. Run the Windows build workflow on a Windows runner and test the generated executable on a clean Windows account.
4. Scan dependencies and the packaged artifact; sign the executable if required by the distribution channel.
5. Complete legal review before any public commercial launch.
