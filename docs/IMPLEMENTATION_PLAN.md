# Implementation plan — JustDownload Desktop

## Repository audit

The provided source is a product master prompt, not an existing application repository. It specifies a Next.js/FastAPI/PostgreSQL/Redis/Celery web product. There were no existing application source files, package manifests, dependency lockfiles, tests, or deployment assets to preserve. This implementation therefore adapts the product scope to a native desktop application rather than attempting to reuse a nonexistent web repository.

## Desktop architecture decisions

- **UI:** Python Tkinter, which is included with standard desktop Python distributions. This removes the browser runtime and does not start a local HTTP server.
- **Execution model:** a single background worker thread and queue. Network operations and media subprocesses never run on the Tkinter event loop.
- **Media tools:** FFmpeg and FFprobe via argument arrays with `shell=False` behavior (Python subprocess default). They are detected in `PATH` or the optional `vendor/ffmpeg/` folder.
- **Persistence:** no database is required for a local single-user workflow. Temporary workspaces are created per job and removed in `finally` cleanup.
- **Remote source support:** direct HTTP(S) media file URLs only. The application does not scrape website pages or invoke platform extractors.
- **Progress:** download metrics use actual response bytes and elapsed time; FFmpeg progress is parsed from its machine-readable progress output. Progress is indeterminate when a meaningful percentage is unavailable.
- **Output finalization:** FFprobe verifies the produced file before it is atomically moved into the destination folder. A SHA-256 checksum is calculated for the result.

## Milestones

| Milestone | Acceptance criteria | Status |
|---|---|---|
| Desktop UI and product identity | Branded, responsive-to-window-size native desktop interface | Implemented |
| Local inspection | FFprobe reads file streams and metadata | Implemented |
| Direct URL inspection | Safe HTTP(S) header inspection, no full download on paste | Implemented |
| Real media pipeline | Direct fetch/local input, FFmpeg conversion, FFprobe verification | Implemented; integration test included |
| Job management | Background processing, state updates, cancel request, cleanup | Implemented for one active job |
| Windows packaging | Reproducible PyInstaller build and CI workflow | Build recipe provided; Windows runner required |
| Security hardening | URL policy, safe paths, bounded downloads and subprocess arguments | Baseline implemented; limitations documented |

## Risks and assumptions

1. **Windows binary:** the authoring environment for this deliverable is Linux. PyInstaller does not cross-compile a Windows PE executable from Linux, so the project includes a one-file Windows build script and a Windows GitHub Actions workflow rather than fabricating an `.exe`.
2. **FFmpeg distribution:** FFmpeg is not bundled by default. The exact build configuration and its license obligations must be checked before bundling or redistribution.
3. **Direct URL compatibility:** some hosts block HEAD/range requests, require credentials, serve playlists/manifests, or use expiring URLs. These are intentionally not bypassed.
4. **Network security:** the client validates DNS answers and redirect destinations but is not a sandbox. OS firewall rules are recommended where the app handles untrusted URLs.
5. **Resource budgets:** the default remote input cap is 2 GiB; conversion is limited to one active job and one hour per FFmpeg process.

## Next engineering milestone

Run the Windows workflow on a Windows runner, install/test FFmpeg on Windows, add a signed installer if required, and perform UI/E2E validation on the supported Windows versions. Before public deployment, complete the legal review called for in the supplied product brief.
