"""Pytest defaults: isolate from developer ``.env`` unless a test clears ``ZHIWEITONG_SKIP_DOTENV``."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _zhiweitong_skip_dotenv_for_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZHIWEITONG_SKIP_DOTENV", "1")
