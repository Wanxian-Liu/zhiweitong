"""AI 总经理 Orchestrator — OpenCLAW Phase 1.2.

Publishes work to Skills via :class:`core.event_bus.EventBus` only; never calls
:class:`core.skill_base.SkillBase.execute` directly.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import httpx
from pydantic import BaseModel, Field

from config.settings import Settings, load_settings
from core.event_bus import EventBus
from core.org_tree import OrgTree
from core.skill_base import SkillBase
from core.skill_registry import SkillRegistry
from core.state_manager import StateManager
from shared.models import EventEnvelope

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1"
ABORT_ON_FAILURE_OPS = frozenset({"abort_on_failure", "strict"})


class PlanStep(BaseModel):
    """One orchestration step from the LLM (or test provider)."""

    model_config = {"extra": "forbid"}

    skill_path: str = Field(..., description="Target org_path for a registered Skill")
    action: str = Field(..., min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)


class PlanPayload(BaseModel):
    model_config = {"extra": "forbid"}

    steps: list[PlanStep] = Field(default_factory=list)


@runtime_checkable
class KnowledgeStoreLike(Protocol):
    async def store(
        self,
        tags: list[str],
        content: str,
        metadata: dict[str, Any],
        *,
        org_path: str | None = None,
    ) -> str: ...


PlanProvider = Callable[[str], Awaitable[list[PlanStep]]]


def _extract_json_object(text: str) -> Any:
    t = text.strip()
    if t.startswith("```"):
        lines = t.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return json.loads(t)


def command_topic(org_path: str) -> str:
    p = org_path.rstrip("/") or "/"
    return f"{p}/command"


def result_topic(org_path: str) -> str:
    p = org_path.rstrip("/") or "/"
    return f"{p}/result"


@dataclass
class StepRunRecord:
    skill_path: str
    skill_id: str
    action: str
    correlation_id: str
    duration_ms: float
    ok: bool
    error: str | None = None
    summary: dict[str, Any] = field(default_factory=dict)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


@dataclass
class GoalReport:
    goal_text: str
    plan_id: str
    ok: bool
    steps: list[StepRunRecord]
    aggregated: dict[str, Any]
    planner_attempts: int = 0
    planner_error: str | None = None


class Orchestrator:
    """Coordinates goals → LLM plan → EventBus command/result rounds."""

    def __init__(
        self,
        event_bus: EventBus,
        state_manager: StateManager,
        skill_registry: SkillRegistry,
        knowledge_store: KnowledgeStoreLike,
        org_tree: OrgTree,
        *,
        settings: Settings | None = None,
        llm_model: str = "gpt-4o-mini",
        step_timeout: float = 60.0,
        http_client: httpx.AsyncClient | None = None,
        plan_provider: PlanProvider | None = None,
        own_http_client: bool = False,
    ) -> None:
        self._bus = event_bus
        self._state = state_manager
        self._registry = skill_registry
        self._knowledge = knowledge_store
        self._org_tree = org_tree
        self._settings = settings or load_settings()
        self._llm_model = llm_model
        self._step_timeout = step_timeout
        self._http = http_client
        self._own_http = own_http_client
        self._plan_provider = plan_provider

    async def aclose(self) -> None:
        if self._own_http and self._http is not None:
            await self._http.aclose()
            self._http = None

    async def __aenter__(self) -> Orchestrator:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    def _resolve_skill(self, skill_path: str) -> SkillBase:
        skill_path = skill_path.strip()
        if not skill_path.startswith("/"):
            skill_path = "/" + skill_path
        candidates = self._registry.find_by_org_path(skill_path)
        exact = [s for s in candidates if s.meta.org_path.rstrip("/") == skill_path.rstrip("/")]
        if not exact:
            raise ValueError(f"no Skill registered at org_path {skill_path!r}")
        if len(exact) > 1:
            ids = [s.meta.skill_id for s in exact]
            raise ValueError(f"ambiguous Skill at {skill_path!r}: {ids}")
        return exact[0]

    def _abort_on_failure(self, skill: SkillBase) -> bool:
        forbidden = skill.meta.compliance.forbidden_operations
        return bool(ABORT_ON_FAILURE_OPS & set(forbidden))

    async def _build_plan(self, goal_text: str) -> tuple[list[PlanStep], int, str | None]:
        if self._plan_provider is not None:
            steps = await self._plan_provider(goal_text)
            return steps, 1, None
        key = self._settings.llm_api_key
        if not key:
            return (
                [],
                0,
                "LLM API key missing (ZHIWEITONG_LLM_API_KEY); "
                "set it or pass plan_provider= for tests",
            )
        last_err: str | None = None
        for attempt in range(3):
            try:
                steps = await self._call_llm_planner(goal_text)
                return steps, attempt + 1, None
            except Exception as e:
                last_err = f"{type(e).__name__}: {e}"
                logger.warning("planner attempt %s failed: %s", attempt + 1, last_err)
        return [], 3, last_err

    async def _call_llm_planner(self, goal_text: str) -> list[PlanStep]:
        base = self._settings.llm_base_url.rstrip("/")
        url = f"{base}/chat/completions"
        system = (
            "You output only valid JSON. Schema: "
            '{"steps":[{"skill_path":"/智维通/城市乳业/...","action":"verb","params":{}}]} '
            "skill_path must be a full org_path. steps may be empty if impossible."
        )
        body: dict[str, Any] = {
            "model": self._llm_model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": goal_text},
            ],
        }
        client = self._http
        created_here = False
        if client is None:
            client = httpx.AsyncClient(timeout=120.0)
            created_here = True
        try:
            r = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {self._settings.llm_api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            if isinstance(content, str):
                text = content.strip()
            else:
                text = json.dumps(content)
            parsed = _extract_json_object(text)
            plan = PlanPayload.model_validate(parsed)
            return plan.steps
        finally:
            if created_here:
                await client.aclose()

    async def process_goal(self, goal_text: str) -> GoalReport:
        """Plan via LLM (or ``plan_provider``), dispatch commands, aggregate results."""
        plan_id = str(uuid.uuid4())
        steps_plan, planner_attempts, planner_err = await self._build_plan(goal_text)
        records: list[StepRunRecord] = []
        aggregated: dict[str, Any] = {"plan_id": plan_id, "summaries": []}

        if planner_err and not steps_plan:
            return GoalReport(
                goal_text=goal_text,
                plan_id=plan_id,
                ok=False,
                steps=[],
                aggregated=aggregated,
                planner_attempts=planner_attempts,
                planner_error=planner_err,
            )

        pending: dict[str, asyncio.Future[dict[str, Any]]] = {}

        async def on_result(topic: str, event: dict[str, Any]) -> None:
            if not str(topic).endswith("/result"):
                return
            cid = str(event.get("correlation_id", ""))
            fut = pending.get(cid)
            if fut is not None and not fut.done():
                fut.set_result(dict(event))

        sub_id = await self._bus.subscribe("/智维通/城市乳业*", on_result)

        ok_all = True
        try:
            for idx, step in enumerate(steps_plan):
                skill = self._resolve_skill(step.skill_path)
                cid = str(uuid.uuid4())
                env = EventEnvelope(
                    correlation_id=cid,
                    org_path=skill.meta.org_path,
                    skill_id=skill.meta.skill_id,
                    payload={
                        "action": step.action,
                        "params": step.params,
                        "plan_id": plan_id,
                        "step_index": idx,
                    },
                )
                entity = f"orchestrator/{plan_id}/{idx}"
                await self._state.save_state(
                    entity,
                    {"status": "dispatched", "envelope": env.model_dump()},
                    skill_id="orchestrator",
                )

                loop = asyncio.get_running_loop()
                fut: asyncio.Future[dict[str, Any]] = loop.create_future()
                pending[cid] = fut
                t0 = time.perf_counter()
                cmd_topic = command_topic(skill.meta.org_path)
                await self._bus.publish(cmd_topic, env.model_dump())
                logger.info(
                    "orchestrator published command topic=%s correlation_id=%s plan_id=%s",
                    cmd_topic,
                    cid,
                    plan_id,
                )

                err: str | None = None
                summary: dict[str, Any] = {}
                step_ok = True
                try:
                    result_event = await asyncio.wait_for(fut, timeout=self._step_timeout)
                    payload = result_event.get("payload") or {}
                    if payload.get("ok") is False:
                        step_ok = False
                        err = str(payload.get("error") or "skill reported ok=false")
                    summary = dict(payload.get("summary") or {})
                except TimeoutError:
                    step_ok = False
                    err = "step_timeout"
                except Exception as e:
                    step_ok = False
                    err = f"{type(e).__name__}: {e}"
                finally:
                    pending.pop(cid, None)
                    dt_ms = (time.perf_counter() - t0) * 1000.0

                rec = StepRunRecord(
                    skill_path=step.skill_path,
                    skill_id=skill.meta.skill_id,
                    action=step.action,
                    correlation_id=cid,
                    duration_ms=dt_ms,
                    ok=step_ok,
                    error=err,
                    summary=summary,
                )
                records.append(rec)
                if summary:
                    aggregated["summaries"].append(
                        {"skill_id": skill.meta.skill_id, "summary": summary},
                    )

                await self._state.save_state(
                    entity,
                    {
                        "status": "completed" if step_ok else "failed",
                        "record": {
                            "skill_path": rec.skill_path,
                            "skill_id": rec.skill_id,
                            "action": rec.action,
                            "correlation_id": rec.correlation_id,
                            "duration_ms": rec.duration_ms,
                            "ok": rec.ok,
                            "error": rec.error,
                            "summary": rec.summary,
                            "prompt_tokens": rec.prompt_tokens,
                            "completion_tokens": rec.completion_tokens,
                        },
                    },
                    skill_id="orchestrator",
                )

                logger.info(
                    "orchestrator step idx=%s skill_id=%s ok=%s duration_ms=%.1f err=%s",
                    idx,
                    skill.meta.skill_id,
                    step_ok,
                    dt_ms,
                    err,
                )

                if not step_ok:
                    ok_all = False
                    if self._abort_on_failure(skill):
                        break
        finally:
            self._bus.unsubscribe(sub_id)

        return GoalReport(
            goal_text=goal_text,
            plan_id=plan_id,
            ok=ok_all and planner_err is None,
            steps=records,
            aggregated=aggregated,
            planner_attempts=planner_attempts,
            planner_error=planner_err,
        )

    async def trigger_evolution(self, skill_id: str) -> str:
        """Draft evolution notes into knowledge store and notify review topic."""
        skill = self._registry.get_skill(skill_id)
        body = (
            f"Skill {skill_id} ({skill.meta.name}) flagged for evolution / human review.\n"
            f"org_path={skill.meta.org_path}\n"
            "Suggested next: review metrics, update prompts or knowledge entries."
        )
        doc_id = await self._knowledge.store(
            ["evolution", skill_id],
            body,
            {"kind": "evolution_draft", "skill_id": skill_id},
            org_path=skill.meta.org_path,
        )
        review = EventEnvelope(
            correlation_id=str(uuid.uuid4()),
            org_path=skill.meta.org_path,
            skill_id=skill_id,
            payload={"knowledge_doc_id": doc_id, "message": "evolution_review_pending"},
        )
        await self._bus.publish("/system/evolution/review", review.model_dump())
        logger.info("orchestrator trigger_evolution skill_id=%s doc_id=%s", skill_id, doc_id)
        return doc_id
