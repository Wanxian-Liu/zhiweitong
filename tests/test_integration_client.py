"""``shared.integration_client`` 契约：重试、幂等头、JSON 解析。"""

from __future__ import annotations

import asyncio

import httpx

from shared.integration_client import (
    IntegrationGetResult,
    extra_headers_from_payload,
    get_json_with_retries,
    merge_json_float_override,
    merge_json_int_override,
)


def test_extra_headers_from_payload() -> None:
    assert extra_headers_from_payload({}) is None
    assert extra_headers_from_payload({"external_request_headers": None}) is None
    assert extra_headers_from_payload({"external_request_headers": {}}) is None
    assert extra_headers_from_payload({"external_request_headers": {"A": "b"}}) == {"A": "b"}
    assert extra_headers_from_payload({"external_request_headers": {1: "x"}}) is None
    assert extra_headers_from_payload({"external_request_headers": {"X": 99}}) is None


def test_get_json_retries_until_200() -> None:
    n = {"c": 0}
    idem: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        idem.append(request.headers.get("Idempotency-Key", ""))
        n["c"] += 1
        if n["c"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"raw_stock": 42})

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            r = await get_json_with_retries(
                "http://wms.example/stock",
                correlation_id="step-cid-1",
                client=client,
                max_attempts=3,
            )
        assert isinstance(r, IntegrationGetResult)
        assert r.ok is True
        assert r.status_code == 200
        assert r.json_body == {"raw_stock": 42}
        assert r.attempts == 3
        assert idem == ["step-cid-1", "step-cid-1", "step-cid-1"]

    asyncio.run(_run())


def test_get_json_fails_on_404_no_retry() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            r = await get_json_with_retries(
                "http://wms.example/missing",
                correlation_id="c2",
                client=client,
                max_attempts=3,
            )
        assert r.ok is False
        assert r.status_code == 404
        assert r.attempts == 1

    asyncio.run(_run())


def test_get_json_request_error_retries() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(200, json={"a": 1})

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            r = await get_json_with_retries(
                "http://wms.example/x",
                correlation_id="c3",
                client=client,
                max_attempts=2,
            )
        assert r.ok is True
        assert r.json_body == {"a": 1}
        assert r.attempts == 2

    asyncio.run(_run())


def test_get_json_extra_headers_authorization() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("Authorization", ""))
        return httpx.Response(200, json={"x": 1})

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            r = await get_json_with_retries(
                "http://wms.example/secure",
                correlation_id="cid-auth",
                client=client,
                extra_headers={"Authorization": "Bearer test-token"},
            )
        assert r.ok is True
        assert seen == ["Bearer test-token"]

    asyncio.run(_run())


def test_get_json_extra_headers_do_not_override_idempotency() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Idempotency-Key") == "real-cid"
        return httpx.Response(200, json={"ok": True})

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            r = await get_json_with_retries(
                "http://wms.example/x",
                correlation_id="real-cid",
                client=client,
                extra_headers={"Idempotency-Key": "attacker", "Authorization": "Bearer z"},
            )
        assert r.ok is True
        assert r.json_body == {"ok": True}

    asyncio.run(_run())


def test_merge_json_int_override_passes_extra_headers() -> None:
    auth: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        auth.append(request.headers.get("Authorization", ""))
        return httpx.Response(200, json={"n": 7})

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            v, d = await merge_json_int_override(
                "http://wms/h",
                correlation_id="m1",
                field="n",
                fallback=0,
                mode="mh",
                client=client,
                extra_headers={"Authorization": "Bearer m"},
            )
        assert v == 7
        assert auth == ["Bearer m"]
        assert d["used_external"] is True

    asyncio.run(_run())


def test_merge_json_int_override_empty_url() -> None:
    async def _run() -> None:
        v, d = await merge_json_int_override(
            "",
            correlation_id="c0",
            field="x",
            fallback=7,
            mode="t",
        )
        assert v == 7 and d == {}

    asyncio.run(_run())


def test_merge_json_int_override_success_and_degraded() -> None:
    async def _run() -> None:
        transport_ok = httpx.MockTransport(lambda r: httpx.Response(200, json={"n": 42}))
        async with httpx.AsyncClient(transport=transport_ok) as client:
            v, d = await merge_json_int_override(
                "http://wms/n",
                correlation_id="c1",
                field="n",
                fallback=0,
                mode="m1",
                client=client,
            )
        assert v == 42
        assert d["used_external"] is True
        assert d["mode"] == "m1"

        transport_fail = httpx.MockTransport(lambda r: httpx.Response(404))
        async with httpx.AsyncClient(transport=transport_fail) as client:
            v2, d2 = await merge_json_int_override(
                "http://wms/miss",
                correlation_id="c2",
                field="n",
                fallback=99,
                mode="m2",
                client=client,
            )
        assert v2 == 99
        assert d2["degraded"] is True
        assert d2["used_external"] is False

    asyncio.run(_run())


def test_merge_json_float_override_empty_url() -> None:
    async def _run() -> None:
        v, d = await merge_json_float_override(
            "",
            correlation_id="cf0",
            field="x",
            fallback=12.345,
            mode="f",
        )
        assert v == 12.35 and d == {}

    asyncio.run(_run())


def test_merge_json_float_override_success_and_degraded() -> None:
    async def _run() -> None:
        transport_ok = httpx.MockTransport(lambda r: httpx.Response(200, json={"amt": 99.996}))
        async with httpx.AsyncClient(transport=transport_ok) as client:
            v, d = await merge_json_float_override(
                "http://erp/a",
                correlation_id="cf1",
                field="amt",
                fallback=0.0,
                mode="fx",
                client=client,
            )
        assert v == 100.0
        assert d["used_external"] is True

        transport_fail = httpx.MockTransport(lambda r: httpx.Response(404))
        async with httpx.AsyncClient(transport=transport_fail) as client:
            v2, d2 = await merge_json_float_override(
                "http://erp/miss",
                correlation_id="cf2",
                field="amt",
                fallback=3.33,
                mode="fy",
                client=client,
            )
        assert v2 == 3.33
        assert d2["degraded"] is True
        assert d2["used_external"] is False

    asyncio.run(_run())
