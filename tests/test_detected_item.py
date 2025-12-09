"""Unit tests for DetectedItem data transformations."""

from __future__ import annotations

import pytest

from homebox_companion.tools.vision.models import DetectedItem


class TestFromRawItems:
    """Test DetectedItem.from_raw_items() parsing behavior."""

    def test_valid_data_returns_typed_items(self) -> None:
        """Parse valid raw items into DetectedItem instances."""
        raw_items = [
            {
                "name": "Hammer",
                "quantity": 2,
                "description": "Claw hammer",
                "labelIds": ["label-1"],
            },
            {
                "name": "Screwdriver",
                "quantity": 1,
                "description": "Phillips head",
            },
        ]

        items = DetectedItem.from_raw_items(raw_items)

        assert len(items) == 2
        assert items[0].name == "Hammer"
        assert items[0].quantity == 2
        assert items[0].description == "Claw hammer"
        assert items[0].label_ids == ["label-1"]
        assert items[1].name == "Screwdriver"
        assert items[1].quantity == 1

    def test_empty_name_filters_out_item(self) -> None:
        """Items with empty names should be excluded."""
        raw_items = [
            {"name": "Valid Item", "quantity": 1},
            {"name": "", "quantity": 5},
            {"name": "   ", "quantity": 3},
            {"quantity": 2},  # Missing name
        ]

        items = DetectedItem.from_raw_items(raw_items)

        assert len(items) == 1
        assert items[0].name == "Valid Item"

    def test_string_quantity_coerces_to_int(self) -> None:
        """Quantity should be coerced to int, defaulting to 1 on failure."""
        raw_items = [
            {"name": "Item 1", "quantity": "5"},
            {"name": "Item 2", "quantity": "invalid"},
            {"name": "Item 3", "quantity": 0},
            {"name": "Item 4"},  # Missing quantity
        ]

        items = DetectedItem.from_raw_items(raw_items)

        assert items[0].quantity == 5
        assert items[1].quantity == 1  # Invalid coerces to 1
        assert items[2].quantity == 1  # 0 becomes 1 (min)
        assert items[3].quantity == 1  # Missing defaults to 1

    def test_mixed_label_formats_normalize_to_string_list(self) -> None:
        """Label IDs should normalize to list of strings, filtering empty values."""
        raw_items = [
            {"name": "Item 1", "quantity": 1, "labelIds": ["abc", "def"]},
            {"name": "Item 2", "quantity": 1, "label_ids": [123, 456]},
            {"name": "Item 3", "quantity": 1, "labelIds": ["valid", "", "  "]},
            {"name": "Item 4", "quantity": 1, "labelIds": []},
            {"name": "Item 5", "quantity": 1},  # No labels
        ]

        items = DetectedItem.from_raw_items(raw_items)

        assert items[0].label_ids == ["abc", "def"]
        assert items[1].label_ids == ["123", "456"]
        assert items[2].label_ids == ["valid"]  # Empty strings filtered
        assert items[3].label_ids is None  # Empty list becomes None
        assert items[4].label_ids is None

    def test_extended_fields_parsed_correctly(self) -> None:
        """Extended fields should be parsed with type coercion."""
        raw_items = [
            {
                "name": "Drill",
                "quantity": 1,
                "manufacturer": "DeWalt",
                "modelNumber": "DCD771",
                "serialNumber": "SN12345",
                "purchasePrice": 99.99,
                "purchaseFrom": "Home Depot",
                "notes": "Slightly used",
            },
            {
                "name": "Saw",
                "quantity": 1,
                "manufacturer": "  ",  # Whitespace only
                "model_number": "M18",  # Snake case variant
                "purchase_price": "50.0",  # String price
            },
        ]

        items = DetectedItem.from_raw_items(raw_items)

        # First item - all fields present
        assert items[0].manufacturer == "DeWalt"
        assert items[0].model_number == "DCD771"
        assert items[0].serial_number == "SN12345"
        assert items[0].purchase_price == 99.99
        assert items[0].purchase_from == "Home Depot"
        assert items[0].notes == "Slightly used"

        # Second item - whitespace filtered, snake_case handled
        assert items[1].manufacturer is None  # Whitespace filtered
        assert items[1].model_number == "M18"
        assert items[1].purchase_price == 50.0  # String coerced


