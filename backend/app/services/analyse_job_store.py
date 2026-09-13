"""Stockage mémoire des jobs d'analyse scoring (TTL, SSE, index par dossier)."""
from __future__ import annotations

import asyncio
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque

from app.config import DIRECT_FINANCIAL_JOB_TTL_MINUTES
from app.schemas.analyse import AnalyseJobProgress, JobStatus, ScoringAnalysisResult


@dataclass
class ScoringJob:
    job_id: str
    dossier_id: str
    status: JobStatus = "queued"
    progress_pct: int = 0
    current_step: str = "queued"
    current_page: int | None = None
    pages_total: int | None = None
    pages_financial: int = 0
    pages_skipped: int = 0
    pages_failed: int = 0
    message: str = ""
    error: str | None = None
    result: ScoringAnalysisResult | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    events: Deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=500))
    subscribers: list[asyncio.Queue] = field(default_factory=list)
    pdf_bytes: bytes | None = None
    filename: str = "document.pdf"
    max_pages: int | None = None
    extra_pdfs: list[tuple[bytes, str]] = field(default_factory=list)


class ScoringJobStore:
    def __init__(self, *, ttl_minutes: int | None = None) -> None:
        self._ttl = (ttl_minutes or DIRECT_FINANCIAL_JOB_TTL_MINUTES) * 60
        self._jobs: dict[str, ScoringJob] = {}
        self._by_dossier: dict[str, str] = {}
        self._lock = threading.RLock()

    def create(
        self,
        *,
        dossier_id: str,
        pdf_bytes: bytes,
        filename: str,
        max_pages: int | None = None,
        extra_pdfs: list[tuple[bytes, str]] | None = None,
    ) -> ScoringJob:
        self.cleanup()
        job_id = uuid.uuid4().hex
        job = ScoringJob(
            job_id=job_id,
            dossier_id=dossier_id,
            pdf_bytes=pdf_bytes,
            filename=filename,
            max_pages=max_pages,
            extra_pdfs=list(extra_pdfs or []),
            message="Job en file d'attente",
        )
        with self._lock:
            previous = self._by_dossier.get(dossier_id)
            if previous and previous in self._jobs:
                old = self._jobs[previous]
                if old.status in {"queued", "processing"}:
                    return old
            self._jobs[job_id] = job
            self._by_dossier[dossier_id] = job_id
        return job

    def get(self, job_id: str) -> ScoringJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if time.time() - job.updated_at > self._ttl:
                del self._jobs[job_id]
                return None
            return job

    def get_for_dossier(self, dossier_id: str) -> ScoringJob | None:
        with self._lock:
            job_id = self._by_dossier.get(dossier_id)
        if not job_id:
            return None
        return self.get(job_id)

    def update(self, job_id: str, **kwargs: Any) -> ScoringJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            for key, value in kwargs.items():
                if hasattr(job, key):
                    setattr(job, key, value)
            job.updated_at = time.time()
            return job

    def emit(self, job_id: str, event_type: str, data: dict[str, Any] | None = None) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            event = {
                "event": event_type,
                "job_id": job_id,
                "dossier_id": job.dossier_id,
                "ts": time.time(),
                "status": job.status,
                "progress_pct": job.progress_pct,
                "current_step": job.current_step,
                "current_page": job.current_page,
                "pages_total": job.pages_total,
                "pages_financial": job.pages_financial,
                "pages_skipped": job.pages_skipped,
                "pages_failed": job.pages_failed,
                "message": job.message,
                "error": job.error,
                **(data or {}),
            }
            job.events.append(event)
            job.updated_at = time.time()
            subscribers = list(job.subscribers)
        for queue in subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def subscribe(self, job_id: str) -> asyncio.Queue | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            queue: asyncio.Queue = asyncio.Queue(maxsize=200)
            for event in list(job.events):
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    break
            job.subscribers.append(queue)
            return queue

    def unsubscribe(self, job_id: str, queue: asyncio.Queue) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            if queue in job.subscribers:
                job.subscribers.remove(queue)

    def to_progress(self, job: ScoringJob) -> AnalyseJobProgress:
        return AnalyseJobProgress(
            job_id=job.job_id,
            dossier_id=job.dossier_id,
            status=job.status,
            progress_pct=job.progress_pct,
            current_step=job.current_step,
            current_page=job.current_page,
            pages_total=job.pages_total,
            pages_financial=job.pages_financial,
            pages_skipped=job.pages_skipped,
            pages_failed=job.pages_failed,
            message=job.message,
            error=job.error,
            stream_url=f"/api/v1/analyse/jobs/{job.job_id}/stream",
            result_url=f"/api/v1/analyse/jobs/{job.job_id}/result",
            filename=job.filename,
        )

    def cleanup(self) -> None:
        now = time.time()
        with self._lock:
            expired = [
                jid
                for jid, job in self._jobs.items()
                if now - job.updated_at > self._ttl
            ]
            for jid in expired:
                job = self._jobs.pop(jid, None)
                if job and self._by_dossier.get(job.dossier_id) == jid:
                    del self._by_dossier[job.dossier_id]


job_store = ScoringJobStore()
