"""Unit tests for chat session and orchestrator.

These tests verify the chat module implementations using mocked dependencies.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homebox_companion.chat.orchestrator import (
    ChatEvent,
    ChatEventType,
    ChatOrchestrator,
)
from homebox_companion.chat.session import (
    ChatMessage,
    ChatSession,
    PendingApproval,
    ToolCall,
    clear_session,
    create_approval_id,
    get_session,
)

# =============================================================================
# ChatMessage Tests
# =============================================================================


class TestChatMessage:
    """Tests for ChatMessage dataclass."""

    def test_user_message_to_llm_format(self):
        """User message should convert to basic format."""
        msg = ChatMessage(role="user", content="Hello")
        result = msg.to_llm_format()

        assert result == {"role": "user", "content": "Hello"}

    def test_assistant_message_with_tool_calls(self):
        """Assistant message with tool calls should include them."""
        msg = ChatMessage(
            role="assistant",
            content="Let me check that.",
            tool_calls=[
                ToolCall(id="tc1", name="list_locations", arguments={}),
            ],
        )
        result = msg.to_llm_format()

        assert result["role"] == "assistant"
        assert result["content"] == "Let me check that."
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["function"]["name"] == "list_locations"

    def test_tool_message_includes_call_id(self):
        """Tool message should include tool_call_id."""
        msg = ChatMessage(
            role="tool",
            content='{"success": true}',
            tool_call_id="tc1",
        )
        result = msg.to_llm_format()

        assert result["role"] == "tool"
        assert result["tool_call_id"] == "tc1"


# =============================================================================
# PendingApproval Tests
# =============================================================================


class TestPendingApproval:
    """Tests for PendingApproval dataclass."""

    def test_default_expiry_is_set(self):
        """Approval should have expiry based on settings."""
        approval = PendingApproval(
            id="ap1",
            tool_name="create_item",
            parameters={"name": "Test"},
        )

        assert approval.expires_at is not None
        assert approval.expires_at > approval.created_at

    def test_is_expired_false_when_valid(self):
        """Approval should not be expired when created."""
        approval = PendingApproval(
            id="ap1",
            tool_name="create_item",
            parameters={},
        )

        assert not approval.is_expired

    def test_is_expired_true_when_past_expiry(self):
        """Approval should be expired after expiry time."""
        approval = PendingApproval(
            id="ap1",
            tool_name="create_item",
            parameters={},
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )

        assert approval.is_expired

    def test_to_dict_includes_all_fields(self):
        """to_dict should include all relevant fields."""
        approval = PendingApproval(
            id="ap1",
            tool_name="create_item",
            parameters={"name": "Test"},
        )
        result = approval.to_dict()

        assert result["id"] == "ap1"
        assert result["tool_name"] == "create_item"
        assert result["parameters"] == {"name": "Test"}
        assert "created_at" in result
        assert "expires_at" in result
        assert "is_expired" in result


# =============================================================================
# ChatSession Tests
# =============================================================================


class TestChatSession:
    """Tests for ChatSession class."""

    def test_add_message_appends_to_history(self):
        """Messages should be appended to history."""
        session = ChatSession()
        session.add_message(ChatMessage(role="user", content="Hello"))
        session.add_message(ChatMessage(role="assistant", content="Hi there!"))

        assert len(session.messages) == 2
        assert session.messages[0].content == "Hello"
        assert session.messages[1].content == "Hi there!"

    def test_get_history_returns_llm_format(self):
        """get_history should return messages in LLM format."""
        session = ChatSession()
        session.add_message(ChatMessage(role="user", content="Hello"))

        history = session.get_history()

        assert len(history) == 1
        assert history[0] == {"role": "user", "content": "Hello"}

    def test_get_history_respects_limit(self):
        """get_history should respect max_messages limit."""
        session = ChatSession()
        for i in range(10):
            session.add_message(ChatMessage(role="user", content=f"Message {i}"))

        history = session.get_history(max_messages=3)

        assert len(history) == 3
        # Should get the most recent 3
        assert history[0]["content"] == "Message 7"
        assert history[2]["content"] == "Message 9"

    def test_add_pending_approval(self):
        """Approvals should be added to pending dict."""
        session = ChatSession()
        approval = PendingApproval(id="ap1", tool_name="test", parameters={})

        session.add_pending_approval(approval)

        assert "ap1" in session.pending_approvals
        assert session.pending_approvals["ap1"] == approval

    def test_get_pending_approval_returns_valid(self):
        """get_pending_approval should return valid approvals."""
        session = ChatSession()
        approval = PendingApproval(id="ap1", tool_name="test", parameters={})
        session.add_pending_approval(approval)

        result = session.get_pending_approval("ap1")

        assert result == approval

    def test_get_pending_approval_removes_expired(self):
        """get_pending_approval should remove and return None for expired."""
        session = ChatSession()
        approval = PendingApproval(
            id="ap1",
            tool_name="test",
            parameters={},
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        session.pending_approvals["ap1"] = approval

        result = session.get_pending_approval("ap1")

        assert result is None
        assert "ap1" not in session.pending_approvals

    def test_remove_approval_returns_true_when_found(self):
        """remove_approval should return True when approval exists."""
        session = ChatSession()
        session.pending_approvals["ap1"] = PendingApproval(id="ap1", tool_name="t", parameters={})

        result = session.remove_approval("ap1")

        assert result is True
        assert "ap1" not in session.pending_approvals

    def test_remove_approval_returns_false_when_not_found(self):
        """remove_approval should return False when approval doesn't exist."""
        session = ChatSession()

        result = session.remove_approval("nonexistent")

        assert result is False

    def test_cleanup_expired_removes_old_approvals(self):
        """cleanup_expired should remove all expired approvals."""
        session = ChatSession()
        session.pending_approvals["valid"] = PendingApproval(
            id="valid", tool_name="t", parameters={},
            expires_at=datetime.now(UTC) + timedelta(hours=1)
        )
        session.pending_approvals["expired1"] = PendingApproval(
            id="expired1", tool_name="t", parameters={},
            expires_at=datetime.now(UTC) - timedelta(seconds=1)
        )
        session.pending_approvals["expired2"] = PendingApproval(
            id="expired2", tool_name="t", parameters={},
            expires_at=datetime.now(UTC) - timedelta(seconds=10)
        )

        removed = session.cleanup_expired()

        assert removed == 2
        assert "valid" in session.pending_approvals
        assert "expired1" not in session.pending_approvals
        assert "expired2" not in session.pending_approvals

    def test_clear_removes_all_data(self):
        """clear should remove all messages and approvals."""
        session = ChatSession()
        session.add_message(ChatMessage(role="user", content="Hello"))
        session.pending_approvals["ap1"] = PendingApproval(id="ap1", tool_name="t", parameters={})

        session.clear()

        assert len(session.messages) == 0
        assert len(session.pending_approvals) == 0


