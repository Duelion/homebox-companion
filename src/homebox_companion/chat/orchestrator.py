"""Chat orchestrator - thin facade for LLM interactions with tool calling.

This module provides the orchestration layer that coordinates:
- LLM communication via LLMClient
- Tool execution via ToolExecutor
- Session state via ChatSession
- Event generation via StreamEmitter

The orchestrator is intentionally thin - it delegates to focused
components rather than implementing logic directly.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from ..core.config import settings
from ..mcp.executor import ToolExecutor
from .llm_client import LLMClient, TokenUsage
from .session import ChatSession, PendingApproval, create_approval_id
from .stream import ChatEvent, StreamEmitter
from .types import ChatMessage, ToolCall

# Maximum recursion depth for tool call continuations
# Prevents infinite loops if LLM keeps making tool calls
MAX_TOOL_RECURSION_DEPTH = 10


# =============================================================================
# HELPER DATA CLASSES
# =============================================================================


@dataclass
class ToolExecution:
    """Result of a single tool execution with timing info.

    Used internally by the orchestrator to collect parallel execution results
    and process them in order.
    """

    tc: ToolCall
    result: Any  # ToolResult, but using Any to avoid import in dataclass
    elapsed_ms: float


# =============================================================================
# STREAM TOOL CALL ACCUMULATOR
# =============================================================================


@dataclass
class ToolCallAccumulator:
    """Accumulates streaming tool call chunks into complete ToolCall objects.

    LLM streaming responses deliver tool calls in fragments across multiple
    chunks. This class collects those fragments and reconstructs complete
    ToolCall objects when the stream ends.

    Example:
        >>> accumulator = ToolCallAccumulator()
        >>> for chunk in stream:
        ...     if chunk.tool_calls:
        ...         for tc_delta in chunk.tool_calls:
        ...             accumulator.add_chunk(tc_delta)
        >>> tool_calls = accumulator.build()
    """

    _chunks: dict[int, dict[str, str]] = field(default_factory=dict)

    def add_chunk(self, tc_delta: Any) -> None:
        """Add a streaming tool call chunk.

        Args:
            tc_delta: The delta chunk from the stream (has index, id, function attrs).
        """
        idx = tc_delta.index
        if idx not in self._chunks:
            self._chunks[idx] = {"id": "", "name": "", "arguments": ""}

        if tc_delta.id:
            self._chunks[idx]["id"] = tc_delta.id
        if tc_delta.function and tc_delta.function.name:
            self._chunks[idx]["name"] = tc_delta.function.name
        if tc_delta.function and tc_delta.function.arguments:
            self._chunks[idx]["arguments"] += tc_delta.function.arguments

    def add_complete(self, idx: int, tc: Any) -> None:
        """Add a complete tool call (for non-incremental streaming).

        Args:
            idx: Index of the tool call.
            tc: Complete tool call object from non-streaming response.
        """
        if idx not in self._chunks:
            self._chunks[idx] = {
                "id": getattr(tc, "id", ""),
                "name": (
                    tc.function.name
                    if hasattr(tc, "function") and tc.function
                    else ""
                ),
                "arguments": (
                    tc.function.arguments
                    if hasattr(tc, "function") and tc.function
                    else ""
                ),
            }

    def build(self) -> list[ToolCall]:
        """Build complete ToolCall objects from accumulated chunks.

        Returns:
            List of ToolCall objects (reusing the Pydantic model from session).
        """
        if not self._chunks:
            return []

        tool_calls = []
        for idx in sorted(self._chunks.keys()):
            tc_data = self._chunks[idx]
            if not tc_data["id"] or not tc_data["name"]:
                logger.warning(
                    f"[CHAT] Skipping incomplete tool call: id={tc_data['id']}, "
                    f"name={tc_data['name']}"
                )
                continue

            # Parse arguments JSON into dict
            try:
                args = json.loads(tc_data["arguments"]) if tc_data["arguments"] else {}
            except json.JSONDecodeError as e:
                logger.warning(
                    f"[CHAT] Failed to parse tool arguments for {tc_data['name']}: {e}"
                )
                args = {}

            tool_calls.append(
                ToolCall(id=tc_data["id"], name=tc_data["name"], arguments=args)
            )

        for tc in tool_calls:
            logger.trace(f"[CHAT] Tool call: {tc.name}({tc.arguments})")

        return tool_calls


# =============================================================================
# ORCHESTRATOR
# =============================================================================


class ChatOrchestrator:
    """Coordinates chat flow between LLM, tools, and session.

    This class is a thin facade that delegates to focused components:
    - LLMClient: LLM communication
    - ToolExecutor: Tool discovery and execution
    - ChatSession: State management
    - StreamEmitter: Event generation

    The orchestrator handles:
    - User message processing
    - LLM response streaming
    - Tool call routing (auto-execute READ, queue WRITE for approval)
    - Recursive tool call handling

    Example:
        >>> orchestrator = ChatOrchestrator(session, executor, llm, emitter)
        >>> async for event in orchestrator.process_message("List items", token):
        ...     yield event.to_sse()
    """

    def __init__(
        self,
        session: ChatSession,
        executor: ToolExecutor,
        llm: LLMClient | None = None,
        emitter: StreamEmitter | None = None,
    ):
        """Initialize the orchestrator with required components.

        Args:
            session: ChatSession for conversation state.
            executor: ToolExecutor for tool discovery and execution.
            llm: LLMClient for LLM calls. Created if not provided.
            emitter: StreamEmitter for event generation. Created if not provided.
        """
        self._session = session
        self._executor = executor
        self._llm = llm or LLMClient()
        self._emitter = emitter or StreamEmitter()

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    async def process_message(
        self,
        user_message: str,
        token: str,
    ) -> AsyncGenerator[ChatEvent, None]:
        """Process a user message and yield streaming events.

        This is the main entry point for chat interactions. It:
        1. Adds the user message to history
        2. Auto-rejects any pending approvals (superseded)
        3. Calls the LLM with streaming
        4. Handles tool calls (auto-execute READ, queue WRITE)
        5. Yields SSE events throughout

        Args:
            user_message: The user's message content.
            token: Homebox auth token for tool execution.

        Yields:
            ChatEvent objects for SSE streaming.
        """
        if not settings.chat_enabled:
            yield self._emitter.error("Chat feature is disabled")
            return

        # TRACE: Log the start of a new conversation turn
        logger.trace("[CHAT] === NEW MESSAGE ===")
        logger.trace(f"[CHAT] User message:\n{user_message}")
        logger.trace(
            f"[CHAT] Session state: {len(self._session.messages)} messages in history"
        )

        # Add user message to history
        self._session.add_message(ChatMessage(role="user", content=user_message))

        # Auto-reject any pending approvals - user's new message supersedes them
        rejected_count = self._session.auto_reject_all_pending(
            "superseded by new message"
        )
        if rejected_count:
            logger.debug(f"[CHAT] Auto-rejected {rejected_count} pending approvals")

        # Build messages for LLM
        system_prompt = self._llm.get_system_prompt()
        messages = [{"role": "system", "content": system_prompt}]

        # Get conversation history
        history = self._session.get_history()
        messages.extend(history)

        # TRACE: Log conversation context
        logger.trace(f"[CHAT] Sending {len(history)} history messages to LLM")

        # Get tool schemas
        tools = self._executor.get_tool_schemas(include_write=True)

        # Call LLM with streaming
        try:
            stream = self._llm.complete_stream(messages, tools)
            async for event in self._handle_stream(stream, token, tools):
                yield event
        except Exception as e:
            logger.exception("LLM call failed")
            yield self._emitter.error(f"LLM error: {str(e)}")
            yield self._emitter.done()
            return

        yield self._emitter.done()

    # =========================================================================
    # STREAM HANDLING
    # =========================================================================

    async def _handle_stream(
        self,
        stream: AsyncGenerator[Any, None],
        token: str,
        tools: list[dict[str, Any]],
        depth: int = 0,
    ) -> AsyncGenerator[ChatEvent, None]:
        """Handle a streaming LLM response.

        Accumulates chunks, yields text events, and handles tool calls.

        Args:
            stream: Streaming response from LLM.
            token: Homebox auth token.
            tools: Tool definitions for recursive calls.
            depth: Current recursion depth.

        Yields:
            ChatEvent objects.
        """
        content_chunks: list[str] = []
        accumulator = ToolCallAccumulator()
        usage_info: TokenUsage | None = None
        # Track if we've received a complete message (non-incremental providers)
        seen_complete_message = False

        start_time = time.perf_counter()
        chunk_count = 0

        try:
            async for chunk in stream:
                chunk_count += 1

                if not hasattr(chunk, "choices") or not chunk.choices:
                    # Some providers send usage-only chunks at the end
                    if hasattr(chunk, "usage") and chunk.usage:
                        usage_info = TokenUsage(
                            prompt_tokens=chunk.usage.prompt_tokens,
                            completion_tokens=chunk.usage.completion_tokens,
                            total_tokens=chunk.usage.total_tokens,
                        )
                    continue

                choice = chunk.choices[0]

                # Handle content from delta (standard streaming)
                if hasattr(choice, "delta") and choice.delta:
                    delta = choice.delta
                    if hasattr(delta, "content") and delta.content:
                        content_chunks.append(delta.content)
                        yield self._emitter.text(delta.content)

                    # Accumulate tool call chunks
                    if hasattr(delta, "tool_calls") and delta.tool_calls:
                        for tc_delta in delta.tool_calls:
                            accumulator.add_chunk(tc_delta)

                # Handle content from message (non-incremental streaming)
                # Only process once to avoid duplicate content
                if (
                    not seen_complete_message
                    and hasattr(choice, "message")
                    and choice.message
                ):
                    message = choice.message
                    if hasattr(message, "content") and message.content:
                        seen_complete_message = True
                        content_chunks.append(message.content)
                        yield self._emitter.text(message.content)

                    if hasattr(message, "tool_calls") and message.tool_calls:
                        for idx, tc in enumerate(message.tool_calls):
                            accumulator.add_complete(idx, tc)

                # Capture usage from chunk
                if hasattr(chunk, "usage") and chunk.usage:
                    usage_info = TokenUsage(
                        prompt_tokens=chunk.usage.prompt_tokens,
                        completion_tokens=chunk.usage.completion_tokens,
                        total_tokens=chunk.usage.total_tokens,
                    )

        except Exception as e:
            logger.exception("[CHAT] Error during streaming")
            yield self._emitter.error(f"Streaming error: {str(e)}")
            return

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.trace(
            f"[CHAT] Streaming completed in {elapsed_ms:.0f}ms - "
            f"{chunk_count} chunks received"
        )

        # Emit usage event if available
        if usage_info:
            yield self._emitter.usage(usage_info)

        # Reconstruct full content
        full_content = "".join(content_chunks)

        # Build tool calls from accumulator
        tool_calls = accumulator.build()

        # Handle bulk create lead-in
        if not full_content and tool_calls:
            create_calls = [tc for tc in tool_calls if tc.name == "create_item"]
            if len(create_calls) > 1:
                full_content = f"I'll create {len(create_calls)} sample items for you..."
                yield self._emitter.text(full_content)

        # Handle tool calls or store message
        if tool_calls:
            async for event in self._handle_tool_calls(
                full_content, tool_calls, token, tools, depth
            ):
                yield event
        else:
            self._session.add_message(
                ChatMessage(role="assistant", content=full_content, tool_calls=None)
            )

    # =========================================================================
    # TOOL HANDLING
    # =========================================================================

    async def _handle_tool_calls(
        self,
        content: str,
        tool_calls: list[ToolCall],
        token: str,
        tools: list[dict[str, Any]],
        depth: int = 0,
    ) -> AsyncGenerator[ChatEvent, None]:
        """Handle LLM tool calls.

        Args:
            content: Assistant message content.
            tool_calls: List of ToolCall objects (already parsed).
            token: Homebox auth token.
            tools: Tool definitions for recursive calls.
            depth: Current recursion depth.

        Yields:
            ChatEvent objects.
        """
        # Safety check: prevent infinite recursion
        if depth >= MAX_TOOL_RECURSION_DEPTH:
            logger.warning(
                f"[CHAT] Max tool recursion depth ({MAX_TOOL_RECURSION_DEPTH}) reached"
            )
            yield self._emitter.error(
                "Max tool recursion depth reached. Please try a simpler query."
            )
            return

        # Add assistant message with tool_calls BEFORE executing
        self._session.add_message(
            ChatMessage(role="assistant", content=content, tool_calls=tool_calls)
        )

        # Categorize tools: READ (parallel), WRITE (approval), unknown (error)
        read_calls: list[ToolCall] = []
        write_calls: list[ToolCall] = []
        unknown_calls: list[ToolCall] = []

        for tc in tool_calls:
            tool = self._executor.get_tool(tc.name)
            if not tool:
                unknown_calls.append(tc)
            elif not self._executor.requires_approval(tc.name):
                read_calls.append(tc)
            else:
                write_calls.append(tc)

        # Handle unknown tools first (add error messages to history)
        for tc in unknown_calls:
            error_dict = {"success": False, "error": f"Unknown tool: {tc.name}"}
            self._session.add_message(
                ChatMessage(
                    role="tool",
                    content=json.dumps(error_dict),
                    tool_call_id=tc.id,
                )
            )
            yield self._emitter.error(f"Unknown tool: {tc.name}")

        # Execute READ tools in parallel, preserving message order
        if read_calls:
            logger.debug(f"[CHAT] Executing {len(read_calls)} read tools in parallel")
            async for event in self._execute_tools_parallel(read_calls, token):
                yield event

        # Handle WRITE tools (queue for approval)
        for tc in write_calls:
            async for event in self._queue_approval(tc.id, tc.name, tc.arguments, token):
                yield event

        # Continue conversation if no approvals pending
        if not write_calls:
            async for event in self._continue_with_results(token, tools, depth + 1):
                yield event

    async def _execute_tools_parallel(
        self,
        tool_calls: list[ToolCall],
        token: str,
    ) -> AsyncGenerator[ChatEvent, None]:
        """Execute multiple READ tools in parallel, preserving message order.

        Executes tools concurrently for speed, but adds results to session
        history in the original tool_calls order to maintain LLM context integrity.

        Args:
            tool_calls: List of ToolCall objects to execute.
            token: Homebox auth token.

        Yields:
            Tool execution events (tool_start, tool_result).
        """

        async def run_tool(tc: ToolCall) -> ToolExecution:
            """Execute a single tool and capture result."""
            start_time = time.perf_counter()
            result = await self._executor.execute(tc.name, tc.arguments, token)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return ToolExecution(tc=tc, result=result, elapsed_ms=elapsed_ms)

        # Execute all tools in parallel
        executions = await asyncio.gather(*(run_tool(tc) for tc in tool_calls))

        # Process results in original order, adding to history sequentially
        for execution in executions:
            tc = execution.tc
            result = execution.result
            result_dict = result.to_dict()

            logger.trace(
                f"[CHAT] Tool '{tc.name}' completed in {execution.elapsed_ms:.0f}ms"
            )

            # Add tool result to history (in order)
            self._session.add_message(
                ChatMessage(
                    role="tool",
                    content=json.dumps(result_dict),
                    tool_call_id=tc.id,
                )
            )

            # Yield events
            yield self._emitter.tool_start(tc.name, tc.arguments)
            yield self._emitter.tool_result(tc.name, result_dict)

    async def _queue_approval(
        self,
        tool_call_id: str,
        tool_name: str,
        tool_args: dict[str, Any],
        token: str,
    ) -> AsyncGenerator[ChatEvent, None]:
        """Queue a write tool for approval.

        Args:
            tool_call_id: ID of the tool call.
            tool_name: Name of the tool.
            tool_args: Tool arguments.
            token: Auth token for display info lookup.

        Yields:
            Approval required event.
        """
        # Fetch display-friendly info via executor (encapsulates client access)
        display_info = await self._executor.get_display_info(tool_name, tool_args, token)

        approval_id = create_approval_id()
        approval = PendingApproval(
            id=approval_id,
            tool_name=tool_name,
            parameters=tool_args,
            tool_call_id=tool_call_id,  # Store for efficient lookup later
            display_info=display_info,
        )
        self._session.add_pending_approval(approval)

        # Add placeholder tool result (OpenAI API requirement)
        self._session.add_message(
            ChatMessage(
                role="tool",
                content=json.dumps(
                    {
                        "success": False,
                        "pending_approval": True,
                        "approval_id": approval_id,
                        "message": f"Action '{tool_name}' requires user approval.",
                    }
                ),
                tool_call_id=tool_call_id,
            )
        )

        yield self._emitter.approval_required(approval)

    async def _continue_with_results(
        self,
        token: str,
        tools: list[dict[str, Any]],
        depth: int,
    ) -> AsyncGenerator[ChatEvent, None]:
        """Continue conversation after tool execution.

        Args:
            token: Homebox auth token.
            tools: Tool definitions.
            depth: Current recursion depth.

        Yields:
            Additional chat events.
        """
        system_prompt = self._llm.get_system_prompt()
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self._session.get_history())

        try:
            stream = self._llm.complete_stream(messages, tools)
            async for event in self._handle_stream(stream, token, tools, depth):
                yield event
        except Exception as e:
            logger.exception("LLM continuation failed")
            yield self._emitter.error(f"LLM error: {str(e)}")
