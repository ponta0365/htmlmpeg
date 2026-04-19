"""Job lifecycle management."""

from __future__ import annotations

import threading
from datetime import datetime
from itertools import count

from .models import Job


class JobManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._counter = count(1)

    def create_job(self, job_type: str) -> Job:
        with self._lock:
            job_id = f"job-{next(self._counter):05d}"
            job = Job(job_id=job_id, type=job_type, state="queued")
            self._jobs[job_id] = job
            return job

    def get_job(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update_state(self, job_id: str, state: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.state = state
            if state == "running" and job.started_at is None:
                job.started_at = datetime.now()
            if state in {"completed", "failed", "stopped"}:
                job.finished_at = datetime.now()

    def append_log(self, job_id: str, message: str) -> None:
        with self._lock:
            self._jobs[job_id].logs.append(message)