# =============================================================================
# Session Management Tests
# =============================================================================


class TestSessionManagement:
    """Tests for session management functions."""

    def test_get_session_creates_new_session(self):
        """get_session should create new session for unknown token."""
        # Clear any existing sessions
        from homebox_companion.chat.session import _sessions
        _sessions.clear()

        session = get_session("test-token-123")

        assert isinstance(session, ChatSession)

    def test_get_session_returns_same_session(self):
        """get_session should return same session for same token."""
        session1 = get_session("test-token-456")
        session2 = get_session("test-token-456")

        assert session1 is session2

    def test_clear_session_removes_session(self):
        """clear_session should remove the session."""
        from homebox_companion.chat.session import _sessions

        get_session("test-token-789")  # Create session
        result = clear_session("test-token-789")

        assert result is True
        assert str(hash("test-token-789")) not in _sessions

    def test_create_approval_id_is_unique(self):
        """create_approval_id should generate unique IDs."""
        ids = {create_approval_id() for _ in range(100)}

        assert len(ids) == 100  # All unique


# =============================================================================
# ChatEvent Tests
# =============================================================================


class TestChatEvent:
    """Tests for ChatEvent dataclass."""

    def test_to_sse_format(self):
        """to_sse should return proper SSE format."""
        event = ChatEvent(
            type=ChatEventType.TEXT,
            data={"content": "Hello"},
        )

        result = event.to_sse()

        assert "event: text\n" in result
        assert 'data: {"content": "Hello"}' in result


