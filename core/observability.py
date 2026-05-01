"""可观测性约定：编排与集成组件在 ``logging.LogRecord`` 上挂载 ``zt_*`` 字段。

便于日志平台按 ``zt_goal_run_id`` 关联单次 ``process_goal``、按 ``zt_correlation_id``
关联总线消息。字段名使用 ``zt_`` 前缀，避免与 :class:`logging.LogRecord` 保留属性冲突。

环境变量 ``ZHIWEITONG_LOG_JSON=1`` 时，``configure_zhiweitong_logging()`` 为根 logger
增加一行一条 JSON 的 stderr 处理器（便于 Loki / Datadog 等采集）。
编排器还可选写 ``zt_outcome``、``zt_duration_ms``（见 ``docs/ops-runbook.md``）。

详见 ``docs/ops-runbook.md``「日志字段」。
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

# 与文档、采集规则对齐的稳定键名
ZT_GOAL_RUN_ID = "zt_goal_run_id"
ZT_STEP_INDEX = "zt_step_index"
ZT_CORRELATION_ID = "zt_correlation_id"
ZT_SKILL_ID = "zt_skill_id"
ZT_COMPONENT = "zt_component"
ZT_OUTCOME = "zt_outcome"
ZT_DURATION_MS = "zt_duration_ms"
ZT_BUS_CHANNEL = "zt_bus_channel"
ZT_SUBSCRIPTION_ID = "zt_subscription_id"
ZT_TOPIC = "zt_topic"

LOG_JSON_ENV = "ZHIWEITONG_LOG_JSON"

_logging_configure_done = False


def _truthy_env(val: str | None) -> bool:
    if val is None:
        return False
    return val.strip().lower() in {"1", "true", "yes", "on"}


class ZhiweitongJsonFormatter(logging.Formatter):
    """单行 JSON：``ts`` / ``level`` / ``logger`` / ``message``，以及 ``LogRecord`` 上所有 ``zt_*``。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key, val in record.__dict__.items():
            if key.startswith("zt_"):
                payload[key] = val
        return json.dumps(payload, ensure_ascii=False, default=str) + "\n"


def configure_zhiweitong_logging(*, force: bool = False) -> None:
    """若 ``ZHIWEITONG_LOG_JSON`` 为真，为根 logger 挂载 JSON stderr 处理器（幂等）。

    在 ``load_settings()`` 与 CLI 入口调用；嵌入方也可在启动早期显式调用。
    未开启 JSON 时仅标记已检查，不改变现有 logging 配置。
    """
    global _logging_configure_done
    if _logging_configure_done and not force:
        return

    if not _truthy_env(os.environ.get(LOG_JSON_ENV)):
        _logging_configure_done = True
        return

    root = logging.getLogger()
    for h in list(root.handlers):
        if getattr(h, "_zhiweitong_json", False):
            root.removeHandler(h)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(ZhiweitongJsonFormatter())
    handler._zhiweitong_json = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    if root.level > logging.INFO or root.level == logging.NOTSET:
        root.setLevel(logging.INFO)
    _logging_configure_done = True


def zt_log_extra(
    *,
    goal_run_id: str | None = None,
    step_index: int | None = None,
    correlation_id: str | None = None,
    skill_id: str | None = None,
    component: str | None = None,
    outcome: str | None = None,
    duration_ms: float | int | None = None,
    bus_channel: str | None = None,
    subscription_id: str | None = None,
    topic: str | None = None,
) -> dict[str, Any]:
    """构造 ``logger.*(..., extra=...)`` 用的字典；未传的键不出现。"""
    d: dict[str, Any] = {}
    if goal_run_id is not None:
        d[ZT_GOAL_RUN_ID] = goal_run_id
    if step_index is not None:
        d[ZT_STEP_INDEX] = step_index
    if correlation_id is not None:
        d[ZT_CORRELATION_ID] = correlation_id
    if skill_id is not None:
        d[ZT_SKILL_ID] = skill_id
    if component is not None:
        d[ZT_COMPONENT] = component
    if outcome is not None:
        d[ZT_OUTCOME] = outcome
    if duration_ms is not None:
        d[ZT_DURATION_MS] = int(round(float(duration_ms)))
    if bus_channel is not None:
        d[ZT_BUS_CHANNEL] = bus_channel
    if subscription_id is not None:
        d[ZT_SUBSCRIPTION_ID] = subscription_id
    if topic is not None:
        d[ZT_TOPIC] = topic
    return d
