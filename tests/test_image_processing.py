"""Image workers do not block the loop or bypass limits after disconnects."""

import asyncio
import threading

import pytest

from server.services import image_processing


@pytest.mark.asyncio
async def test_cancelled_request_holds_slot_until_worker_finishes(monkeypatch):
    monkeypatch.setattr(image_processing.os, "cpu_count", lambda: 1)
    monkeypatch.setattr(image_processing, "_loop", None)
    loop = asyncio.get_running_loop()
    entered = asyncio.Event()
    release = threading.Event()
    second_entered = asyncio.Event()

    def first():
        loop.call_soon_threadsafe(entered.set)
        assert release.wait(timeout=5)
        return 1

    def second():
        loop.call_soon_threadsafe(second_entered.set)
        return 2

    worker = asyncio.create_task(image_processing.run_image_processing(first))
    other = None
    try:
        await asyncio.wait_for(entered.wait(), timeout=2)
        worker.cancel()
        with pytest.raises(asyncio.CancelledError):
            await worker
        other = asyncio.create_task(image_processing.run_image_processing(second))
        # Advance the loop while the worker thread remains blocked.
        await asyncio.sleep(0)
        assert not second_entered.is_set()
        release.set()
        assert await asyncio.wait_for(other, timeout=2) == 2
    finally:
        release.set()
        await asyncio.gather(worker, *([other] if other else []), return_exceptions=True)
