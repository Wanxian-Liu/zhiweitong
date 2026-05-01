"""Normalize Orchestrator ``command`` envelope payloads for Skill domain logic."""

from __future__ import annotations

from typing import Any


def effective_skill_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Orchestrator publishes ``payload`` shaped like::

        {"action": str, "params": {...}, "plan_id": str, "step_index": int}

    Sandbox tests often pass a **flat** ``payload`` (business fields only).

    Merge ``params`` onto the outer dict so ``.get("demand_units")`` etc. work in both modes.
    Outer keys still present (e.g. ``action``, ``plan_id``) for skills that need them.
    """
    p = dict(payload)
    inner = p.get("params")
    if isinstance(inner, dict):
        return {**p, **inner}
    return p
