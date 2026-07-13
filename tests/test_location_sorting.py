"""Unit tests for natural sorting of location tree nodes and children.

Homebox returns siblings in lexicographic order, so numbered containers
came back as 1, 10, 11, 2. The server sorts them naturally before
handing them to the frontend.
"""

from __future__ import annotations

from server.api.locations import natural_sort_key, sort_tree_naturally


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