# =============================================================================
# ChatOrchestrator Tests
# =============================================================================


class TestChatOrchestrator:
    """Tests for ChatOrchestrator class."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock HomeboxClient."""
        client = MagicMock()
        client.list_locations = AsyncMock(return_value=[{"id": "loc1", "name": "Test"}])
        client.list_labels = AsyncMock(return_value=[])
        client.list_items = AsyncMock(return_value=[])
        return client

    @pytest.fixture
    def session(self) -> ChatSession:
        """Create a fresh chat session."""
        return ChatSession()

    @pytest.fixture
    def orchestrator(self, mock_client: MagicMock, session: ChatSession) -> ChatOrchestrator:
        """Create orchestrator with mocked dependencies."""
        return ChatOrchestrator(mock_client, session)

    @pytest.mark.asyncio
    async def test_process_message_adds_user_message(
        self, orchestrator: ChatOrchestrator, session: ChatSession
    ):
        """process_message should add user message to session."""
        # Mock LLM response with no tool calls
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello!"
        mock_response.choices[0].message.tool_calls = None

        with patch(
            "homebox_companion.chat.orchestrator.litellm.acompletion",
            new=AsyncMock(return_value=mock_response)
        ):
            events = []
            async for event in orchestrator.process_message("Hi", "token"):
                events.append(event)

        assert len(session.messages) >= 1
        assert session.messages[0].role == "user"
        assert session.messages[0].content == "Hi"

    @pytest.mark.asyncio
    async def test_process_message_yields_text_event(
        self, orchestrator: ChatOrchestrator
    ):
        """process_message should yield text event for LLM response."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "I can help with that!"
        mock_response.choices[0].message.tool_calls = None

        with patch(
            "homebox_companion.chat.orchestrator.litellm.acompletion",
            new=AsyncMock(return_value=mock_response)
        ):
            events = []
            async for event in orchestrator.process_message("Help me", "token"):
                events.append(event)

        text_events = [e for e in events if e.type == ChatEventType.TEXT]
        assert len(text_events) == 1
        assert text_events[0].data["content"] == "I can help with that!"

    @pytest.mark.asyncio
    async def test_process_message_yields_done_event(
        self, orchestrator: ChatOrchestrator
    ):
        """process_message should always yield done event at the end."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Done"
        mock_response.choices[0].message.tool_calls = None

        with patch(
            "homebox_companion.chat.orchestrator.litellm.acompletion",
            new=AsyncMock(return_value=mock_response)
        ):
            events = []
            async for event in orchestrator.process_message("Test", "token"):
                events.append(event)

        assert events[-1].type == ChatEventType.DONE

    @pytest.mark.asyncio
    async def test_process_message_yields_error_on_exception(
        self, orchestrator: ChatOrchestrator
    ):
        """process_message should yield error event on LLM failure."""
        with patch(
            "homebox_companion.chat.orchestrator.litellm.acompletion",
            new=AsyncMock(side_effect=Exception("API Error"))
        ):
            events = []
            async for event in orchestrator.process_message("Test", "token"):
                events.append(event)

        error_events = [e for e in events if e.type == ChatEventType.ERROR]
        assert len(error_events) == 1
        assert "API Error" in error_events[0].data["message"]

    @pytest.mark.asyncio
    async def test_process_message_handles_chained_tool_calls(
        self, mock_client: MagicMock, session: ChatSession
    ):
        """Orchestrator should handle multiple sequential tool calls correctly.

        This tests the exact scenario that triggered the original bug:
        1. User asks a question
        2. LLM makes a search_items call
        3. LLM receives results and makes a get_item call
        4. LLM provides final response

        The key assertion is that the session message sequence is valid:
        each tool message must be preceded by an assistant message with tool_calls.
        """
        orchestrator = ChatOrchestrator(mock_client, session)

        # Mock search_items tool
        mock_client.search_items = AsyncMock(return_value=[
            {"id": "item-123", "name": "Picture Hanging Wire"}
        ])
        # Mock get_item tool
        mock_client.get_item = AsyncMock(return_value={
            "id": "item-123",
            "name": "Picture Hanging Wire",
            "description": "Steel wire for hanging pictures"
        })

        def create_tool_call(name: str, args: dict):
            """Helper to create mock tool calls."""
            tc = MagicMock()
            tc.id = f"call_{name}"
            tc.function.name = name
            tc.function.arguments = json.dumps(args)
            return tc

        # First LLM response: search_items call
        first_response = MagicMock()
        first_response.choices = [MagicMock()]
        first_response.choices[0].message.content = ""
        first_response.choices[0].message.tool_calls = [
            create_tool_call("search_items", {"query": "wire", "compact": True})
        ]

        # Second LLM response: get_item call based on search results
        second_response = MagicMock()
        second_response.choices = [MagicMock()]
        second_response.choices[0].message.content = ""
        second_response.choices[0].message.tool_calls = [
            create_tool_call("get_item", {"item_id": "item-123"})
        ]

        # Final LLM response: text response
        final_response = MagicMock()
        final_response.choices = [MagicMock()]
        final_response.choices[0].message.content = (
            "Based on my search, you have Picture Hanging Wire."
        )
        final_response.choices[0].message.tool_calls = None

        with patch(
            "homebox_companion.chat.orchestrator.litellm.acompletion",
            new=AsyncMock(side_effect=[first_response, second_response, final_response])
        ):
            events = []
            async for event in orchestrator.process_message("What wire do I have?", "token"):
                events.append(event)

        # Verify we got the expected events
        tool_start_events = [e for e in events if e.type == ChatEventType.TOOL_START]
        tool_result_events = [e for e in events if e.type == ChatEventType.TOOL_RESULT]
        text_events = [e for e in events if e.type == ChatEventType.TEXT]

        assert len(tool_start_events) == 2, "Should have 2 tool start events"
        assert len(tool_result_events) == 2, "Should have 2 tool result events"
        assert len(text_events) == 1, "Should have 1 text event"
        assert "Picture Hanging Wire" in text_events[0].data["content"]

        # Verify message sequence in session is valid
        # Each tool message must be preceded by an assistant message whose tool_calls
        # contains the matching tool_call_id
        messages = session.messages
        for i, msg in enumerate(messages):
            if msg.role == "tool":
                # Find the most recent assistant message with tool_calls containing this ID
                found_matching_assistant = False
                for j in range(i - 1, -1, -1):
                    prev_msg = messages[j]
                    if prev_msg.role == "assistant" and prev_msg.tool_calls:
                        assistant_call_ids = [tc.id for tc in prev_msg.tool_calls]
                        if msg.tool_call_id in assistant_call_ids:
                            found_matching_assistant = True
                            break

                assert found_matching_assistant, (
                    f"Tool message at index {i} with tool_call_id={msg.tool_call_id} "
                    f"has no preceding assistant message with matching tool_calls"
                )

    @pytest.mark.asyncio
    async def test_recursion_depth_limit(
        self, mock_client: MagicMock, session: ChatSession
    ):
        """Orchestrator should stop after MAX_TOOL_RECURSION_DEPTH iterations."""
        from homebox_companion.chat.orchestrator import MAX_TOOL_RECURSION_DEPTH

        orchestrator = ChatOrchestrator(mock_client, session)

        # Mock a tool that always exists
        mock_client.list_locations = AsyncMock(return_value=[{"id": "loc1", "name": "Test"}])

        def create_tool_call():
            tc = MagicMock()
            tc.id = "call_list_locations"
            tc.function.name = "list_locations"
            tc.function.arguments = "{}"
            return tc

        # Create a response that always calls list_locations (infinite loop scenario)
        tool_response = MagicMock()
        tool_response.choices = [MagicMock()]
        tool_response.choices[0].message.content = ""
        tool_response.choices[0].message.tool_calls = [create_tool_call()]

        # Create enough responses to trigger the limit
        responses = [tool_response] * (MAX_TOOL_RECURSION_DEPTH + 5)

        with patch(
            "homebox_companion.chat.orchestrator.litellm.acompletion",
            new=AsyncMock(side_effect=responses)
        ):
            events = []
            async for event in orchestrator.process_message("Test", "token"):
                events.append(event)

        # Should have an error about max recursion depth
        error_events = [e for e in events if e.type == ChatEventType.ERROR]
        assert any("recursion" in e.data.get("message", "").lower() for e in error_events), (
            "Should have error about max recursion depth"
        )
