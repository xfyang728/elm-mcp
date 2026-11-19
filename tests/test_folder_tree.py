"""Regression tests for list_folder_tree (2026-11-18).

list_folders returns a flat [{title, uri, depth, parent}] list; build_folder_tree
must assemble it into a nested {title, uri, children} tree without dropping
nodes or recursing forever on malformed / cyclic parent links. list_folder_tree
is the async convenience wrapper exposed as an MCP tool.
"""

from unittest.mock import AsyncMock, patch

import pytest

from elm_mcp import oslc


def _titles(nodes):
    return [(n["title"], _titles(n["children"])) for n in nodes]


def test_build_folder_tree_nests_children():
    flat = [
        {"title": "Root", "uri": "r", "depth": 1, "parent": "pa"},
        {"title": "A", "uri": "a", "depth": 2, "parent": "r"},
        {"title": "B", "uri": "b", "depth": 2, "parent": "r"},
        {"title": "A1", "uri": "a1", "depth": 3, "parent": "a"},
    ]
    assert _titles(oslc.build_folder_tree(flat)) == [
        ("Root", [("A", [("A1", [])]), ("B", [])])
    ]


def test_build_folder_tree_keeps_orphan_as_root():
    flat = [{"title": "Orphan", "uri": "o", "parent": "missing"}]
    assert _titles(oslc.build_folder_tree(flat)) == [("Orphan", [])]


def test_build_folder_tree_self_parent_is_root():
    flat = [{"title": "Self", "uri": "s", "parent": "s"}]
    assert _titles(oslc.build_folder_tree(flat)) == [("Self", [])]


def test_build_folder_tree_cycle_becomes_roots():
    flat = [
        {"title": "A", "uri": "a", "parent": "b"},
        {"title": "B", "uri": "b", "parent": "a"},
    ]
    assert _titles(oslc.build_folder_tree(flat)) == [("A", []), ("B", [])]


def test_build_folder_tree_ignores_entries_without_uri():
    flat = [{"title": "NoUri"}, {"title": "Ok", "uri": "ok", "parent": None}]
    assert _titles(oslc.build_folder_tree(flat)) == [("Ok", [])]


async def test_list_folder_tree_calls_list_folders():
    flat = [
        {"title": "Root", "uri": "r", "parent": "pa"},
        {"title": "Child", "uri": "c", "parent": "r"},
    ]
    with patch("elm_mcp.oslc.list_folders", new=AsyncMock(return_value=flat)) as mock:
        tree = await oslc.list_folder_tree("TEST")
    mock.assert_awaited_once_with("TEST")
    assert _titles(tree) == [("Root", [("Child", [])])]
