"""FastAPI router for chat API endpoints.

This module provides SSE streaming chat endpoints and approval management
for the conversational assistant.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel, ValidationError
from sse_starlette.sse import EventSourceResponse

from homebox_companion import HomeboxClient, settings
from homebox_companion.chat.orchestrator import ChatOrchestrator, generate_confirmation_message
from homebox_companion.chat.session import (
    clear_session,
    get_session,
)
from homebox_companion.mcp.tools import get_tools

from ..dependencies import get_client, get_token

router = APIRouter()

# Discover tools once at module load for approval execution
_all_tools = get_tools()
_tools_by_name = {t.name: t for t in _all_tools}


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
    import json

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
    client: Annotated[HomeboxClient, Depends(get_client)],
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
        client: Homebox client

    Returns:
        EventSourceResponse with streaming events
    """
    if not settings.chat_enabled:
        raise HTTPException(status_code=503, detail="Chat feature is disabled")

    # TRACE: Log incoming chat message
    logger.trace(f"[API] Incoming chat message: {request.message}")

    session = get_session(token)
    orchestrator = ChatOrchestrator(client, session)

    return EventSourceResponse(
        _event_generator(orchestrator, request.message, token),
        media_type="text/event-stream",
    )


@router.get("/chat/pending")
async def list_pending_approvals(
    token: Annotated[str, Depends(get_token)],
) -> dict[str, Any]:
    """List pending approval requests for this session.

    Returns:
        Dict with 'approvals' list containing pending approval objects
    """
    if not settings.chat_enabled:
        raise HTTPException(status_code=503, detail="Chat feature is disabled")

    session = get_session(token)
    approvals = session.list_pending_approvals()

    return {
        "approvals": [a.to_dict() for a in approvals],
    }


@router.post("/chat/approve/{approval_id}")
async def approve_action(
    approval_id: str,
    token: Annotated[str, Depends(get_token)],
    client: Annotated[HomeboxClient, Depends(get_client)],
    body: ApproveRequest | None = None,
) -> JSONResponse:
    """Approve a pending action and execute it.

    Args:
        approval_id: ID of the approval to approve
        token: Auth token
        client: Homebox client
        body: Optional request body with modified parameters

    Returns:
        Result of the action execution
    """
    if not settings.chat_enabled:
        raise HTTPException(status_code=503, detail="Chat feature is disabled")

    session = get_session(token)
    approval = session.get_pending_approval(approval_id)

    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found or expired")

    # Find the tool_call_id for this approval so we can update the history
    tool_call_id = session.get_tool_call_id_for_approval(approval_id)

    # Get tool by name
    tool = _tools_by_name.get(approval.tool_name)

    if not tool:
        session.remove_approval(approval_id)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Tool not found: {approval.tool_name}",
            }
        )

    # Merge user-modified parameters with original approval parameters
    final_params = {**approval.parameters}
    if body and body.parameters:
        final_params.update(body.parameters)
        logger.info(f"User modified parameters for {approval.tool_name}: {body.parameters}")

    try:
        logger.info(
            f"Executing approved action: {approval.tool_name} "
            f"with params {final_params}"
        )
        # Validate parameters with Pydantic
        params = tool.Params(**final_params)
        result = await tool.execute(client, token, params)

        # Update the session history to replace the stale "pending_approval" message
        # with the actual tool result. This ensures the LLM has correct context.
        if tool_call_id:
            result_message = {
                "success": result.success,
                "data": result.data,
                "error": result.error,
                "message": f"Action '{approval.tool_name}' executed successfully."
                if result.success
                else f"Action '{approval.tool_name}' failed: {result.error}",
            }
            session.update_tool_message(tool_call_id, json.dumps(result_message))

        session.remove_approval(approval_id)

        # Generate confirmation message (no orchestrator needed - uses standalone function)
        confirmation = generate_confirmation_message(
            tool_name=approval.tool_name,
            success=result.success,
            data=result.data,
            error=result.error,
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

    except ValidationError as e:
        session.remove_approval(approval_id)
        confirmation = generate_confirmation_message(
            tool_name=approval.tool_name,
            success=False,
            data=None,
            error=f"Invalid parameters: {e}",
        )
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": f"Invalid parameters: {e}",
                "tool": approval.tool_name,
                "confirmation": confirmation,
            }
        )
    except Exception as e:
        logger.exception(f"Approved action execution failed: {approval.tool_name}")
        session.remove_approval(approval_id)
        confirmation = generate_confirmation_message(
            tool_name=approval.tool_name,
            success=False,
            data=None,
            error=str(e),
        )
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "tool": approval.tool_name,
                "confirmation": confirmation,
            }
        )


@router.post("/chat/reject/{approval_id}")
async def reject_action(
    approval_id: str,
    token: Annotated[str, Depends(get_token)],
) -> ApprovalResponse:
    """Reject a pending action.

    Args:
        approval_id: ID of the approval to reject
        token: Auth token

    Returns:
        Success status
    """
    if not settings.chat_enabled:
        raise HTTPException(status_code=503, detail="Chat feature is disabled")

    session = get_session(token)
    approval = session.get_pending_approval(approval_id)

    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found or expired")

    session.remove_approval(approval_id)
    logger.info(f"User rejected approval {approval_id} for tool {approval.tool_name}")

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

    clear_session(token)
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
