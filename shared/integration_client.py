"""L3 外部集成：HTTP GET + 超时、有限重试、Idempotency-Key。

供垂直切片内 Skill 调用 WMS/ERP 等只读查询；失败时由调用方回退到 payload 内本地字段。
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from collections.abc import Mapping
from typing import Any

import httpx

# 重试间隔（秒），避免打爆对端；单测可用 mock 无影响。
_RETRY_BACKOFF_S = 0.05


def extra_headers_from_payload(payload: Mapping[str, Any]) -> Mapping[str, str] | None:
    """从 ``payload.external_request_headers`` 解析额外 HTTP 头（键值须均为 ``str``）。

    非 dict、空 dict 或无法解析为 ``str→str`` 的项跳过；若无有效项则返回 ``None``。
    长期密钥不宜写入持久化 payload，生产环境宜由 Gateway 注入。
    """
    raw = payload.get("external_request_headers")
    if not isinstance(raw, dict) or not raw:
        return None
    out: dict[str, str] = {}
    for k, v in raw.items():
        if isinstance(k, str) and isinstance(v, str):
            out[k] = v
    return out or None


@dataclass(frozen=True)
class IntegrationGetResult:
    """单次 ``get_json_with_retries`` 的聚合结果。"""

    ok: bool
    status_code: int | None
    json_body: dict[str, Any] | None
    attempts: int
    last_error: str | None


async def get_json_with_retries(
    url: str,
    *,
    correlation_id: str,
    timeout_s: float = 5.0,
    max_attempts: int = 3,
    client: httpx.AsyncClient | None = None,
    extra_headers: Mapping[str, str] | None = None,
) -> IntegrationGetResult:
    """GET JSON；成功时 ``json_body`` 为 dict。

    - 请求头：``Idempotency-Key`` = ``correlation_id``（与总线步级 ID 对齐，便于对端去重）；``Accept: application/json``。
    - ``extra_headers``：额外头（如 ``Authorization``）；**不会**覆盖上述两条固定头（幂等与 Accept 始终由本函数强制）。
    - 对 **502/503/504** 与 **网络类错误** 重试，最多 ``max_attempts`` 次。
    - 传入 ``client`` 时不在此函数内关闭（便于测试注入 ``MockTransport``）。
    """
    own = client is None
    c = client or httpx.AsyncClient(timeout=timeout_s)
    headers: dict[str, str] = {}
    if extra_headers:
        for hk, hv in extra_headers.items():
            if isinstance(hk, str) and isinstance(hv, str):
                headers[hk] = hv
    headers["Idempotency-Key"] = correlation_id
    headers["Accept"] = "application/json"
    last_err: str | None = None
    try:
        for attempt in range(1, max_attempts + 1):
            try:
                r = await c.get(url, headers=headers)
                if r.status_code == 200:
                    try:
                        body = r.json()
                    except Exception as e:  # noqa: BLE001 — 返回结构化错误
                        return IntegrationGetResult(
                            False,
                            r.status_code,
                            None,
                            attempt,
                            f"json_parse:{type(e).__name__}",
                        )
                    if isinstance(body, dict):
                        return IntegrationGetResult(True, 200, body, attempt, None)
                    return IntegrationGetResult(
                        False,
                        r.status_code,
                        None,
                        attempt,
                        "json_not_object",
                    )
                if r.status_code in (502, 503, 504) and attempt < max_attempts:
                    last_err = f"http_{r.status_code}"
                    await asyncio.sleep(_RETRY_BACKOFF_S)
                    continue
                return IntegrationGetResult(
                    False,
                    r.status_code,
                    None,
                    attempt,
                    f"http_{r.status_code}",
                )
            except httpx.RequestError as e:
                last_err = f"{type(e).__name__}:{e}"
                if attempt < max_attempts:
                    await asyncio.sleep(_RETRY_BACKOFF_S)
                    continue
                return IntegrationGetResult(False, None, None, attempt, last_err)
        return IntegrationGetResult(False, None, None, max_attempts, last_err or "exhausted")
    finally:
        if own:
            await c.aclose()


async def merge_json_int_override(
    url: str,
    *,
    correlation_id: str,
    field: str,
    fallback: int,
    mode: str,
    client: httpx.AsyncClient | None = None,
    extra_headers: Mapping[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    """若 ``url`` 非空则 GET JSON，并读取 ``field`` 为 int（≥0）；失败或未解析则回退 ``fallback``。

    返回 ``(最终整数值, l3_integration 或 {})``；无 URL 时返回 ``(fallback, {})`` 且不发起请求。
    ``extra_headers`` 传给 :func:`get_json_with_retries`（如对端需 ``Authorization``）。
    """
    u = str(url or "").strip()
    if not u:
        return fallback, {}
    res = await get_json_with_retries(
        u,
        correlation_id=correlation_id,
        client=client,
        extra_headers=extra_headers,
    )
    l3: dict[str, Any] = {
        "mode": mode,
        "attempts": res.attempts,
        "status_code": res.status_code,
    }
    if res.last_error:
        l3["last_error"] = res.last_error[:500]
    used = False
    if res.ok and isinstance(res.json_body, dict) and field in res.json_body:
        try:
            value = max(int(res.json_body[field]), 0)
            used = True
        except (TypeError, ValueError):
            pass
    if not used:
        l3["degraded"] = True
        l3["used_external"] = False
        return fallback, l3
    l3["used_external"] = True
    return value, l3


async def merge_json_float_override(
    url: str,
    *,
    correlation_id: str,
    field: str,
    fallback: float,
    mode: str,
    client: httpx.AsyncClient | None = None,
    extra_headers: Mapping[str, str] | None = None,
) -> tuple[float, dict[str, Any]]:
    """若 ``url`` 非空则 GET JSON，并读取 ``field`` 为有限浮点数，**四舍五入到 2 位小数**后覆盖 ``fallback``。

    失败或未解析则回退 ``fallback``。金额类字段与本地 ``round(..., 2)`` 对齐。
    返回 ``(最终 float, l3_integration 或 {})``；无 URL 时返回 ``(fallback, {})`` 且不发起请求。
    """
    u = str(url or "").strip()
    if not u:
        return round(float(fallback), 2), {}
    res = await get_json_with_retries(
        u,
        correlation_id=correlation_id,
        client=client,
        extra_headers=extra_headers,
    )
    l3: dict[str, Any] = {
        "mode": mode,
        "attempts": res.attempts,
        "status_code": res.status_code,
    }
    if res.last_error:
        l3["last_error"] = res.last_error[:500]
    parsed: float | None = None
    if res.ok and isinstance(res.json_body, dict) and field in res.json_body:
        try:
            v = float(res.json_body[field])
            if math.isfinite(v):
                parsed = round(v, 2)
        except (TypeError, ValueError):
            pass
    if parsed is None:
        l3["degraded"] = True
        l3["used_external"] = False
        return round(float(fallback), 2), l3
    l3["used_external"] = True
    return parsed, l3
