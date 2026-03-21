"""Runtime apply helpers for validating/applying PicoClaw bundles."""

from __future__ import annotations

import httpx

from app.schemas.silos import (
    RuntimeBundleApplyResponseRead,
    RuntimeBundleValidateRequestRead,
    RuntimeBundleValidateResponseRead,
)


class RuntimeApplyService:
    """Call PicoClaw runtime bundle validate/apply endpoints."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def validate_bundle(
        self,
        *,
        runtime_url: str,
        bundle: RuntimeBundleValidateRequestRead,
        runtime_token: str | None = None,
        allow_insecure_tls: bool = False,
    ) -> RuntimeBundleValidateResponseRead:
        """Validate a rendered runtime bundle against one PicoClaw host."""
        response = await self._post(
            runtime_url=runtime_url,
            endpoint="/api/system/runtime-bundles/validate",
            payload=bundle.model_dump(exclude_none=True),
            runtime_token=runtime_token,
            allow_insecure_tls=allow_insecure_tls,
        )
        return RuntimeBundleValidateResponseRead.model_validate(response.json())

    async def apply_bundle(
        self,
        *,
        runtime_url: str,
        bundle: RuntimeBundleValidateRequestRead,
        runtime_token: str | None = None,
        allow_insecure_tls: bool = False,
    ) -> RuntimeBundleApplyResponseRead:
        """Apply a rendered runtime bundle against one PicoClaw host."""
        response = await self._post(
            runtime_url=runtime_url,
            endpoint="/api/system/runtime-bundles/apply",
            payload=bundle.model_dump(exclude_none=True),
            runtime_token=runtime_token,
            allow_insecure_tls=allow_insecure_tls,
        )
        return RuntimeBundleApplyResponseRead.model_validate(response.json())

    async def _post(
        self,
        *,
        runtime_url: str,
        endpoint: str,
        payload: dict[str, object],
        runtime_token: str | None,
        allow_insecure_tls: bool,
    ) -> httpx.Response:
        url = f"{runtime_url.rstrip('/')}{endpoint}"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if runtime_token:
            headers["Authorization"] = f"Bearer {runtime_token}"

        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(verify=not allow_insecure_tls, timeout=30.0)
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response
        finally:
            if owns_client:
                await client.aclose()
