"""Tests for :func:`core.command_payload.effective_skill_payload`."""

from __future__ import annotations

from core.command_payload import effective_skill_payload


def test_effective_payload_flat_sandbox_style() -> None:
    p = {"demand_units": 50, "line_id": "L1"}
    assert effective_skill_payload(p) == p


def test_effective_payload_orchestrator_wraps_params() -> None:
    p = {
        "action": "schedule",
        "params": {"demand_units": 50, "line_id": "L1"},
        "plan_id": "pid",
        "step_index": 0,
    }
    out = effective_skill_payload(p)
    assert out["demand_units"] == 50
    assert out["line_id"] == "L1"
    assert out["action"] == "schedule"
    assert out["plan_id"] == "pid"
