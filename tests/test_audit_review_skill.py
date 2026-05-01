"""审计审核岗 Skill 沙盒测试。"""

from __future__ import annotations

import asyncio

from core.sandbox import run_sandbox
from shared.system_topics import EVOLUTION_APPROVED, EVOLUTION_REJECTED

_AUDIT_ORG = "/智维通/城市乳业/总经办/审计审核岗"
_AUDIT_SID = "gov_audit_review"


def _env(correlation_id: str, payload: dict) -> dict:
    return {
        "schema_version": "1",
        "correlation_id": correlation_id,
        "org_path": _AUDIT_ORG,
        "skill_id": _AUDIT_SID,
        "payload": payload,
    }


def test_audit_review_optimization_pending_by_default() -> None:
    async def _run() -> None:
        def factory():
            from skills.general_office.audit_review import AuditReviewSkill

            return AuditReviewSkill()

        review = {
            "kind": "optimization_review",
            "target_skill_id": "leaf_qc",
            "knowledge_doc_id": "doc-1",
            "proposed_execution_patch": {"decision_rule": "x"},
        }
        rep = await run_sandbox(
            [
                _env(
                    "a1",
                    {
                        "action": "optimization_review",
                        "params": {"review": review},
                    },
                ),
            ],
            skill_factory=factory,
            enforce_coverage=False,
        )
        assert rep.passed == 1 and rep.failed == 0
        r0 = rep.cases[0].result
        assert r0 is not None
        assert r0["verdict"] == "pending_human"
        assert r0["summary"]["target_skill_id"] == "leaf_qc"
        bus = rep.event_bus
        assert bus is not None
        published = [t for t, _ in bus.published if str(t).endswith("/result")]
        assert len(published) == 1
        sys_topics = [t for t, _ in bus.published if t in (EVOLUTION_APPROVED, EVOLUTION_REJECTED)]
        assert sys_topics == []

    asyncio.run(_run())


def test_audit_review_reviewer_reject() -> None:
    async def _run() -> None:
        def factory():
            from skills.general_office.audit_review import AuditReviewSkill

            return AuditReviewSkill()

        review = {
            "kind": "optimization_review",
            "target_skill_id": "x",
            "knowledge_doc_id": "d",
        }
        rep = await run_sandbox(
            [
                _env(
                    "a2",
                    {
                        "action": "optimization_review",
                        "params": {"review": review, "reviewer_decision": "reject"},
                    },
                ),
            ],
            skill_factory=factory,
            enforce_coverage=False,
        )
        assert rep.cases[0].result is not None
        assert rep.cases[0].result["verdict"] == "rejected"
        bus = rep.event_bus
        assert bus is not None
        rej = [(t, e) for t, e in bus.published if t == EVOLUTION_REJECTED]
        assert len(rej) == 1
        assert rej[0][1]["payload"]["target_skill_id"] == "x"

    asyncio.run(_run())


def test_audit_review_reviewer_approve_publishes_system_topic() -> None:
    async def _run() -> None:
        def factory():
            from skills.general_office.audit_review import AuditReviewSkill

            return AuditReviewSkill()

        review = {
            "kind": "optimization_review",
            "target_skill_id": "leaf_qc",
            "knowledge_doc_id": "doc-9",
            "proposed_execution_patch": {"decision_rule": "v2"},
            "proposed_meta_preview": {"execution": {"decision_rule": "v2"}},
        }
        rep = await run_sandbox(
            [
                _env(
                    "a3",
                    {
                        "action": "optimization_review",
                        "params": {"review": review, "reviewer_decision": "approve"},
                    },
                ),
            ],
            skill_factory=factory,
            enforce_coverage=False,
        )
        assert rep.cases[0].result is not None
        assert rep.cases[0].result["verdict"] == "approved"
        bus = rep.event_bus
        assert bus is not None
        app = [(t, e) for t, e in bus.published if t == EVOLUTION_APPROVED]
        assert len(app) == 1
        pl = app[0][1]["payload"]
        assert pl["decision"] == "approved"
        assert pl["target_skill_id"] == "leaf_qc"
        assert pl["proposed_execution_patch"] == {"decision_rule": "v2"}

    asyncio.run(_run())
