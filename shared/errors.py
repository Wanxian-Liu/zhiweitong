"""Unified error codes for zhiweitong (expand with domain errors in Phase 1)."""

from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "E_VALIDATION"
    INTERNAL_ERROR = "E_INTERNAL"
