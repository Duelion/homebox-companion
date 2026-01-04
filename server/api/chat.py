"""FastAPI router for chat API endpoints.

This module provides SSE streaming chat endpoints and approval management
for the conversational assistant.

Uses the refactored service architecture:
- ChatOrchestrator: Thin facade for chat flow
- ToolExecutor: Centralized tool execution
- ChatSession: Pure state management
- ApprovalService: Approval lifecycle handling
- SessionStoreProtocol: Pluggable session storage
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from homebox_companion import settings
from homebox_companion.chat.approvals import ApprovalService
from homebox_companion.chat.orchestrator import ChatOrchestrator
from homebox_companion.chat.session import ChatSession
from homebox_companion.chat.stream import StreamEmitter
from homebox_companion.mcp.executor import ToolExecutor

from ..dependencies import get_executor, get_session, get_token, session_store_holder

router = APIRouter()


class ChatMessageRequest(BaseModel):
    """Request body for sending a chat message."""

    message: str


class ApprovalResponse(BaseModel):
    """Response for approval actions."""

    success: bool
    message: str | None = None


class ApproveRequest(BaseModel):
    """Optional request body for approve action with modified parameters."""

    parameters: dict[str, Any] | None = None


async def _event_generator(
    orchestrator: ChatOrchestrator,
    user_message: str,
    token: str,
):
    """Generate SSE events from orchestrator.

    Args:
        orchestrator: The chat orchestrator
        user_message: User's message content
        token: Auth token

    Yields:
        SSE formatted events
    """
    try:
        async for event in orchestrator.process_message(user_message, token):
            # sse_starlette expects data as a string - must JSON-serialize dicts
            yield {
                "event": event.type.value,
                "data": json.dumps(event.data),
            }
    except Exception as e:
        logger.exception("Event generation failed")
        yield {
            "event": "error",
            "data": json.dumps({"message": str(e)}),
        }
        yield {
            "event": "done",
            "data": json.dumps({}),
        }


@router.post("/chat/messages")
async def send_message(
    request: ChatMessageRequest,
    token: Annotated[str, Depends(get_token)],
    session: Annotated[ChatSession, Depends(get_session)],
    executor: Annotated[ToolExecutor, Depends(get_executor)],
) -> EventSourceResponse:
    """Send a message and receive SSE stream of events.

    The response is a Server-Sent Events stream with the following event types:
    - text: Streaming text chunk {"content": string}
    - tool_start: Tool execution started {"tool": string, "params": object}
    - tool_result: Tool result {"tool": string, "result": object}
    - approval_required: Write action needs approval
        {"id": string, "tool": string, "params": object}
    - error: Error occurred {"message": string}
    - done: Stream complete {}

    Args:
        request: The chat message request
        token: Auth token from header
        session: Chat session for this user
        executor: Shared ToolExecutor instance

    Returns:
        EventSourceResponse with streaming events
    """
    if not settings.chat_enabled:
        raise HTTPException(status_code=503, detail="Chat feature is disabled")

    # TRACE: Log incoming chat message
    logger.trace(f"[API] Incoming chat message: {request.message}")

    # Create orchestrator with injected dependencies
    orchestrator = ChatOrchestrator(session=session, executor=executor)

    return EventSourceResponse(
        _event_generator(orchestrator, request.message, token),
        media_type="text/event-stream",
    )


@router.get("/chat/pending")
async def list_pending_approvals(
    session: Annotated[ChatSession, Depends(get_session)],
) -> dict[str, Any]:
    """List pending approval requests for this session.

    Returns:
        Dict with 'approvals' list containing pending approval objects
    """
    if not settings.chat_enabled:
        raise HTTPException(status_code=503, detail="Chat feature is disabled")

    approvals = session.list_pending_approvals()

    return {
        "approvals": [a.to_dict() for a in approvals],
    }


@router.post("/chat/approve/{approval_id}")
async def approve_action(
    approval_id: str,
    token: Annotated[str, Depends(get_token)],
    session: Annotated[ChatSession, Depends(get_session)],
    executor: Annotated[ToolExecutor, Depends(get_executor)],
    body: ApproveRequest | None = None,
) -> JSONResponse:
    """Approve a pending action and execute it.

    Uses ApprovalService which handles:
    - Approval validation
    - Parameter merging
    - Tool execution via ToolExecutor
    - History update
    - Approval cleanup

    Args:
        approval_id: ID of the approval to approve
        token: Auth token
        session: Chat session for this user
        executor: Shared ToolExecutor instance
        body: Optional request body with modified parameters

    Returns:
        Result of the action execution
    """
    if not settings.chat_enabled:
        raise HTTPException(status_code=503, detail="Chat feature is disabled")

    # Create approval service with injected executor
    approval_service = ApprovalService(session, executor)

    # Get modified params if provided
    modified_params = body.parameters if body and body.parameters else None

    try:
        # Use approval service for atomic execution (validates approval internally)
        result, approval = await approval_service.execute(
            approval_id=approval_id,
            token=token,
            modified_params=modified_params,
        )

        # Generate confirmation message
        confirmation = StreamEmitter.confirmation_message(
            tool_name=approval.tool_name,
            success=result.success,
            data=result.data,
            error=result.error,
            display_info=approval.display_info,
        )

        return JSONResponse(
            content={
                "success": result.success,
                "tool": approval.tool_name,
                "data": result.data,
                "error": result.error,
                "confirmation": confirmation,
            }
        )

    except ValueError as e:
        # Approval not found or expired
        raise HTTPException(status_code=404, detail=str(e)) from e

    except Exception as e:
        logger.exception(f"Approved action execution failed: {approval_id}")
        # Remove approval on failure (may already be removed if execute partially succeeded)
        session.remove_approval(approval_id)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "tool": None,
                "confirmation": f"✗ Action failed: {e}",
            },
        )


@router.post("/chat/reject/{approval_id}")
async def reject_action(
    approval_id: str,
    session: Annotated[ChatSession, Depends(get_session)],
) -> ApprovalResponse:
    """Reject a pending action.

    Args:
        approval_id: ID of the approval to reject
        session: Chat session for this user

    Returns:
        Success status
    """
    if not settings.chat_enabled:
        raise HTTPException(status_code=503, detail="Chat feature is disabled")

    # Use the session's reject_approval method which handles history update
    if not session.reject_approval(approval_id, "user rejected"):
        raise HTTPException(status_code=404, detail="Approval not found or expired")

    return ApprovalResponse(success=True, message="Action rejected")


@router.delete("/chat/history")
async def clear_history(
    token: Annotated[str, Depends(get_token)],
) -> ApprovalResponse:
    """Clear conversation history for this session.

    Returns:
        Success status
    """
    if not settings.chat_enabled:
        raise HTTPException(status_code=503, detail="Chat feature is disabled")

    session_store_holder.get().delete(token)
    return ApprovalResponse(success=True, message="History cleared")


@router.get("/chat/health")
async def chat_health() -> dict[str, Any]:
    """Health check for chat API.

    Returns:
        Status information about the chat service
    """
    return {
        "status": "healthy" if settings.chat_enabled else "disabled",
        "chat_enabled": settings.chat_enabled,
        "max_history": settings.chat_max_history,
        "approval_timeout_seconds": settings.chat_approval_timeout,
    }
