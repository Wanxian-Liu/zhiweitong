"""Tests for core.skill_registry."""

from __future__ import annotations

import threading

import pytest

from core.skill_base import SkillBase, minimal_skill_meta
from core.skill_registry import SkillRegistry


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    SkillRegistry._reset_singleton_for_tests()
    yield
    SkillRegistry._reset_singleton_for_tests()


def test_register_get_unregister() -> None:
    class S(SkillBase):
        META = minimal_skill_meta(
            skill_id="s1",
            name="一",
            org_path="/智维通/城市乳业/快消板块",
        )

        async def execute(self, event: dict) -> dict:
            return {}

    reg = SkillRegistry()
    s = S()
    reg.register(s)
    assert reg.get_skill("s1") is s
    assert len(reg) == 1
    reg.unregister("s1")
    with pytest.raises(KeyError):
        reg.get_skill("s1")


def test_duplicate_skill_id() -> None:
    class A(SkillBase):
        META = minimal_skill_meta(skill_id="dup", name="a", org_path="/智维通/城市乳业")

        async def execute(self, event: dict) -> dict:
            return {}

    class B(SkillBase):
        META = minimal_skill_meta(skill_id="dup", name="b", org_path="/智维通/城市乳业/快消板块")

        async def execute(self, event: dict) -> dict:
            return {}

    reg = SkillRegistry()
    reg.register(A())
    with pytest.raises(ValueError, match="already registered"):
        reg.register(B())


def test_find_by_org_path_exact_and_children() -> None:
    class Root(SkillBase):
        META = minimal_skill_meta(skill_id="root", name="根", org_path="/智维通/城市乳业")

        async def execute(self, event: dict) -> dict:
            return {}

    class Child(SkillBase):
        META = minimal_skill_meta(
            skill_id="child",
            name="子",
            org_path="/智维通/城市乳业/快消板块",
        )

        async def execute(self, event: dict) -> dict:
            return {}

    class Grand(SkillBase):
        META = minimal_skill_meta(
            skill_id="grand",
            name="孙",
            org_path="/智维通/城市乳业/快消板块/门店",
        )

        async def execute(self, event: dict) -> dict:
            return {}

    reg = SkillRegistry()
    r, c, g = Root(), Child(), Grand()
    reg.register(r)
    reg.register(c)
    reg.register(g)

    at_root = reg.find_by_org_path("/智维通/城市乳业")
    assert {x.meta.skill_id for x in at_root} == {"root", "child", "grand"}

    at_child = reg.find_by_org_path("/智维通/城市乳业/快消板块")
    assert {x.meta.skill_id for x in at_child} == {"child", "grand"}

    at_leaf = reg.find_by_org_path("/智维通/城市乳业/快消板块/门店")
    assert [x.meta.skill_id for x in at_leaf] == ["grand"]


def test_singleton() -> None:
    a = SkillRegistry()
    b = SkillRegistry()
    assert a is b


def test_concurrent_register() -> None:
    errors: list[BaseException] = []

    class Mk:
        @staticmethod
        def skill(i: int) -> SkillBase:
            class K(SkillBase):
                META = minimal_skill_meta(
                    skill_id=f"c{i}",
                    name="x",
                    org_path="/智维通/城市乳业",
                )

                async def execute(self, event: dict) -> dict:
                    return {}

            return K()

    def worker(i: int) -> None:
        try:
            SkillRegistry().register(Mk.skill(i))
        except BaseException as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert len(SkillRegistry()) == 8
