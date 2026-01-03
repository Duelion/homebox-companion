"""Unit tests for DetectedItem data transformations."""

from __future__ import annotations

import pytest

from homebox_companion.tools.vision.models import DetectedItem

# All tests in this module are pure unit tests
pytestmark = pytest.mark.unit


class TestGetExtendedFieldsPayload:
    """Test DetectedItem.get_extended_fields_payload() for update operations."""

    def test_with_data_returns_camelcase_dict(self) -> None:
        """Extended fields should use camelCase keys."""
        item = DetectedItem(
            name="Tool",
            quantity=1,
            manufacturer="DeWalt",
            model_number="DCD771",
            serial_number="SN12345",
            purchase_price=99.99,
            purchase_from="Home Depot",
            notes="Good condition",
        )

        payload = item.get_extended_fields_payload()

        assert payload is not None
        assert payload["manufacturer"] == "DeWalt"
        assert payload["modelNumber"] == "DCD771"
        assert payload["serialNumber"] == "SN12345"
        assert payload["purchasePrice"] == 99.99
        assert payload["purchaseFrom"] == "Home Depot"
        assert payload["notes"] == "Good condition"

    def test_when_empty_returns_none(self) -> None:
        """No extended fields should return None."""
        item = DetectedItem(name="Basic Item", quantity=1)

        payload = item.get_extended_fields_payload()

        assert payload is None


class TestHasExtendedFields:
    """Test DetectedItem.has_extended_fields() detection."""

    @pytest.mark.parametrize(
        "fields,expected",
        [
            ({}, False),  # Basic item without extended fields
            ({"manufacturer": "Bosch"}, True),  # With manufacturer
            ({"purchase_price": 50.0}, True),  # With positive price
            ({"notes": "Damaged"}, True),  # With notes
            ({"model_number": "ABC123"}, True),  # With model number
            ({"serial_number": "SN12345"}, True),  # With serial number
            ({"purchase_from": "Store"}, True),  # With purchase location
        ],
    )
    def test_has_extended_fields(self, fields: dict, expected: bool) -> None:
        """Item with various extended fields should return appropriate result."""
        item = DetectedItem(name="Tool", quantity=1, **fields)

        assert item.has_extended_fields() is expected


class TestPydanticValidation:
    """Test that DetectedItem validates input correctly via Pydantic."""

    def test_rejects_empty_name(self) -> None:
        """Empty name should be rejected by Pydantic validation."""
        with pytest.raises(ValueError):
            DetectedItem(name="", quantity=1)

    def test_rejects_name_too_long(self) -> None:
        """Name longer than 255 chars should be rejected."""
        with pytest.raises(ValueError):
            DetectedItem(name="x" * 300, quantity=1)

    def test_rejects_description_too_long(self) -> None:
        """Description longer than 1000 chars should be rejected."""
        with pytest.raises(ValueError):
            DetectedItem(name="Item", quantity=1, description="y" * 1500)

    def test_rejects_zero_quantity(self) -> None:
        """Zero quantity should be rejected."""
        with pytest.raises(ValueError):
            DetectedItem(name="Item", quantity=0)

    def test_rejects_zero_price(self) -> None:
        """Zero price should be rejected (must be > 0)."""
        with pytest.raises(ValueError):
            DetectedItem(name="Item", quantity=1, purchase_price=0)

    def test_accepts_valid_item(self) -> None:
        """Valid item should be accepted."""
        item = DetectedItem(
            name="Valid Item",
            quantity=1,
            description="A valid description",
        )
        assert item.name == "Valid Item"
        assert item.quantity == 1
