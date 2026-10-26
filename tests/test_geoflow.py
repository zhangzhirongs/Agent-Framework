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


async def test_geoflow_material_libraries_normalizes_type_and_bounds_pagination(monkeypatch):
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

    await GeoFlowClient("https://geo.example.test", "token").material_libraries(
        "knowledge", " brand ", page=0, per_page=500
    )

    assert seen[0].url.path == "/api/v1/materials/knowledge_bases"
    assert dict(seen[0].url.params) == {"page": "1", "per_page": "100", "search": "brand"}


async def test_geoflow_material_libraries_rejects_arbitrary_type():
    client = GeoFlowClient("https://geo.example.test", "token")
    with pytest.raises(ValueError):
        await client.material_libraries("../../articles")


async def test_geoflow_catalog_api_requires_login_and_returns_selectable_libraries(platform):
    from tests.conftest import browser, login

    app, _ = platform
    app.state.runtime.geoflow = GeoFlowClient("https://geo.example.test", "token")

    async def catalog():
        return {"models": [], "knowledge_bases": [{"id": 4}], "title_libraries": [{"id": 8}]}

    app.state.runtime.geoflow.catalog = catalog
    async with browser(app) as client:
        assert (await client.get("/api/geoflow/catalog")).status_code == 401
        await login(client)
        response = await client.get("/api/geoflow/catalog")

    assert response.status_code == 200
    assert response.json()["knowledge_bases"] == [{"id": 4}]
    assert response.json()["title_libraries"] == [{"id": 8}]


async def test_runtime_registers_only_read_tools_when_geoflow_is_configured(platform):
    app, _ = platform
    app.state.runtime.geoflow = GeoFlowClient("https://geo.example.test", "token")

    names = {tool.name for tool in app.state.runtime.tools("thread", [])}

    assert {"geoflow_catalog", "geoflow_search_articles", "geoflow_get_article"} <= names
    assert "geoflow_publish_article" not in names
