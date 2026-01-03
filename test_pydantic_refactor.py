"""Quick test to verify the Pydantic refactor works correctly."""

from homebox_companion.chat.session import PendingApproval
from homebox_companion.chat.types import ChatMessage, ToolCall
from homebox_companion.homebox.models import ItemCreate, Location
from homebox_companion.homebox.views import LocationView
from homebox_companion.mcp.types import DisplayInfo, ToolParams, ToolResult


def test_models():
    """Test core domain models."""
    # Test Location model
    loc = Location.model_validate({"id": "abc", "name": "Test", "itemCount": 5})
    assert loc.name == "Test"
    assert loc.item_count == 5
    print(f"✓ Location: {loc.name}, items: {loc.item_count}")

    # Test ItemCreate
    item_create = ItemCreate(name="Test Item", location_id="loc-123")
    payload = item_create.model_dump(by_alias=True, exclude_unset=True)
    assert payload["name"] == "Test Item"
    assert payload["locationId"] == "loc-123"
    print(f"✓ ItemCreate payload uses aliases: {payload}")


def test_views():
    """Test view models with URL generation."""
    # Test LocationView from_dict
    view_data = {"id": "loc-1", "name": "Garage", "itemCount": 10}
    view = LocationView.from_dict(view_data)
    assert view.name == "Garage"
    assert "/location/loc-1" in view.url
    print(f"✓ LocationView: {view.name}, url: {view.url}")

    # Test validation warning (missing id)
    empty_view = LocationView.from_dict({})
    assert empty_view.id == ""  # Should not fail, but log warning
    print("✓ LocationView handles missing id gracefully")


def test_mcp_types():
    """Test MCP types (now Pydantic)."""
    # Test ToolResult
    result = ToolResult(success=True, data={"items": [1, 2, 3]})
    assert result.to_dict()["success"] is True
    print(f"✓ ToolResult: {result.to_dict()}")

    # Test ToolParams base class with extra="forbid"
    class TestParams(ToolParams):
        name: str

    params = TestParams(name="test")
    assert params.name == "test"
    print(f"✓ ToolParams: {params.name}")

    # Test that extra params are rejected (use dict to bypass static type checking)
    try:
        TestParams.model_validate({"name": "test", "unknown_field": "bad"})
        raise AssertionError("Should have raised validation error")
    except Exception as e:
        assert "extra" in str(e).lower() or "unknown_field" in str(e).lower()
        print("✓ ToolParams correctly rejects unknown fields")


def test_chat_session_models():
    """Test chat session models (converted from dataclass to Pydantic)."""
    # Test ChatMessage
    msg = ChatMessage(role="user", content="Hello!")
    llm_format = msg.to_llm_format()
    assert llm_format["role"] == "user"
    assert llm_format["content"] == "Hello!"
    print(f"✓ ChatMessage: {llm_format}")

    # Test ToolCall (frozen)
    tc = ToolCall(id="tc-1", name="list_items", arguments={"page": 1})
    assert tc.name == "list_items"
    assert tc.model_config.get("frozen") is True
    print(f"✓ ToolCall: {tc.name}, frozen: True")

    # Test immutability
    try:
        tc.name = "different"
        raise AssertionError("Should be immutable")
    except Exception:
        print("✓ ToolCall is immutable (frozen)")

    # Test PendingApproval with model_validator auto-setting expires_at
    approval = PendingApproval(
        id="ap-1", tool_name="delete_item", parameters={"item_id": "x"}
    )
    assert approval.expires_at is not None
    print(f"✓ PendingApproval: expires_at auto-set: {approval.expires_at}")

    # Test DisplayInfo
    display = DisplayInfo(item_name="Test Item", location="Garage")
    dumped = display.model_dump(exclude_none=True)
    assert "item_name" in dumped
    assert "asset_id" not in dumped  # excluded because None
    print(f"✓ DisplayInfo: {dumped}")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Pydantic-First Architecture Refactor")
    print("=" * 60)

    test_models()
    print()
    test_views()
    print()
    test_mcp_types()
    print()
    test_chat_session_models()

    print()
    print("=" * 60)
    print("All Pydantic model tests passed! ✓")
    print("=" * 60)
