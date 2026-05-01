"""Tests for core.org_tree."""

from __future__ import annotations

import pytest

from core.org_tree import REQUIRED_PREFIX, OrgTree


def test_root_exists_and_supervisor_empty() -> None:
    tree = OrgTree()
    assert tree.get_supervisor(REQUIRED_PREFIX) == ""
    assert tree.find_children(REQUIRED_PREFIX) == []
    assert tree.is_leaf(REQUIRED_PREFIX) is True


def test_invalid_prefix() -> None:
    tree = OrgTree()
    with pytest.raises(ValueError, match="org_path"):
        tree.add_node("/其他公司/总部", {})


def test_add_child_and_find_children() -> None:
    tree = OrgTree()
    finance = f"{REQUIRED_PREFIX}/财务中心"
    tree.add_node(finance, {"k": 1})
    assert tree.find_children(REQUIRED_PREFIX) == [finance]
    assert tree.get_supervisor(finance) == REQUIRED_PREFIX
    assert tree.is_leaf(REQUIRED_PREFIX) is False
    assert tree.is_leaf(finance) is True
    assert tree.get_meta(finance) == {"k": 1}


def test_auto_intermediate_nodes() -> None:
    tree = OrgTree()
    leaf = f"{REQUIRED_PREFIX}/财务中心/应收会计"
    tree.add_node(leaf, {"role": "ar"})
    assert tree.find_children(REQUIRED_PREFIX) == [f"{REQUIRED_PREFIX}/财务中心"]
    assert tree.find_children(f"{REQUIRED_PREFIX}/财务中心") == [leaf]
    assert tree.get_meta(f"{REQUIRED_PREFIX}/财务中心") == {}


def test_add_node_updates_meta() -> None:
    tree = OrgTree()
    p = f"{REQUIRED_PREFIX}/a"
    tree.add_node(p, {"x": 1})
    tree.add_node(p, {"x": 2})
    assert tree.get_meta(p) == {"x": 2}


def test_is_leaf_unknown_raises() -> None:
    tree = OrgTree()
    with pytest.raises(KeyError):
        tree.is_leaf(f"{REQUIRED_PREFIX}/nope")


def test_load_many_order_independent() -> None:
    tree = OrgTree()
    deep = f"{REQUIRED_PREFIX}/生产中心/灌装岗"
    mid = f"{REQUIRED_PREFIX}/生产中心"
    tree.load_many(
        [
            (deep, {"d": True}),
            (mid, {"m": True}),
        ],
    )
    assert tree.get_meta(mid) == {"m": True}
    assert tree.get_meta(deep) == {"d": True}
    assert tree.find_children(mid) == [deep]


def test_load_many_from_dict() -> None:
    tree = OrgTree()
    tree.load_many({f"{REQUIRED_PREFIX}/x": {"a": 1}})
    assert tree.get_meta(f"{REQUIRED_PREFIX}/x") == {"a": 1}
