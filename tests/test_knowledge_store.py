"""Tests for core.knowledge_store (ChromaDB)."""

from __future__ import annotations

import importlib.util
import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from core.knowledge_store import (
    KnowledgeStore,
    _decode_tags,
    _encode_tags,
    _flatten_metadata,
    _tags_intersect,
    _tags_visible_for_org_path,
)
from core.org_tree import OrgTree

skip_no_chroma = pytest.mark.skipif(
    importlib.util.find_spec("chromadb") is None,
    reason="chromadb not installed (see pyproject.toml)",
)


def test_tag_helpers() -> None:
    assert _encode_tags(["b", "a", "b"]) == "a|b"
    assert _decode_tags("a|b") == ["a", "b"]
    assert _tags_intersect(["a", "b"], ["b", "c"])
    assert not _tags_intersect(["a"], ["b"])
    assert _tags_intersect(["a"], [])
    assert _tags_visible_for_org_path(["快消板块"], "/智维通/城市乳业/快消板块")


def test_flatten_metadata() -> None:
    m = _flatten_metadata({"n": 1, "s": "x", "o": {"k": 2}})
    assert m["n"] == 1
    assert m["s"] == "x"
    assert json.loads(str(m["o"])) == {"k": 2}


def _make_tree() -> OrgTree:
    t = OrgTree()
    t.load_many(
        {
            "/智维通/城市乳业": {},
            "/智维通/城市乳业/快消板块": {},
        },
    )
    return t


@skip_no_chroma
def test_store_retrieve_with_temp_dir() -> None:
    async def _run() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ks = KnowledgeStore(persist_directory=Path(tmp))
            doc_id = await ks.store(
                ["finance", "receivable"],
                "应收账款月度对账流程说明。",
                {"source": "runbook"},
                org_path="/智维通/城市乳业/快消板块",
            )
            assert doc_id
            rows = await ks.retrieve(
                ["finance"],
                "应收账款 对账",
                top_k=3,
                org_path="/智维通/城市乳业/快消板块",
            )
            assert len(rows) >= 1
            hit = next(r for r in rows if r["doc_id"] == doc_id)
            assert "应收账款" in hit["content"]
            assert "finance" in hit["tags"]
            assert hit["metadata"].get("source") == "runbook"

    asyncio.run(_run())


@skip_no_chroma
def test_tag_filter_excludes_mismatch() -> None:
    async def _run() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ks = KnowledgeStore(persist_directory=Path(tmp))
            await ks.store(["only_a"], "document one", {}, org_path=None)
            rows = await ks.retrieve(
                ["other_tag"],
                "document",
                top_k=5,
                org_path=None,
            )
            assert rows == []

    asyncio.run(_run())


@skip_no_chroma
def test_org_tree_requires_org_path_on_retrieve() -> None:
    async def _run() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tree = _make_tree()
            ks = KnowledgeStore(persist_directory=Path(tmp), org_tree=tree)
            await ks.store(["快消"], "hello", {}, org_path="/智维通/城市乳业/快消板块")
            with pytest.raises(ValueError, match="org_path is required"):
                await ks.retrieve(["快消"], "hello", org_path=None)

    asyncio.run(_run())


@skip_no_chroma
def test_org_tree_rejects_unknown_path() -> None:
    async def _run() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tree = _make_tree()
            ks = KnowledgeStore(persist_directory=Path(tmp), org_tree=tree)
            with pytest.raises(KeyError):
                await ks.store(["x"], "c", {}, org_path="/智维通/城市乳业/不存在部门")

    asyncio.run(_run())


@skip_no_chroma
def test_update_and_delete() -> None:
    async def _run() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ks = KnowledgeStore(persist_directory=Path(tmp))
            doc_id = await ks.store(["t1"], "original body", {"v": 1})
            await ks.update(doc_id, content="updated body", tags=["t2"], metadata={"v": 2})
            rows = await ks.retrieve(["t2"], "updated", org_path=None)
            assert any(r["doc_id"] == doc_id for r in rows)
            await ks.delete(doc_id)
            with pytest.raises(KeyError):
                await ks.delete(doc_id)

    asyncio.run(_run())


def test_lazy_core_export() -> None:
    import core

    KS = core.KnowledgeStore
    assert KS is KnowledgeStore
