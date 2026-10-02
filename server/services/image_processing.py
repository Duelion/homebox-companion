"""Bound CPU-heavy image work without blocking the server event loop."""

import asyncio
import os
from collections.abc import Callable

_semaphore: asyncio.Semaphore | None = None
_loop: asyncio.AbstractEventLoop | None = None


async def run_image_processing[T](operation: Callable[..., T], *args: object) -> T:
    """Share one compression budget per loop, including cancelled requests."""
    global _semaphore, _loop
    loop = asyncio.get_running_loop()
    if _loop is not loop or _semaphore is None:
        _loop = loop
        _semaphore = asyncio.Semaphore(os.cpu_count() or 4)
    semaphore = _semaphore
    await semaphore.acquire()
    task = asyncio.create_task(asyncio.to_thread(operation, *args))

    def completed(work: asyncio.Task[T]) -> None:
        semaphore.release()
        # A disconnected request may no longer be awaiting the worker.
        if not work.cancelled():
            work.exception()

    task.add_done_callback(completed)
    # Cancellation cannot stop a running thread. Keep its slot until completion.
    return await asyncio.shield(task)