class TestToCreatePayload:
    """Test DetectedItem.to_create_payload() API payload generation."""

    def test_valid_item_returns_required_fields(self) -> None:
        """Payload includes name, quantity, description with correct keys."""
        item = DetectedItem(
            name="Test Item",
            quantity=3,
            description="A test description",
            location_id="loc-123",
            label_ids=["label-1", "label-2"],
        )

        payload = item.to_create_payload()

        assert payload["name"] == "Test Item"
        assert payload["quantity"] == 3
        assert payload["description"] == "A test description"
        assert payload["locationId"] == "loc-123"
        assert payload["labelIds"] == ["label-1", "label-2"]

    def test_long_name_truncates_to_255_chars(self) -> None:
        """Names longer than 255 chars should be truncated."""
        long_name = "x" * 300
        item = DetectedItem(name=long_name, quantity=1)

        payload = item.to_create_payload()

        assert len(payload["name"]) == 255
        assert payload["name"] == "x" * 255

    def test_long_description_truncates_to_1000_chars(self) -> None:
        """Descriptions longer than 1000 chars should be truncated."""
        long_desc = "y" * 1500
        item = DetectedItem(name="Item", quantity=1, description=long_desc)

        payload = item.to_create_payload()

        assert len(payload["description"]) == 1000
        assert payload["description"] == "y" * 1000

    def test_empty_fields_provide_sensible_defaults(self) -> None:
        """Missing or empty fields should have sensible defaults."""
        item = DetectedItem(name="", quantity=0, description=None)

        payload = item.to_create_payload()

        assert payload["name"] == "Untitled item"
        assert payload["quantity"] == 1
        assert payload["description"] == "Created via Homebox Companion."
        assert "locationId" not in payload
        assert "labelIds" not in payload

    def test_extended_fields_not_in_create_payload(self) -> None:
        """Extended fields should not appear in create payload."""
        item = DetectedItem(
            name="Tool",
            quantity=1,
            manufacturer="DeWalt",
            model_number="DCD771",
            purchase_price=99.99,
        )

        payload = item.to_create_payload()

        assert "manufacturer" not in payload
        assert "modelNumber" not in payload
        assert "purchasePrice" not in payload


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

    def test_zero_price_excluded(self) -> None:
        """Zero or negative prices should be excluded."""
        item = DetectedItem(
            name="Item",
            quantity=1,
            manufacturer="Brand",
            purchase_price=0,
        )

        payload = item.get_extended_fields_payload()

        assert payload is not None
        assert "purchasePrice" not in payload
        assert payload["manufacturer"] == "Brand"

    def test_whitespace_values_stripped(self) -> None:
        """Whitespace-only values should be stripped to empty strings."""
        item = DetectedItem(
            name="Item",
            quantity=1,
            manufacturer="  ",
            notes="   ",
        )

        payload = item.get_extended_fields_payload()

        # Whitespace strings are stripped, but empty strings are still included
        # The filtering of whitespace typically happens in from_raw_items
        assert payload is not None
        assert payload["manufacturer"] == ""
        assert payload["notes"] == ""


class TestHasExtendedFields:
    """Test DetectedItem.has_extended_fields() detection."""

    @pytest.mark.parametrize(
        "fields,expected",
        [
            ({}, False),  # Basic item without extended fields
            ({"manufacturer": "Bosch"}, True),  # With manufacturer
            ({"purchase_price": 50.0}, True),  # With positive price
            ({"purchase_price": 0}, False),  # With zero price
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

