from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable


class LocalJobDispatcher:
    def __init__(self, runner: Callable[[str], Awaitable[None]], concurrency: int = 1) -> None:
        self._semaphore = asyncio.Semaphore(max(1, concurrency))
        self._runner = runner

    async def dispatch_analysis(self, job_id: str) -> None:
        asyncio.create_task(self._execute(job_id))

    async def _execute(self, job_id: str) -> None:
        async with self._semaphore:
            await self._runner(job_id)
