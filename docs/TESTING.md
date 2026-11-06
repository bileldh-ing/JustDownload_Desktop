# Testing

## Run tests

```bash
python -m unittest discover -s tests -v
```

## Included coverage

- Unsafe URL scheme rejection.
- Loopback and private IPv6 destination rejection.
- Credential-bearing URL rejection.
- Non-standard port rejection.
- Filename sanitation and Windows reserved device names.
- Integration test that synthesizes an audio fixture with FFmpeg, converts it to MP3, and verifies the resulting audio codec using FFprobe.

## Manual desktop acceptance test

1. Launch `python app.py` (or the packaged executable).
2. Confirm the tool-status panel detects FFmpeg and FFprobe.
3. Select a local, owned media file and confirm FFprobe-derived details appear.
4. Select MP3, M4A, WAV, MP4 (where available), or Original file.
5. Process the media and confirm progress is tied to FFmpeg output.
6. Confirm the job becomes ready only after FFprobe verifies the output.
7. Open the output and check its codec/container with `ffprobe -v error -show_streams`.
8. Test cancel, invalid URL, `localhost`, private IP, an unsupported website page, and an unreachable direct URL.
9. Repeat at small window sizes and using keyboard navigation.

The included automated suite does not claim full OS-level SSRF resistance, exhaustive Windows UI/E2E validation, or platform-provider compatibility.
