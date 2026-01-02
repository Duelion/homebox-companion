from homebox_companion.chat.session import ChatMessage, ChatSession, ToolCall


def test_history_truncation_safety():
    """Verify that get_history does not orphan tool messages."""
    session = ChatSession()

    # 1. Add some initial context
    session.add_message(ChatMessage(role="user", content="Hello"))
    session.add_message(ChatMessage(role="assistant", content="Hi!"))

    # 2. Add a tool sequence
    tc1 = ToolCall(id="call_1", name="test_tool", arguments={})
    session.add_message(ChatMessage(role="assistant", content="Checking...", tool_calls=[tc1]))
    session.add_message(ChatMessage(role="tool", content='{"result": "ok"}', tool_call_id="call_1"))

    # 3. Add more messages to reach limit
    session.add_message(ChatMessage(role="user", content="Next thing"))
    session.add_message(ChatMessage(role="assistant", content="Got it"))

    # Total messages: 6
    # [0] user: Hello
    # [1] assistant: Hi!
    # [2] assistant: Checking... (tc1)
    # [3] tool: ok (call_1)
    # [4] user: Next thing
    # [5] assistant: Got it

    # Test 1: Slicing exactly at the tool message (limit=3)
    # If we take last 3, we get [3], [4], [5].
    # [3] is a tool message. The fix should move start back to [2].
    history = session.get_history(max_messages=3)

    assert history[0]["role"] == "assistant"
    assert "tool_calls" in history[0]
    assert history[1]["role"] == "tool"
    assert history[1]["tool_call_id"] == "call_1"
    assert len(history) == 4

def test_history_truncation_multi_tool():
    """Verify safety with multiple tool results in a row."""
    session = ChatSession()
    session.add_message(ChatMessage(role="user", content="Search"))

    tcs = [
        ToolCall(id="c1", name="t1", arguments={}),
        ToolCall(id="c2", name="t2", arguments={})
    ]
    session.add_message(ChatMessage(role="assistant", content="", tool_calls=tcs))
    session.add_message(ChatMessage(role="tool", content="r1", tool_call_id="c1"))
    session.add_message(ChatMessage(role="tool", content="r2", tool_call_id="c2"))

    # If we slice at the last tool message (limit=1)
    # It should move back to the assistant call
    history = session.get_history(max_messages=1)

    assert history[0]["role"] == "assistant"
    assert len(history) == 3
    assert history[1]["tool_call_id"] == "c1"
    assert history[2]["tool_call_id"] == "c2"
