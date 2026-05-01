"""Core runtime: event bus, state, orchestrator, skills base (Phase 0+)."""

from core.event_bus import EventBus, topic_matches
from core.org_tree import REQUIRED_PREFIX, OrgTree
from core.orchestrator import (
    GoalReport,
    Orchestrator,
    PlanStep,
    command_topic,
    result_topic,
)
from core.skill_base import (
    AI_CEO,
    SkillBase,
    SkillMeta,
    json_schema,
    minimal_skill_meta,
)
from core.sandbox import (
    CoverageError,
    SandboxReport,
    StubEventBus,
    StubStateManager,
    run_sandbox,
)
from core.skill_registry import SkillRegistry
from core.state_manager import StateManager

__all__ = [
    "AI_CEO",
    "CoverageError",
    "EventBus",
    "KnowledgeStore",
    "GoalReport",
    "Orchestrator",
    "OrgTree",
    "PlanStep",
    "REQUIRED_PREFIX",
    "command_topic",
    "SandboxReport",
    "SkillBase",
    "SkillRegistry",
    "SkillMeta",
    "StateManager",
    "StubEventBus",
    "StubStateManager",
    "json_schema",
    "minimal_skill_meta",
    "result_topic",
    "run_sandbox",
    "topic_matches",
]


def __getattr__(name: str):
    if name == "KnowledgeStore":
        from core.knowledge_store import KnowledgeStore

        return KnowledgeStore
    if name in (
        "AUDIT_SKILL_ID",
        "AUDIT_SKILL_ORG_PATH",
        "EvolutionEngine",
        "EvolutionPromotion",
        "EvolutionProposal",
        "EvolutionThresholds",
        "SkillCommandGateway",
        "merge_execution_patch",
        "resolve_skill_for_command_topic",
    ):
        if name in ("SkillCommandGateway", "resolve_skill_for_command_topic"):
            import core.skill_command_gateway as scg

            return getattr(scg, name)
        if name == "EvolutionPromotion":
            from core.evolution_promotion import EvolutionPromotion

            return EvolutionPromotion
        import core.evolution as evo

        return getattr(evo, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
