"""In-memory organization tree backed by anytree; API is path-string only.

Paths must live under :data:`REQUIRED_PREFIX` ``/智维通/城市乳业``.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from anytree import Node

REQUIRED_PREFIX = "/智维通/城市乳业"


class _OrgNode(Node):
    """Internal node; ``name`` is the last path segment for readability."""

    def __init__(
        self,
        org_path: str,
        meta: dict[str, Any],
        parent: _OrgNode | None = None,
    ) -> None:
        segment = org_path.rstrip("/").rsplit("/", 1)[-1]
        super().__init__(segment, parent=parent)
        self.org_path = org_path
        self.meta = dict(meta)


class OrgTree:
    """组织树：不向外暴露 anytree 节点，仅通过 ``org_path`` 字符串操作。"""

    REQUIRED_PREFIX = REQUIRED_PREFIX

    def __init__(self) -> None:
        self._nodes: dict[str, _OrgNode] = {}
        root = _OrgNode(self.REQUIRED_PREFIX, {}, parent=None)
        self._nodes[self.REQUIRED_PREFIX] = root

    def _validate(self, org_path: str) -> str:
        p = org_path.strip()
        if not p.startswith("/"):
            p = "/" + p
        p = p.rstrip("/") or "/"
        if p != self.REQUIRED_PREFIX and not p.startswith(self.REQUIRED_PREFIX + "/"):
            raise ValueError(
                f"org_path must be {self.REQUIRED_PREFIX!r} or a child path, got {org_path!r}",
            )
        return p

    @staticmethod
    def _parent_path(path: str) -> str | None:
        if path == REQUIRED_PREFIX:
            return None
        parent = path.rsplit("/", 1)[0]
        return parent if parent else None

    def add_node(self, org_path: str, meta: dict[str, Any]) -> None:
        """插入或更新节点；若祖先不存在则自动用 ``meta={{}}`` 补齐。"""
        path = self._validate(org_path)
        chain = self._ancestor_chain(path)
        for ancestor in chain[:-1]:
            if ancestor in self._nodes:
                continue
            par = self._parent_path(ancestor)
            if par is None or par not in self._nodes:
                raise RuntimeError(f"cannot create {ancestor!r}: missing parent")
            self._nodes[ancestor] = _OrgNode(ancestor, {}, parent=self._nodes[par])

        if path in self._nodes:
            self._nodes[path].meta = dict(meta)
            return
        par = self._parent_path(path)
        if par is None or par not in self._nodes:
            raise RuntimeError(f"cannot create {path!r}: missing parent")
        self._nodes[path] = _OrgNode(path, dict(meta), parent=self._nodes[par])

    def _ancestor_chain(self, path: str) -> list[str]:
        """从根到 ``path`` 的祖先链（含两端）。"""
        if path == self.REQUIRED_PREFIX:
            return [path]
        rel = path[len(self.REQUIRED_PREFIX) :].lstrip("/")
        segments = rel.split("/") if rel else []
        chain: list[str] = [self.REQUIRED_PREFIX]
        acc = self.REQUIRED_PREFIX
        for seg in segments:
            acc = f"{acc}/{seg}"
            chain.append(acc)
        return chain

    def find_children(self, org_path: str) -> list[str]:
        """直接子节点的全路径，按字典序排序。"""
        p = self._validate(org_path)
        node = self._nodes.get(p)
        if node is None:
            return []
        return sorted(c.org_path for c in node.children)

    def get_supervisor(self, org_path: str) -> str:
        """父路径；根节点返回空字符串。"""
        p = self._validate(org_path)
        if p == self.REQUIRED_PREFIX:
            return ""
        par = self._parent_path(p)
        return par if par is not None else ""

    def is_leaf(self, org_path: str) -> bool:
        """若无子节点则为叶子；路径不存在则抛错。"""
        p = self._validate(org_path)
        node = self._nodes.get(p)
        if node is None:
            raise KeyError(f"unknown org_path: {org_path!r}")
        return len(node.children) == 0

    def get_meta(self, org_path: str) -> dict[str, Any]:
        """返回节点 meta 副本；不存在则抛错。"""
        p = self._validate(org_path)
        node = self._nodes.get(p)
        if node is None:
            raise KeyError(f"unknown org_path: {org_path!r}")
        return dict(node.meta)

    def load_many(
        self,
        items: Mapping[str, dict[str, Any]] | Iterable[tuple[str, dict[str, Any]]],
    ) -> None:
        """批量加载；按路径长度排序，尽量先父后子。"""
        if isinstance(items, Mapping):
            pairs = list(items.items())
        else:
            pairs = list(items)
        pairs.sort(key=lambda x: (len(x[0]), x[0]))
        for path, meta in pairs:
            self.add_node(path, meta)


def canonical_org_tree() -> OrgTree:
    """预载 :mod:`shared.org_canonical` 中已注册岗路径的 :class:`OrgTree`。"""
    from shared.org_canonical import CANONICAL_ORG_PATHS

    tree = OrgTree()
    tree.load_many({p: {} for p in CANONICAL_ORG_PATHS})
    return tree
