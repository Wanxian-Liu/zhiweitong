"""Sandbox test runner: stub EventBus / StateManager, optional coverage gate (default 90%)."""

from __future__ import annotations

import inspect
import io
import logging
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.event_bus import topic_matches
from core.skill_base import SkillBase

logger = logging.getLogger(__name__)

EventCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


@dataclass
class SandboxCaseResult:
    index: int
    event: dict[str, Any]
    ok: bool
    result: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class SandboxReport:
    coverage_percent: float
    coverage_morfs: tuple[str, ...]
    coverage_threshold: float
    passed: int
    failed: int
    cases: list[SandboxCaseResult] = field(default_factory=list)
    event_bus: StubEventBus | None = None
    state_manager: StubStateManager | None = None


class CoverageError(Exception):
    """Raised when measured coverage is below the configured threshold."""

    def __init__(self, percent: float, threshold: float, report: SandboxReport) -> None:
        self.percent = percent
        self.threshold = threshold
        self.report = report
        super().__init__(
            f"coverage {percent:.2f}% is below required {threshold:.2f}% "
            f"(morfs={report.coverage_morfs!r})",
        )


class StubEventBus:
    """In-memory bus compatible with :class:`core.event_bus.EventBus` call patterns.

    Records every :meth:`publish` for assertions; invokes subscribers inline (no
    background task).
    """

    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, Any]]] = []
        self._subs: dict[str, tuple[str, EventCallback]] = {}
        self._closed = False

    async def publish(self, topic: str, event: dict[str, Any]) -> None:
        if self._closed:
            raise RuntimeError("EventBus is closed")
        payload = dict(event)
        self.published.append((topic, payload))
        for pattern, callback in list(self._subs.values()):
            if topic_matches(pattern, topic):
                try:
                    await callback(topic, payload)
                except Exception:
                    logger.exception("stub subscriber failed topic=%s pattern=%s", topic, pattern)

    async def subscribe(self, pattern: str, callback: EventCallback) -> str:
        if not inspect.iscoroutinefunction(callback):
            raise TypeError("callback must be an async function")
        if self._closed:
            raise RuntimeError("EventBus is closed")
        sid = str(uuid.uuid4())
        self._subs[sid] = (pattern, callback)
        return sid

    def unsubscribe(self, subscription_id: str) -> bool:
        return self._subs.pop(subscription_id, None) is not None

    async def aclose(self) -> None:
        self._closed = True
        self._subs.clear()

    async def __aenter__(self) -> StubEventBus:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()


