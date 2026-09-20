"""FastAPI router for MCP protocol endpoint.

This module provides HTTP endpoints for the MCP protocol, allowing
external MCP hosts to communicate with the Homebox MCP server over HTTP.

Uses the ToolExecutor service for centralized tool execution.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from loguru import logger

from homebox_companion import HomeboxClient, HomeboxGateway
from homebox_companion.mcp.executor import ToolExecutionContext, ToolExecutor
from homebox_companion.mcp.types import ToolPermission

from ..dependencies import get_client, get_executor, get_homebox_access, get_token, require_auth

router = APIRouter()


@router.get("/mcp/v1/tools", dependencies=[Depends(require_auth)])
async def list_mcp_tools(
    request: Request,
    executor: Annotated[ToolExecutor, Depends(get_executor)],
) -> JSONResponse:
    """List available MCP tools and their schemas.

    This endpoint is primarily for discovery and debugging.
    External MCP hosts typically use the MCP protocol directly.

    Returns:
        JSON object with tool names and their metadata.
        Legacy-mode tool parameters include the required body 'token' field.
    """
    if not request.app.state.settings.chat_enabled:
        return JSONResponse(status_code=503, content={"error": "Chat/MCP feature is disabled"})

    # API-key deployments never accept a caller-supplied credential.
    schemas = executor.get_tool_schemas(
        include_write=False,
        include_token=request.app.state.settings.auth_mode == "legacy",
    )

    # Convert to dict format for JSON response
    tools_dict = {
        schema["function"]["name"]: {
            "description": schema["function"]["description"],
            "parameters": schema["function"]["parameters"],
        }
        for schema in schemas
    }

    return JSONResponse(content={"tools": tools_dict})


@router.post("/mcp/v1/tools/{tool_name}")
async def execute_mcp_tool(
    tool_name: str,
    request: Request,
    executor: Annotated[ToolExecutor, Depends(get_executor)],
    client: Annotated[HomeboxClient, Depends(get_client)],
) -> JSONResponse:
    """Execute an MCP tool directly via HTTP.

    This is a convenience endpoint for testing and simple integrations.
    For full MCP protocol support with streaming, external hosts should
    use the stdio transport or connect via SSE.

    Args:
        tool_name: Name of the tool to execute
        request: FastAPI request containing JSON body with:
            - token: Homebox auth token (required in legacy mode)
            - Additional tool-specific parameters
        executor: Shared ToolExecutor instance

    Returns:
        JSON response with tool execution result
    """
    if not request.app.state.settings.chat_enabled:
        return JSONResponse(status_code=503, content={"error": "Chat/MCP feature is disabled"})

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse(status_code=400, content={"success": False, "error": "Invalid JSON body"})
    if not isinstance(body, dict):
        return JSONResponse(status_code=400, content={"success": False, "error": "JSON body must be an object"})

    # Extract token without mutating the input dict
    if request.app.state.settings.auth_mode == "api_key":
        token = await get_token(request, None)
    else:
        token = body.get("token")
    if not isinstance(token, str) or not token.strip():
        return JSONResponse(
            status_code=401,
            content={"success": False, "error": "Missing required token parameter"},
        )
    access = await get_homebox_access(request, token, request.headers.get("X-Group-Id"))
    gateway = HomeboxGateway(client, access)

    # Create tool arguments without the token
    tool_args = {k: v for k, v in body.items() if k != "token"}

    # Check if tool exists
    tool = executor.get_tool(tool_name)
    if not tool:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": f"Unknown tool: {tool_name}"},
        )

    # Only allow read-only tools via HTTP (write tools require approval flow)
    if tool.permission != ToolPermission.READ:
        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "error": "Write operations require approval via the chat interface",
            },
        )

    # Execute via ToolExecutor
    logger.debug(f"Executing MCP tool via HTTP: {tool_name}")
    result = await executor.execute(
        tool_name,
        tool_args,
        context=ToolExecutionContext.for_gateway(gateway),
    )

    if not result.success:
        return JSONResponse(status_code=400, content=result.to_dict())

    return JSONResponse(content=result.to_dict())


@router.get("/mcp/v1/health")
async def mcp_health(request: Request) -> dict[str, Any]:
    """Health check for MCP server.

    Returns:
        Status information about the MCP server
    """
    return {
        "status": "healthy" if request.app.state.settings.chat_enabled else "disabled",
        "chat_enabled": request.app.state.settings.chat_enabled,
        "version": "1.0.0",
    }
