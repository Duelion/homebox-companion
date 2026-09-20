"""Unit tests for natural sorting of location tree nodes and children.

Homebox returns siblings in lexicographic order, so numbered containers
came back as 1, 10, 11, 2. The server sorts them naturally before
handing them to the frontend.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.api import locations as locations_module
from server.api.locations import natural_sort_key, sort_tree_naturally

pytestmark = pytest.mark.unit


def _names(nodes: list[dict]) -> list[str]:
    return [node["name"] for node in nodes]


class TestNaturalSortKey:
    def test_numbers_sort_numerically(self) -> None:
        names = ["1", "10", "11", "2", "21", "3"]
        assert sorted(names, key=natural_sort_key) == ["1", "2", "3", "10", "11", "21"]

    def test_mixed_text_and_numbers(self) -> None:
        names = ["Box 10", "Box 2", "Box 1", "Box 21"]
        assert sorted(names, key=natural_sort_key) == ["Box 1", "Box 2", "Box 10", "Box 21"]

    def test_case_insensitive(self) -> None:
        names = ["banana", "Apple", "cherry"]
        assert sorted(names, key=natural_sort_key) == ["Apple", "banana", "cherry"]

    def test_plain_text_stays_alphabetical(self) -> None:
        names = ["Garage", "Attic", "Basement"]
        assert sorted(names, key=natural_sort_key) == ["Attic", "Basement", "Garage"]

    def test_numeric_prefix_before_text(self) -> None:
        names = ["Shelf", "2 Shelf", "10 Shelf"]
        assert sorted(names, key=natural_sort_key) == ["2 Shelf", "10 Shelf", "Shelf"]

    def test_multiple_digit_runs(self) -> None:
        names = ["A2-B10", "A2-B2", "A10-B1"]
        assert sorted(names, key=natural_sort_key) == ["A2-B2", "A2-B10", "A10-B1"]


class TestSortTreeNaturally:
    def test_sorts_top_level_nodes(self) -> None:
        tree = [{"name": "10"}, {"name": "2"}, {"name": "1"}]
        assert _names(sort_tree_naturally(tree)) == ["1", "2", "10"]

    def test_sorts_nested_children_recursively(self) -> None:
        tree = [
            {
                "name": "Garage",
                "children": [
                    {"name": "Box 10", "children": [{"name": "11"}, {"name": "2"}]},
                    {"name": "Box 2"},
                ],
            }
        ]
        result = sort_tree_naturally(tree)
        assert _names(result[0]["children"]) == ["Box 2", "Box 10"]
        assert _names(result[0]["children"][1]["children"]) == ["2", "11"]

    def test_handles_missing_or_null_names(self) -> None:
        tree = [{"name": None}, {"id": "no-name"}, {"name": "A"}]
        result = sort_tree_naturally(tree)
        assert len(result) == 3

    def test_empty_tree(self) -> None:
        assert sort_tree_naturally([]) == []

    def test_preserves_node_data(self) -> None:
        tree = [{"name": "2", "id": "b", "type": "item"}, {"name": "1", "id": "a", "type": "location"}]
        result = sort_tree_naturally(tree)
        assert result[0] == {"name": "1", "id": "a", "type": "location"}
        assert result[1] == {"name": "2", "id": "b", "type": "item"}

    def test_does_not_mutate_input(self) -> None:
        tree = [{"name": "10", "children": [{"name": "2"}, {"name": "1"}]}]
        original = [{"name": "10", "children": [{"name": "2"}, {"name": "1"}]}]

        result = sort_tree_naturally(tree)

        assert tree == original
        assert result is not tree
        assert result[0] is not tree[0]
        assert result[0]["children"] is not tree[0]["children"]

    def test_equal_numeric_keys_are_stable(self) -> None:
        tree = [{"name": "02", "id": "first"}, {"name": "2", "id": "second"}]

        result = sort_tree_naturally(tree)

        assert [node["id"] for node in result] == ["first", "second"]

    def test_preserves_null_and_empty_children(self) -> None:
        tree = [
            {"name": "A", "children": None, "extra": {"kind": "null"}},
            {"name": "B", "children": [], "extra": {"kind": "empty"}},
        ]

        result = sort_tree_naturally(tree)

        assert result[0]["children"] is None
        assert result[1]["children"] == []
        assert result[1]["children"] is not tree[1]["children"]
        assert result[0]["extra"] == {"kind": "null"}


class _LocationClient:
    def __init__(self, tree: list[dict[str, Any]] | None = None) -> None:
        self.tree = tree or []
        self.locations: dict[str, dict[str, Any]] = {}
        self.all_locations: list[dict[str, Any]] = []
        self.fail_ids: set[str] = set()

    async def get_location_tree(self, token: str) -> list[dict[str, Any]]:
        return self.tree

    async def get_location(self, token: str, location_id: str) -> dict[str, Any]:
        if location_id in self.fail_ids:
            raise RuntimeError("simulated child lookup failure")
        return self.locations[location_id]

    async def list_locations(
        self, token: str, *, filter_children: bool | None = None
    ) -> list[dict[str, Any]]:
        return self.all_locations


def _http_client(location_client: _LocationClient) -> TestClient:
    app = FastAPI()
    app.include_router(locations_module.router)
    from server.dependencies import get_client, get_token

    app.dependency_overrides[get_client] = lambda: location_client
    app.dependency_overrides[get_token] = lambda: "test-token"
    return TestClient(app)


def test_tree_route_sorts_without_mutating_client_payload() -> None:
    tree = [
        {"id": "root", "name": "10", "children": [{"id": "child", "name": "2"}]},
        {"id": "root-2", "name": "2", "children": []},
    ]
    client = _LocationClient(tree)

    with _http_client(client) as http_client:
        response = http_client.get("/locations/tree")

    assert response.status_code == 200
    assert [node["name"] for node in response.json()] == ["2", "10"]
    assert tree[0]["name"] == "10"
    assert tree[0]["children"][0]["name"] == "2"


def test_location_route_sorts_nested_children_and_preserves_fallback_data() -> None:
    client = _LocationClient()
    client.locations["root"] = {
        "id": "root",
        "name": "Garage",
        "children": [
            {"id": "shelf-10", "name": "Shelf 10"},
            {"id": "shelf-2", "name": "Shelf 2"},
            {"id": "missing", "name": "Zone 99", "description": "Fallback description"},
        ],
    }
    client.locations["shelf-10"] = {
        "id": "shelf-10",
        "name": "Shelf 10",
        "description": "Ten",
        "children": [{"id": "bin-11", "name": "11"}, {"id": "bin-2", "name": "2"}],
    }
    client.locations["shelf-2"] = {
        "id": "shelf-2",
        "name": "Shelf 2",
        "description": "Two",
        "children": [],
    }
    client.fail_ids.add("missing")
    client.all_locations = [
        {"id": "root", "itemCount": 7},
        {"id": "shelf-10", "itemCount": 10},
        {"id": "shelf-2", "itemCount": 2},
        {"id": "missing", "itemCount": 99},
    ]

    with _http_client(client) as http_client:
        response = http_client.get("/locations/root")

    assert response.status_code == 200
    body = response.json()
    assert body["itemCount"] == 7
    assert [child["name"] for child in body["children"]] == ["Shelf 2", "Shelf 10", "Zone 99"]
    assert [child["name"] for child in body["children"][1]["children"]] == ["2", "11"]
    fallback = body["children"][2]
    assert fallback["name"] == "Zone 99"
    assert fallback["description"] == "Fallback description"
    assert fallback["itemCount"] == 99
