"""L3 主线：``production-inventory-v1`` 五步经 ``httpx.MockTransport`` 走真实 ``get_json_with_retries``。

与 ``docs/vertical-slice-l3-integration.md`` 一致：不 patch 返回 dict，而是注入
``AsyncClient(MockTransport(...))`` 调用 ``shared.integration_client.get_json_with_retries``。

``test_zz_``：在 ``test_phase2_department_skills`` 之后收集；沙盒 ``enforce_coverage=False``
（覆盖率由 phase2 承担，见 ``test_zz_golden_production_inventory_v1_json`` 说明）。
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from core.sandbox import run_sandbox
from shared.integration_client import get_json_with_retries as real_get_json_with_retries
from shared.vertical_slices import PRODUCTION_INVENTORY_CHAIN, PRODUCTION_INVENTORY_DEFAULT_PARAMS

_L3_BASE = "http://l3-mock.test"


def _mock_handler(request: httpx.Request) -> httpx.Response:
    """按路径返回与主链五步 ``external_*_url`` 文档一致的 JSON 字段名。"""
    u = str(request.url)
    if "/mes/planned_units" in u:
        return httpx.Response(200, json={"planned_units": 130})
    if "/wms/raw_stock" in u:
        return httpx.Response(200, json={"raw_stock": 555})
    if "/wms/received_qty" in u:
        return httpx.Response(200, json={"received_qty": 205})
    if "/wms/quantity_on_hand" in u:
        return httpx.Response(200, json={"quantity_on_hand": 350})
    if "/wms/picked_qty" in u:
        return httpx.Response(200, json={"picked_qty": 77})
    return httpx.Response(404, json={"error": "unknown l3 path"})


def _envelope(skill_id: str, org_path: str, correlation_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "correlation_id": correlation_id,
        "org_path": org_path,
        "skill_id": skill_id,
        "payload": payload,
    }


def _skill_factory(step_index: int):
    def factory():
        if step_index == 0:
            from skills.production_center.production_scheduling import ProductionSchedulingSkill

            return ProductionSchedulingSkill()
        if step_index == 1:
            from skills.production_center.material_requirement import MaterialRequirementSkill

            return MaterialRequirementSkill()
        if step_index == 2:
            from skills.warehouse_logistics.inbound_receiving import InboundReceivingSkill

            return InboundReceivingSkill()
        if step_index == 3:
            from skills.warehouse_logistics.inventory_management import InventoryManagementSkill

            return InventoryManagementSkill()
        from skills.warehouse_logistics.outbound_picking import OutboundPickingSkill

        return OutboundPickingSkill()

    return factory


_COVERAGE_MODULES: tuple[str, ...] = (
    "skills.production_center.production_scheduling",
    "skills.production_center.material_requirement",
    "skills.warehouse_logistics.inbound_receiving",
    "skills.warehouse_logistics.inventory_management",
    "skills.warehouse_logistics.outbound_picking",
)

_L3_URL_KEYS: tuple[str, ...] = (
    "external_planned_units_url",
    "external_raw_stock_url",
    "external_received_qty_url",
    "external_quantity_on_hand_url",
    "external_picked_qty_url",
)

_L3_PATHS: tuple[str, ...] = (
    f"{_L3_BASE}/mes/planned_units",
    f"{_L3_BASE}/wms/raw_stock",
    f"{_L3_BASE}/wms/received_qty",
    f"{_L3_BASE}/wms/quantity_on_hand",
    f"{_L3_BASE}/wms/picked_qty",
)


@pytest.mark.parametrize("step_index", [0, 1, 2, 3, 4])
def test_production_inventory_main_chain_l3_mock_http(step_index: int) -> None:
    """五步各带对应 ``external_*_url``，MockTransport 返回覆盖值；断言 ``l3_integration.used_external``。"""
    step = PRODUCTION_INVENTORY_CHAIN[step_index]
    params = dict(PRODUCTION_INVENTORY_DEFAULT_PARAMS[step_index])
    params[_L3_URL_KEYS[step_index]] = _L3_PATHS[step_index]

    async def _run() -> None:
        transport = httpx.MockTransport(_mock_handler)

        async def patched_get(
            url: str,
            *,
            correlation_id: str,
            timeout_s: float = 5.0,
            max_attempts: int = 3,
            client: httpx.AsyncClient | None = None,
            extra_headers: Any = None,
        ):
            if client is not None:
                return await real_get_json_with_retries(
                    url,
                    correlation_id=correlation_id,
                    timeout_s=timeout_s,
                    max_attempts=max_attempts,
                    client=client,
                    extra_headers=extra_headers,
                )
            async with httpx.AsyncClient(transport=transport) as c:
                return await real_get_json_with_retries(
                    url,
                    correlation_id=correlation_id,
                    timeout_s=timeout_s,
                    max_attempts=max_attempts,
                    client=c,
                    extra_headers=extra_headers,
                )

        with patch("shared.integration_client.get_json_with_retries", new=patched_get):
            rep = await run_sandbox(
                [
                    _envelope(
                        step.skill_id,
                        step.org_path,
                        f"l3-mock-pi-{step_index}",
                        params,
                    ),
                ],
                skill_factory=_skill_factory(step_index),
                coverage_skill_module=_COVERAGE_MODULES[step_index],
                enforce_coverage=False,
            )
        assert rep.passed == 1 and rep.failed == 0
        r = rep.cases[0].result
        assert r is not None
        summ = r["summary"]
        assert summ["l3_integration"]["used_external"] is True
        assert summ["l3_integration"].get("degraded") is not True

        if step_index == 0:
            assert r["planned_units"] == 130
        elif step_index == 1:
            assert r["raw_stock"] == 555
            assert r["mrp_feasible"] is True
        elif step_index == 2:
            assert r["received_qty"] == 205
            assert r["receipt_complete"] is True
        elif step_index == 3:
            assert r["quantity_on_hand"] == 350
        else:
            assert r["picked_qty"] == 77
            assert r["pick_complete"] is False
            assert r["summary"]["exception_code"] == "W_OUTBOUND_SHORTFALL"

    asyncio.run(_run())


def test_production_inventory_l3_external_request_headers_on_wire() -> None:
    """``external_request_headers`` 经 ``get_json_with_retries`` 到达 Mock 请求（Authorization）。"""
    step = PRODUCTION_INVENTORY_CHAIN[0]
    params = dict(PRODUCTION_INVENTORY_DEFAULT_PARAMS[0])
    params["external_planned_units_url"] = f"{_L3_BASE}/secure/planned"
    params["external_request_headers"] = {"Authorization": "Bearer l3-test"}

    seen: list[str] = []

    def capturing_handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("Authorization", ""))
        u = str(request.url)
        if "/secure/planned" in u:
            return httpx.Response(200, json={"planned_units": 42})
        return _mock_handler(request)

    async def _run() -> None:
        transport = httpx.MockTransport(capturing_handler)

        async def patched_get(
            url: str,
            *,
            correlation_id: str,
            timeout_s: float = 5.0,
            max_attempts: int = 3,
            client: httpx.AsyncClient | None = None,
            extra_headers: Any = None,
        ):
            if client is not None:
                return await real_get_json_with_retries(
                    url,
                    correlation_id=correlation_id,
                    timeout_s=timeout_s,
                    max_attempts=max_attempts,
                    client=client,
                    extra_headers=extra_headers,
                )
            async with httpx.AsyncClient(transport=transport) as c:
                return await real_get_json_with_retries(
                    url,
                    correlation_id=correlation_id,
                    timeout_s=timeout_s,
                    max_attempts=max_attempts,
                    client=c,
                    extra_headers=extra_headers,
                )

        with patch("shared.integration_client.get_json_with_retries", new=patched_get):
            rep = await run_sandbox(
                [
                    _envelope(
                        step.skill_id,
                        step.org_path,
                        "l3-mock-headers",
                        params,
                    ),
                ],
                skill_factory=_skill_factory(0),
                coverage_skill_module=_COVERAGE_MODULES[0],
                enforce_coverage=False,
            )
        assert rep.passed == 1
        r = rep.cases[0].result
        assert r is not None
        assert r["planned_units"] == 42
        assert seen == ["Bearer l3-test"]

    asyncio.run(_run())
