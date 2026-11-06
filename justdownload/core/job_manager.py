from __future__ import annotations

import queue
import threading
import uuid
from dataclasses import dataclass
from typing import Callable

from justdownload.media.pipeline import JobEvent, JobRequest, process_job


@dataclass
class _QueuedJob:
    job_id: str
    request: JobRequest
    cancel_event: threading.Event


class JobManager:
    """Single-worker local queue; media work never blocks the UI thread."""

    def __init__(self, callback: Callable[[JobEvent], None]):
        self.callback = callback
        self._queue: queue.Queue[_QueuedJob | None] = queue.Queue()
        self._lock = threading.Lock()
        self._active: _QueuedJob | None = None
        self._thread = threading.Thread(target=self._run, name="JustDownloadWorker", daemon=True)
        self._thread.start()

    def submit(self, request: JobRequest) -> str:
        job_id = uuid.uuid4().hex
        job = _QueuedJob(job_id, request, threading.Event())
        with self._lock:
            if self._active is not None:
                raise RuntimeError("A job is already running. Wait for it to finish or cancel it first.")
            self._active = job
        self._queue.put(job)
        self.callback(JobEvent(job_id, "queued", "Queued", "Your job is queued on this computer…"))
        return job_id

    def cancel(self) -> None:
        with self._lock:
            if self._active:
                self._active.cancel_event.set()

    def is_busy(self) -> bool:
        with self._lock:
            return self._active is not None

    def _run(self) -> None:
        while True:
            job = self._queue.get()
            if job is None:
                self._queue.task_done()
                break
            try:
                process_job(job.request, job.cancel_event, self.callback, job.job_id)
            except Exception:
                pass
            finally:
                with self._lock:
                    if self._active and self._active.job_id == job.job_id:
                        self._active = None
                self._queue.task_done()

    def shutdown(self) -> None:
        self.cancel()
        self._queue.put(None)
