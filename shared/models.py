"""Pydantic models shared across zhiweitong (event envelopes to be expanded in Phase 0)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EventEnvelope(BaseModel):
    """Minimal event envelope; extend per docs/event_topics.md."""

    schema_version: str = Field(default="1")
    correlation_id: str
    org_path: str
    skill_id: str
    payload: dict = Field(default_factory=dict)