class StubStateManager:
    """In-memory stand-in for :class:`core.state_manager.StateManager` (no SQLite)."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        self._closed = False

    async def init_schema(self) -> None:
        if self._closed:
            raise RuntimeError("StubStateManager is closed")

    async def save_state(
        self,
        entity_id: str,
        state: dict[str, Any],
        skill_id: str,
    ) -> None:
        if self._closed:
            raise RuntimeError("StubStateManager is closed")
        _ = skill_id  # audit field reserved; mirror StateManager signature
        self._store[entity_id] = dict(state)

    async def get_state(self, entity_id: str) -> dict[str, Any] | None:
        if self._closed:
            raise RuntimeError("StubStateManager is closed")
        row = self._store.get(entity_id)
        return None if row is None else dict(row)

    async def aclose(self) -> None:
        self._closed = True
        self._store.clear()

    async def __aenter__(self) -> StubStateManager:
        await self.init_schema()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()


def _default_coverage_morfs(skill: SkillBase) -> tuple[str, ...]:
    path = Path(inspect.getfile(type(skill))).resolve()
    return (str(path),)


def _normalize_morfs(morfs: Sequence[str | Path]) -> tuple[str, ...]:
    return tuple(str(Path(p).resolve()) for p in morfs)


def _resolve_module_file(module: str) -> str:
    import importlib.util

    spec = importlib.util.find_spec(module)
    if spec is None or not spec.origin or spec.origin.endswith((".so", ".pyd")):
        raise ValueError(f"cannot resolve module {module!r} to a .py source file")
    return str(Path(spec.origin).resolve())


def _resolve_coverage_morfs(
    *,
    skill: SkillBase | None,
    coverage_morfs: Sequence[str | Path] | None,
    coverage_skill_module: str | None,
    enforce_coverage: bool,
    skill_factory: Callable[[], SkillBase] | None,
) -> tuple[str, ...]:
    if coverage_morfs is not None:
        return _normalize_morfs(coverage_morfs)
    if skill is not None:
        return _default_coverage_morfs(skill)
    if coverage_skill_module is not None:
        return (_resolve_module_file(coverage_skill_module),)
    if skill_factory is not None and enforce_coverage:
        raise ValueError(
            "with skill_factory and enforce_coverage=True, pass coverage_morfs "
            "or coverage_skill_module (e.g. 'tests.fixtures.sandbox_ok_skill')",
        )
    return ()


async def _maybe_attach_sandbox(skill: SkillBase, bus: StubEventBus, sm: StubStateManager) -> None:
    fn = getattr(skill, "attach_sandbox", None)
    if fn is None:
        return
    result = fn(bus, sm)
    if inspect.isawaitable(result):
        await result


async def run_sandbox(
    events: list[dict[str, Any]],
    *,
    skill: SkillBase | None = None,
    skill_factory: Callable[[], SkillBase] | None = None,
    coverage_threshold: float = 90.0,
    coverage_morfs: Sequence[str | Path] | None = None,
    coverage_skill_module: str | None = None,
    enforce_coverage: bool = True,
) -> SandboxReport:
    """Run ``skill.execute`` on each event under stub bus/state and optional coverage gate.

    Pass **exactly one** of ``skill`` or ``skill_factory``. Prefer ``skill_factory`` when
    ``enforce_coverage`` is True so the Skill module is first imported after tracing
    starts (otherwise module-level lines are often marked missed and the 90% gate fails).
    If that module was already imported elsewhere in the process, ``import`` is a cache
    hit and the per-file percentage can drop spuriously—use a fresh process or a module
    not yet loaded.

    * Calls :meth:`SkillBase.validate_skill` on ``skill.meta``.
    * Builds :class:`StubEventBus` / :class:`StubStateManager`. If the skill defines
      ``attach_sandbox(self, bus, state)`` (sync or async), it is invoked before events.
    * Coverage uses ``coverage`` with ``config_file=False`` so ``pyproject`` ``source=``
      does not override ``include=``. By default (``skill`` path), only the file
      containing the skill class is reported.

    :param enforce_coverage: if False, skip coverage collection and report ``coverage_percent=100.0``.
    :raises CoverageError: when ``enforce_coverage`` and measured coverage < ``coverage_threshold``.
    """
    if (skill is None) == (skill_factory is None):
        raise ValueError("pass exactly one of skill or skill_factory")

    used_premade_instance = skill is not None

    morfs = _resolve_coverage_morfs(
        skill=skill,
        coverage_morfs=coverage_morfs,
        coverage_skill_module=coverage_skill_module,
        enforce_coverage=enforce_coverage,
        skill_factory=skill_factory,
    )

    cases: list[SandboxCaseResult] = []
    cov: Any = None
    pct = 100.0

    if enforce_coverage:
        if not morfs:
            raise ValueError("coverage morfs resolved empty; pass coverage_morfs or coverage_skill_module")
        try:
            from coverage import Coverage
        except ImportError as e:
            raise RuntimeError(
                "coverage package is required when enforce_coverage=True",
            ) from e
        cov = Coverage(
            data_suffix=True,
            config_file=False,
            include=list(morfs),
        )
        cov.start()

    if skill_factory is not None:
        skill = skill_factory()
    assert skill is not None

    SkillBase.validate_skill(skill.meta)

    bus = StubEventBus()
    sm = StubStateManager()
    await _maybe_attach_sandbox(skill, bus, sm)

    if used_premade_instance:
        logger.warning(
            "run_sandbox: prefer skill_factory=... so the skill module loads under the "
            "coverage tracer; premade skill instances often under-report file coverage.",
        )

    passed = 0
    failed = 0
    try:
        for i, event in enumerate(events):
            try:
                out = await skill.execute(dict(event))
                if not isinstance(out, dict):
                    raise TypeError(f"execute must return dict, got {type(out)!r}")
                cases.append(SandboxCaseResult(index=i, event=dict(event), ok=True, result=out))
                passed += 1
            except Exception as e:
                logger.exception("sandbox case %s failed", i)
                cases.append(
                    SandboxCaseResult(
                        index=i,
                        event=dict(event),
                        ok=False,
                        error=f"{type(e).__name__}: {e}",
                    ),
                )
                failed += 1
    finally:
        if cov is not None:
            cov.stop()
            cov.save()
            buf = io.StringIO()
            pct = cov.report(morfs=list(morfs), file=buf, precision=4)

    display_morfs = morfs if morfs else _default_coverage_morfs(skill)
    report = SandboxReport(
        coverage_percent=float(pct),
        coverage_morfs=display_morfs,
        coverage_threshold=coverage_threshold,
        passed=passed,
        failed=failed,
        cases=cases,
        event_bus=bus,
        state_manager=sm,
    )

    if enforce_coverage and report.coverage_percent < coverage_threshold:
        raise CoverageError(report.coverage_percent, coverage_threshold, report)

    return report
