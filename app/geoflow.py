"""Small, server-side client for the GEOFlow API v1."""

from __future__ import annotations

from typing import Any

import httpx


class GeoFlowError(RuntimeError):
    """A sanitized error raised for GEOFlow integration failures."""


class GeoFlowClient:
    MATERIAL_TYPES = {
        alias: canonical
        for canonical, aliases in (
            ("knowledge_bases", ("knowledge", "knowledge_base", "knowledge_bases")),
            ("title_libraries", ("title", "title_library", "title_libraries")),
            ("keyword_libraries", ("keyword", "keywords", "keyword_libraries")),
            ("image_libraries", ("image", "images", "image_libraries")),
        )
        for alias in aliases
    }

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
        normalized = self.MATERIAL_TYPES.get(material_type.strip().lower().replace("-", "_"))
        if normalized is None:
            raise ValueError("Unsupported GEOFlow material type")
        params: dict[str, Any] = {
            "page": max(1, page),
            "per_page": min(100, max(1, per_page)),
        }
        if search.strip():
            params["search"] = search.strip()
        return await self.request("GET", f"materials/{normalized}", params=params)

    async def material_items(
        self, material_type: str, material_id: int, page: int = 1, per_page: int = 50
    ) -> dict[str, Any]:
        normalized = self.MATERIAL_TYPES.get(material_type.strip().lower().replace("-", "_"))
        if normalized is None or material_id < 1:
            raise ValueError("Unsupported GEOFlow material selection")
        return await self.request(
            "GET",
            f"materials/{normalized}/{material_id}/items",
            params={"page": max(1, page), "per_page": min(100, max(1, per_page))},
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

    async def save_article_draft(
        self, payload: dict[str, Any], idempotency_key: str
    ) -> dict[str, Any]:
        draft = {**payload, "status": "draft", "review_status": "pending"}
        return await self.create_article(draft, idempotency_key)

    async def social_platforms(self) -> dict[str, Any]:
        return await self.request("GET", "social-publication/platforms")

    async def social_accounts(self, platform: str | None = None) -> dict[str, Any]:
        params = {"platform": platform} if platform else None
        return await self.request("GET", "social-publication/accounts", params=params)

    async def enqueue_social_publication(
        self,
        account_id: int,
        title: str,
        content: str,
        idempotency_key: str,
        excerpt: str = "",
        images: list[str] | None = None,
    ) -> dict[str, Any]:
        if account_id < 1 or not title.strip() or not content.strip():
            raise ValueError("A valid account, title, and content are required")
        return await self.request(
            "POST",
            "social-publication/jobs",
            json={
                "account_id": account_id,
                "title": title,
                "content": content,
                "excerpt": excerpt,
                "images": images or [],
            },
            headers={"X-Idempotency-Key": idempotency_key},
        )

    async def get_social_job(self, job_id: int) -> dict[str, Any]:
        if job_id < 1:
            raise ValueError("Invalid social job ID")
        return await self.request("GET", f"social-publication/jobs/{job_id}")
