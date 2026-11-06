# Architecture

```text
┌──────────────────────────────────────────────────────────┐
│                  Tkinter desktop interface               │
│   URL input · local file picker · output choices · jobs  │
└──────────────────────────────┬───────────────────────────┘
                               │ typed JobRequest / events
┌──────────────────────────────▼───────────────────────────┐
│                       JobManager                          │
│               one background worker + queue               │
└──────────────────────────────┬───────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────┐
│                    Media pipeline                         │
│  source acquisition → FFprobe → FFmpeg → FFprobe → save  │
└──────────────┬───────────────────────────────┬───────────┘
               │                               │
┌──────────────▼──────────┐       ┌────────────▼───────────┐
│ Direct URL adapter      │       │ Local filesystem       │
│ URL + DNS policy        │       │ User-selected media    │
│ redirect validation     │       │ and output directory   │
└─────────────────────────┘       └────────────────────────┘
```

## Boundaries

- `ui/`: view state and user interaction only. Worker callbacks are marshalled through a thread-safe queue before touching Tk widgets.
- `core/job_manager.py`: serializes media work and coordinates cancellation.
- `core/url_guard.py`: validates direct remote URLs and public DNS destinations.
- `media/remote.py`: inspects HTTP headers and streams the direct media response to a bounded temporary file.
- `media/probe.py`: reads actual stream/container details with FFprobe.
- `media/pipeline.py`: builds fixed FFmpeg argument lists, consumes real progress events, validates output, hashes the finalized artifact and cleans temporary workspaces.

No user-supplied string is used as a shell command or FFmpeg flag. A requested output profile maps to a small application-owned command template.
