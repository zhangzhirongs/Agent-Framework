import httpx
import pytest

from app.geoflow import GeoFlowClient, GeoFlowError


async def test_geoflow_client_uses_v1_bearer_and_unwraps_success(monkeypatch):
    seen = []

    def handle(request):
        seen.append(request)
        return httpx.Response(200, json={"success": True, "data": {"items": []}})

    transport = httpx.MockTransport(handle)
    factory = httpx.AsyncClient
    monkeypatch.setattr(
        "app.geoflow.httpx.AsyncClient",
        lambda **kwargs: factory(transport=transport, **kwargs),
    )
    client = GeoFlowClient("https://geo.example.test/", "secret-token")

    result = await client.catalog()

    assert result == {"items": []}
    assert seen[0].url == "https://geo.example.test/api/v1/catalog"
    assert seen[0].headers["authorization"] == "Bearer secret-token"
    assert "secret-token" not in repr(result)


async def test_geoflow_client_rejects_error_envelope(monkeypatch):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            403,
            json={
                "success": False,
                "data": None,
                "error": {"code": "forbidden", "message": "no"},
            },
        )
    )
    factory = httpx.AsyncClient
    monkeypatch.setattr(
        "app.geoflow.httpx.AsyncClient",
        lambda **kwargs: factory(transport=transport, **kwargs),
    )

    with pytest.raises(GeoFlowError, match="403"):
        await GeoFlowClient("https://geo.example.test", "token").catalog()


async def test_geoflow_client_sends_idempotency_key(monkeypatch):
    seen = []

    def handle(request):
        seen.append(request)
        return httpx.Response(201, json={"success": True, "data": {"id": 7}})

    transport = httpx.MockTransport(handle)
    factory = httpx.AsyncClient
    monkeypatch.setattr(
        "app.geoflow.httpx.AsyncClient",
        lambda **kwargs: factory(transport=transport, **kwargs),
    )

    result = await GeoFlowClient("https://geo.example.test", "token").create_article(
        {"title": "Draft"}, "thread-123"
    )

    assert result == {"id": 7}
    assert seen[0].headers["x-idempotency-key"] == "thread-123"


async def test_geoflow_client_handles_invalid_json(monkeypatch):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"not-json"))
    factory = httpx.AsyncClient
    monkeypatch.setattr(
        "app.geoflow.httpx.AsyncClient",
        lambda **kwargs: factory(transport=transport, **kwargs),
    )

    with pytest.raises(GeoFlowError, match="invalid JSON"):
        await GeoFlowClient("https://geo.example.test", "token").catalog()


async def test_runtime_registers_only_read_tools_when_geoflow_is_configured(platform):
    app, _ = platform
    app.state.runtime.geoflow = GeoFlowClient("https://geo.example.test", "token")

    names = {tool.name for tool in app.state.runtime.tools("thread", [])}

    assert {"geoflow_catalog", "geoflow_search_articles", "geoflow_get_article"} <= names
    assert "geoflow_publish_article" not in names
