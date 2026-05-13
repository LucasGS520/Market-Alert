import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.infra.database import engine

T = TypeVar("T")


def run_async_task(coro_factory: Callable[[], Awaitable[T]]) -> T:
    async def _runner() -> T:
        try:
            return await coro_factory()
        finally:
            await engine.dispose()

    return asyncio.run(_runner())
