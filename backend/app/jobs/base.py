from __future__ import annotations

from typing import Protocol


class JobDispatcher(Protocol):
    async def dispatch_analysis(self, job_id: str) -> None:
        ...
