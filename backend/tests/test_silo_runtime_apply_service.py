# ruff: noqa: INP001
"""Runtime apply service tests for PicoClaw bundle operations."""

from __future__ import annotations

import httpx
import pytest

from app.schemas.silos import RuntimeBundleValidateRequestRead
from app.services.silos.runtime_apply import RuntimeApplyService


@pytest.mark.asyncio
async def test_validate_bundle_posts_picoclaw_payload_with_bearer_token() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("Authorization")
        captured["payload"] = request.content.decode("utf-8")
        return httpx.Response(
            200,
            json={
                "valid": True,
                "restart_required": True,
                "writes": [],
                "warnings": [],
                "resolved_secrets": [],
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = RuntimeApplyService(client=client)

    response = await service.validate_bundle(
        runtime_url="http://gateway.local:9090/",
        runtime_token="runtime-token",
        bundle=RuntimeBundleValidateRequestRead(
            config_patch={"channels": {"discord": {"enabled": True}}},
        ),
    )

    await client.aclose()

    assert response.valid is True
    assert captured["url"] == "http://gateway.local:9090/api/system/runtime-bundles/validate"
    assert captured["auth"] == "Bearer runtime-token"
    assert '"discord"' in str(captured["payload"])


@pytest.mark.asyncio
async def test_apply_bundle_maps_picoclaw_apply_response() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).endswith("/api/system/runtime-bundles/apply")
        return httpx.Response(
            200,
            json={
                "applied": True,
                "restart_required": True,
                "writes": [
                    {
                        "root": "workspace",
                        "path": "AGENTS.md",
                        "target_path": "/srv/openclaw/workspace/AGENTS.md",
                        "perm": "0644",
                        "bytes": 42,
                    },
                ],
                "warnings": [],
                "resolved_secrets": [],
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = RuntimeApplyService(client=client)

    response = await service.apply_bundle(
        runtime_url="https://gateway.local",
        bundle=RuntimeBundleValidateRequestRead(files=[]),
        allow_insecure_tls=True,
    )

    await client.aclose()

    assert response.applied is True
    assert response.writes[0].target_path == "/srv/openclaw/workspace/AGENTS.md"


@pytest.mark.asyncio
async def test_validate_bundle_propagates_runtime_http_errors() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"detail": "config patch validation failed"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = RuntimeApplyService(client=client)

    with pytest.raises(httpx.HTTPStatusError):
        await service.validate_bundle(
            runtime_url="http://gateway.local",
            bundle=RuntimeBundleValidateRequestRead(files=[]),
        )

    await client.aclose()
