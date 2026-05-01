"""``python-dotenv`` integration (``load_repo_dotenv``)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import config.settings as settings


def test_load_repo_dotenv_reads_repo_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZHIWEITONG_SKIP_DOTENV", raising=False)
    for k in list(os.environ):
        if k.startswith("ZHIWEITONG_"):
            monkeypatch.delenv(k, raising=False)

    (tmp_path / ".env").write_text(
        "ZHIWEITONG_LLM_API_KEY=from-dotenv-file\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "REPO_ROOT", tmp_path)

    settings.load_repo_dotenv()
    assert os.environ.get("ZHIWEITONG_LLM_API_KEY") == "from-dotenv-file"


def test_load_repo_dotenv_respects_existing_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZHIWEITONG_SKIP_DOTENV", raising=False)
    monkeypatch.setenv("ZHIWEITONG_LLM_API_KEY", "from-shell")
    (tmp_path / ".env").write_text(
        "ZHIWEITONG_LLM_API_KEY=from-dotenv-file\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "REPO_ROOT", tmp_path)

    settings.load_repo_dotenv()
    assert os.environ.get("ZHIWEITONG_LLM_API_KEY") == "from-shell"
