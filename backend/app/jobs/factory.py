from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.core.config import settings
from app.jobs.base import JobDispatcher
from app.jobs.local import LocalJobDispatcher


def get_job_dispatcher(runner: Callable[[str], Awaitable[None]]) -> JobDispatcher:
    if settings.kafka_enabled and settings.job_dispatcher == "kafka":
        from app.jobs.kafka import KafkaJobDispatcher

        return KafkaJobDispatcher()
    return LocalJobDispatcher(runner, concurrency=settings.local_job_concurrency)
