"""Evolution engine: subscribe to ``/system/errors``, thresholded auto-optimization loop (Phase 3.2).

Human audit remains mandatory: successful sandbox runs publish an optimization review to
``/system/evolution/review``; execution metadata is not mutated until an external approver
applies patches (see :func:`merge_execution_patch`).
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import deque
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from core.event_bus import EventBus
from core.observability import zt_log_extra
from core.knowledge_store import KnowledgeStore
from core.orchestrator import command_topic
from core.sandbox import SandboxReport, run_sandbox
from core.skill_base import SkillBase, SkillExecution, SkillMeta
from core.skill_registry import SkillRegistry
from shared.models import EventEnvelope
from shared.system_topics import EVOLUTION_REVIEW, SYSTEM_ERRORS

logger = logging.getLogger(__name__)

# Keep in sync with ``skills.general_office.audit_review.ORG_PATH``.
AUDIT_SKILL_ORG_PATH = "/智维通/城市乳业/总经办/审计审核岗"
AUDIT_SKILL_ID = "gov_audit_review"


@dataclass
class EvolutionThresholds:
    """Rolling-window rules derived from ``/system/errors`` traffic."""

    window_sec: float = 120.0
    min_errors_in_window: int = 3
    max_latency_ms: float | None = 10_000.0


@dataclass
class EvolutionProposal:
    """Suggested changes to :class:`SkillExecution` (LLM or rules engine)."""

    rationale: str
    execution_patch: dict[str, Any] = field(default_factory=dict)


class EvolutionOptimizer(Protocol):
    async def propose(
        self,
        *,
        skill_id: str,
        org_path: str,
        error_events: list[dict[str, Any]],
    ) -> EvolutionProposal: ...


class _StubOptimizer:
    """Deterministic optimizer for tests and offline runs."""

    async def propose(
        self,
        *,
        skill_id: str,
        org_path: str,
        error_events: list[dict[str, Any]],
    ) -> EvolutionProposal:
        n = len(error_events)
        return EvolutionProposal(
            rationale=f"stub: aggregated {n} error(s) for {skill_id}",
            execution_patch={
                "decision_rule": f"stub_recovered_rule:{skill_id}",
            },
        )


def merge_execution_patch(meta: SkillMeta, patch: Mapping[str, Any]) -> SkillMeta:
    """Return a copy of ``meta`` with :class:`SkillExecution` fields shallow-merged from ``patch``."""
    allowed = {"workflow_steps", "decision_rule", "token_budget", "api_call_budget"}
    ex = meta.execution.model_dump()
    for k, v in patch.items():
        if k in allowed:
            ex[k] = v
    return meta.model_copy(update={"execution": SkillExecution(**ex)})


RegressionRunner = Callable[
    [type[SkillBase], dict[str, Any], Sequence[dict[str, Any]]],
    Awaitable[tuple[bool, SandboxReport | None]],
]


async def _default_regression(
    skill_cls: type[SkillBase],
    execution_patch: dict[str, Any],
    cases: Sequence[dict[str, Any]],
) -> tuple[bool, SandboxReport | None]:
    """Run :func:`run_sandbox` when ``cases`` is non-empty; else accept."""
    if not cases:
        return True, None
    patched_meta = merge_execution_patch(skill_cls.META, execution_patch)

    class _Patched(skill_cls):  # type: ignore[misc, valid-type]
        META = patched_meta

    report = await run_sandbox(
        list(cases),
        skill_factory=lambda: _Patched(),
        enforce_coverage=False,
    )
    ok = report.failed == 0
    return ok, report


class EvolutionEngine:
    """Subscribe to ``/system/errors``, propose optimizations, optional sandbox, publish review."""

    def __init__(
        self,
        *,
        bus: EventBus,
        knowledge: KnowledgeStore,
        registry: SkillRegistry,
        thresholds: EvolutionThresholds | None = None,
        optimizer: EvolutionOptimizer | None = None,
        regression: RegressionRunner | None = None,
        audit_org_path: str = AUDIT_SKILL_ORG_PATH,
        review_cooldown_sec: float = 300.0,
        historical_cases: dict[str, list[dict[str, Any]]] | None = None,
    ) -> None:
        self._bus = bus
        self._knowledge = knowledge
        self._registry = registry
        self._thresholds = thresholds or EvolutionThresholds()
        self._optimizer = optimizer or _StubOptimizer()
        self._regression = regression or _default_regression
        self._audit_org_path = audit_org_path
        self._review_cooldown_sec = review_cooldown_sec
        self._historical_cases = historical_cases or {}

        self._sub_id: str | None = None
        self._locks: dict[str, asyncio.Lock] = {}
        self._samples: dict[str, deque[tuple[float, dict[str, Any]]]] = {}
        self._last_review_mono: dict[str, float] = {}

    async def start(self) -> str:
        if self._sub_id is not None:
            return self._sub_id

        async def _cb(topic: str, event: dict[str, Any]) -> None:
            asyncio.create_task(self._handle_error_event(event))

        self._sub_id = await self._bus.subscribe(SYSTEM_ERRORS, _cb)
        logger.info("EvolutionEngine subscribed %s id=%s", SYSTEM_ERRORS, self._sub_id)
        return self._sub_id

    async def stop(self) -> None:
        if self._sub_id is not None:
            self._bus.unsubscribe(self._sub_id)
            self._sub_id = None

    def _lock_for(self, skill_id: str) -> asyncio.Lock:
        if skill_id not in self._locks:
            self._locks[skill_id] = asyncio.Lock()
        return self._locks[skill_id]

    def _prune_samples(self, skill_id: str, now: float) -> deque[tuple[float, dict[str, Any]]]:
        dq = self._samples.setdefault(skill_id, deque(maxlen=256))
        cutoff = now - self._thresholds.window_sec
        while dq and dq[0][0] < cutoff:
            dq.popleft()
        return dq

    def _thresholds_met(self, skill_id: str, payload: dict[str, Any], now: float) -> bool:
        dq = self._prune_samples(skill_id, now)
        if len(dq) >= self._thresholds.min_errors_in_window:
            return True
        lat = payload.get("latency_ms")
        if (
            self._thresholds.max_latency_ms is not None
            and isinstance(lat, (int, float))
            and float(lat) >= self._thresholds.max_latency_ms
        ):
            return True
        return False

    async def _handle_error_event(self, event: dict[str, Any]) -> None:
        skill_id = str(event.get("skill_id") or "")
        org_path = str(event.get("org_path") or "")
        if not skill_id or not org_path:
            logger.debug("evolution skip: missing skill_id/org_path in %s", event)
            return

        payload = dict(event.get("payload") or {})
        now = time.monotonic()
        dq = self._prune_samples(skill_id, now)
        dq.append((now, dict(payload)))

        if not self._thresholds_met(skill_id, payload, now):
            return

        last = self._last_review_mono.get(skill_id, 0.0)
        if now - last < self._review_cooldown_sec:
            return

        async with self._lock_for(skill_id):
            now2 = time.monotonic()
            last2 = self._last_review_mono.get(skill_id, 0.0)
            if now2 - last2 < self._review_cooldown_sec:
                return
            if not self._thresholds_met(skill_id, payload, now2):
                return
            self._last_review_mono[skill_id] = now2
            try:
                await self._run_evolution_pipeline(skill_id, org_path, event)
            finally:
                self._samples.get(skill_id, deque()).clear()

    async def _run_evolution_pipeline(
        self,
        skill_id: str,
        org_path: str,
        last_event: dict[str, Any],
    ) -> None:
        dq = self._samples.get(skill_id, deque())
        error_events = [dict(e) for _, e in dq]

        proposal = await self._optimizer.propose(
            skill_id=skill_id,
            org_path=org_path,
            error_events=error_events,
        )

        cases = self._historical_cases.get(skill_id, [])
        skill_cls: type[SkillBase] | None = None
        try:
            skill_cls = type(self._registry.get_skill(skill_id))
        except Exception:
            _lcid = last_event.get("correlation_id")
            logger.warning(
                "evolution: skill %s not in registry; sandbox skipped",
                skill_id,
                extra=zt_log_extra(
                    component="evolution_engine",
                    outcome="skill_not_in_registry",
                    skill_id=skill_id,
                    correlation_id=str(_lcid) if _lcid is not None else None,
                ),
            )

        sandbox_ok = True
        report: SandboxReport | None = None
        if skill_cls is not None:
            sandbox_ok, report = await self._regression(
                skill_cls,
                proposal.execution_patch,
                cases,
            )

        kb_body = (
            f"Evolution pipeline for {skill_id}\n"
            f"org_path={org_path}\n"
            f"rationale={proposal.rationale}\n"
            f"patch={proposal.execution_patch!r}\n"
            f"sandbox_ok={sandbox_ok}\n"
            f"last_correlation_id={last_event.get('correlation_id')!r}\n"
        )
        case_id = await self._knowledge.store(
            ["evolution", "case_study", skill_id],
            kb_body,
            {
                "kind": "evolution_case",
                "skill_id": skill_id,
                "sandbox_ok": sandbox_ok,
                "patch": proposal.execution_patch,
            },
            org_path=org_path,
        )

        if not sandbox_ok:
            logger.info(
                "evolution: sandbox failed skill_id=%s case_id=%s report=%s",
                skill_id,
                case_id,
                report,
            )
            return

        merged_preview = None
        if skill_cls is not None:
            merged_preview = merge_execution_patch(skill_cls.META, proposal.execution_patch).model_dump()

        review = EventEnvelope(
            correlation_id=str(uuid.uuid4()),
            org_path=self._audit_org_path,
            skill_id=AUDIT_SKILL_ID,
            payload={
                "kind": "optimization_review",
                "target_skill_id": skill_id,
                "target_org_path": org_path,
                "knowledge_doc_id": case_id,
                "proposed_execution_patch": proposal.execution_patch,
                "proposed_meta_preview": merged_preview,
                "rationale": proposal.rationale,
                "sandbox_ok": True,
                "message": "pending_human_approval",
            },
        )
        await self._bus.publish(EVOLUTION_REVIEW, review.model_dump())
        cmd = EventEnvelope(
            correlation_id=review.correlation_id,
            org_path=self._audit_org_path,
            skill_id=AUDIT_SKILL_ID,
            payload={
                "action": "optimization_review",
                "params": {"review": dict(review.payload)},
            },
        )
        await self._bus.publish(command_topic(self._audit_org_path), cmd.model_dump())
        logger.info("evolution: published optimization_review skill_id=%s doc=%s", skill_id, case_id)
