"""Concurrency contracts for approval execution and chat session operations."""

from __future__ import annotations

import asyncio
import json
from typing import Any, cast

import pytest
from fastapi import FastAPI, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from homebox_companion.chat.approvals import ApprovalService
from homebox_companion.chat.orchestrator import ChatOrchestrator
from homebox_companion.chat.session import ChatSession, PendingApproval
from homebox_companion.chat.stream import ChatEventType
from homebox_companion.chat.types import ChatMessage, ToolCall
from homebox_companion.core.config import Settings
from homebox_companion.mcp.executor import ToolExecutor
from homebox_companion.mcp.types import ToolResult
from server.api.chat import _claim_session, _SessionEventSourceResponse, clear_history


def _pending_session() -> ChatSession:
    session = ChatSession()
    session.add_message(ChatMessage(role="tool", content='{"status":"awaiting_approval"}', tool_call_id="call-1"))
    session.add_pending_approval(
        PendingApproval(id="approval-1", tool_name="create_tag", parameters={"name": "Fragile"}, tool_call_id="call-1")
    )
    return session


@pytest.mark.asyncio
async def test_approval_is_claimed_before_write_and_cannot_execute_twice(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _pending_session()
    executor = ToolExecutor()
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def execute(_name: str, _params: dict[str, object], _token: str) -> ToolResult:
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return ToolResult(success=True, data={"id": "tag-1"})

    monkeypatch.setattr(executor, "execute", execute)
    service = ApprovalService(session, executor)
    first = asyncio.create_task(service.execute("approval-1", "token"))
    await started.wait()
    assert session.list_pending_approvals() == []
    with pytest.raises(ValueError, match="not found or expired"):
        await service.execute("approval-1", "token")
    assert not service.reject("approval-1", "too late")
    release.set()
    result, _ = await first
    assert result.success and calls == 1
    assert json.loads(session.messages[0].content)["success"] is True


@pytest.mark.asyncio
async def test_cancelled_write_keeps_approval_consumed_and_marks_outcome_uncertain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _pending_session()
    executor = ToolExecutor()
    started = asyncio.Event()

    async def execute(_name: str, _params: dict[str, object], _token: str) -> ToolResult:
        started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    monkeypatch.setattr(executor, "execute", execute)
    service = ApprovalService(session, executor)
    task = asyncio.create_task(service.execute("approval-1", "token"))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert session.list_pending_approvals() == []
    assert "result is unknown" in json.loads(session.messages[0].content)["error"]
    with pytest.raises(ValueError, match="not found or expired"):
        await service.execute("approval-1", "token")


def test_busy_session_rejects_overlapping_operations() -> None:
    session = _pending_session()
    _claim_session(session, "message")
    for operation in ("message", "approve", "reject", "clear"):
        with pytest.raises(HTTPException) as exc:
            _claim_session(session, operation)
        assert exc.value.status_code == 409
    session.end_operation("message")
    _claim_session(session, "approve")
    session.end_operation("approve")


@pytest.mark.asyncio
async def test_cancelled_response_releases_claim_before_stream_starts(monkeypatch: pytest.MonkeyPatch) -> None:
    session = ChatSession()
    started = asyncio.Event()

    async def response_call(*_args: Any, **_kwargs: Any) -> None:
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(EventSourceResponse, "__call__", response_call)
    _claim_session(session, "message")

    async def events():
        yield {"data": "unused"}

    response = _SessionEventSourceResponse(content=events())
    response.session = session
    task = asyncio.create_task(response(cast(Any, {}), cast(Any, None), cast(Any, None)))
    await started.wait()
    with pytest.raises(HTTPException) as exc:
        _claim_session(session, "clear")
    assert exc.value.status_code == 409
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    _claim_session(session, "clear")
    session.end_operation("clear")


@pytest.mark.asyncio
async def test_orchestrator_uses_injected_chat_setting() -> None:
    session = ChatSession()
    orchestrator = ChatOrchestrator(
        session=session,
        executor=ToolExecutor(),
        app_settings=Settings(_env_file=None, chat_enabled=False),
    )
    events = [event async for event in orchestrator.process_message("hello", "token")]
    assert len(events) == 1 and events[0].type == ChatEventType.ERROR
    assert session.messages == []


@pytest.mark.asyncio
async def test_cancelled_read_stream_keeps_matching_tool_result(monkeypatch: pytest.MonkeyPatch) -> None:
    session = ChatSession()
    executor = ToolExecutor()
    monkeypatch.setattr(executor, "get_tool", lambda _name: object())
    monkeypatch.setattr(executor, "requires_approval", lambda _name: False)
    orchestrator = ChatOrchestrator(session=session, executor=executor)
    stream = orchestrator._handle_tool_calls("", [ToolCall(id="call-1", name="read_tool", arguments={})], "", [])

    assert (await anext(stream)).type == ChatEventType.TOOL_START
    await stream.aclose()

    history = session.get_history()
    assert len(history) == 2
    assert history[0]["tool_calls"][0]["id"] == history[1]["tool_call_id"]
    assert "interrupted" in json.loads(history[1]["content"])["error"]


@pytest.mark.asyncio
async def test_display_info_failure_keeps_matching_tool_result(monkeypatch: pytest.MonkeyPatch) -> None:
    session = ChatSession()
    executor = ToolExecutor()
    monkeypatch.setattr(executor, "get_tool", lambda _name: object())
    monkeypatch.setattr(executor, "requires_approval", lambda _name: True)

    async def fail_display_info(_name: str, _params: dict[str, object], _token: str) -> None:
        raise RuntimeError("display lookup failed")

    monkeypatch.setattr(executor, "get_display_info", fail_display_info)
    orchestrator = ChatOrchestrator(session=session, executor=executor)
    stream = orchestrator._handle_tool_calls("", [ToolCall(id="call-1", name="write_tool", arguments={})], "", [])

    with pytest.raises(RuntimeError, match="display lookup failed"):
        _ = [event async for event in stream]

    history = session.get_history()
    assert len(history) == 2
    assert history[0]["tool_calls"][0]["id"] == history[1]["tool_call_id"]
    assert "interrupted" in json.loads(history[1]["content"])["error"]
    assert session.pending_approvals == {}


@pytest.mark.asyncio
async def test_clear_rejects_busy_session_then_resets_same_session() -> None:
    app = FastAPI()
    app.state.settings = Settings(_env_file=None, chat_enabled=True, demo_mode=False)
    request = Request({"type": "http", "app": app})
    session = _pending_session()
    old_id = session.session_id
    _claim_session(session, "approve")
    with pytest.raises(HTTPException) as exc:
        await clear_history(request, session)
    assert exc.value.status_code == 409
    assert session.pending_approvals
    session.end_operation("approve")
    result = await clear_history(request, session)
    assert result.success
    assert session.session_id != old_id
    assert session.messages == [] and session.pending_approvals == {}
