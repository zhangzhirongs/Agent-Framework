"""Small, server-side client for the GEOFlow API v1."""

from __future__ import annotations

from typing import Any

import httpx


class GeoFlowError(RuntimeError):
    """A sanitized error raised for GEOFlow integration failures."""


class GeoFlowClient:
    def __init__(self, base_url: str, token: str, timeout: int = 30, verify_tls: bool = True):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.verify_tls = verify_tls

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.token)

    async def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        if not self.enabled:
            raise GeoFlowError("GEOFlow integration is not configured")
        headers = kwargs.pop("headers", {})
        headers = {
            **headers,
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        url = f"{self.base_url}/api/v1/{path.lstrip('/')}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout, verify=self.verify_tls) as client:
                response = await client.request(method, url, headers=headers, **kwargs)
        except (httpx.HTTPError, TimeoutError) as exc:
            raise GeoFlowError("GEOFlow request could not be completed") from exc
        if not response.is_success:
            raise GeoFlowError(f"GEOFlow request failed ({response.status_code})")
        try:
            payload = response.json()
        except ValueError as exc:
            raise GeoFlowError("GEOFlow returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise GeoFlowError("GEOFlow returned an invalid response")
        if payload.get("success") is False or payload.get("ok") is False:
            raise GeoFlowError("GEOFlow rejected the request")
        if payload.get("error") not in (None, {}, ""):
            raise GeoFlowError("GEOFlow rejected the request")
        return payload.get("data", payload)

    async def catalog(self) -> dict[str, Any]:
        return await self.request("GET", "catalog")

    async def material_libraries(
        self, material_type: str, search: str = "", page: int = 1, per_page: int = 50
    ) -> dict[str, Any]:
        """List a GEOFlow material library (for example ``knowledge_bases`` or ``title_libraries``).

        The catalog endpoint is preferred because it is a single request, but this method is
        useful when a UI needs search or pagination.  Keep the allow-list here so a caller
        cannot turn this integration into an arbitrary path proxy.
        """
        aliases = {
            "knowledge": "knowledge_bases",
            "knowledge_base": "knowledge_bases",
            "knowledge_bases": "knowledge_bases",
            "title": "title_libraries",
            "title_library": "title_libraries",
            "title_libraries": "title_libraries",
        }
        normalized = aliases.get(material_type.strip().lower())
        if normalized is None:
            raise ValueError("Unsupported GEOFlow material type")
        params: dict[str, Any] = {
            "page": max(1, page),
            "per_page": min(100, max(1, per_page)),
        }
        if search.strip():
            params["search"] = search.strip()
        return await self.request("GET", f"materials/{normalized}", params=params)

    async def material_items(self, material_type: str, material_id: int) -> dict[str, Any]:
        aliases = {
            "knowledge": "knowledge_bases",
            "knowledge_base": "knowledge_bases",
            "knowledge_bases": "knowledge_bases",
            "title": "title_libraries",
            "title_library": "title_libraries",
            "title_libraries": "title_libraries",
        }
        normalized = aliases.get(material_type.strip().lower())
        if normalized is None or material_id < 1:
            raise ValueError("Unsupported GEOFlow material selection")
        return await self.request(
            "GET", f"materials/{normalized}/{material_id}/items", params={"page": 1, "per_page": 20}
        )

    async def list_articles(self, search: str = "", status: str = "draft") -> dict[str, Any]:
        params = {"status": status}
        if search.strip():
            params["search"] = search.strip()
        return await self.request("GET", "articles", params=params)

    async def get_article(self, article_id: int) -> dict[str, Any]:
        return await self.request("GET", f"articles/{article_id}")

    async def create_article(self, payload: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        return await self.request(
            "POST", "articles", json=payload, headers={"X-Idempotency-Key": idempotency_key}
        )

    async def update_article(
        self, article_id: int, payload: dict[str, Any], idempotency_key: str
    ) -> dict[str, Any]:
        return await self.request(
            "PATCH",
            f"articles/{article_id}",
            json=payload,
            headers={"X-Idempotency-Key": idempotency_key},
        )
