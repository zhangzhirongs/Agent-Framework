import json

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


async def test_keyword_items_support_pagination_and_standard_material_aliases(monkeypatch):
    seen = []
    factory = httpx.AsyncClient

    def handle(request):
        seen.append(request)
        return httpx.Response(200, json={"success": True, "data": {"items": []}})

    monkeypatch.setattr(
        "app.geoflow.httpx.AsyncClient",
        lambda **kwargs: factory(transport=httpx.MockTransport(handle), **kwargs),
    )
    client = GeoFlowClient("https://geo.example.test", "token")
    await client.material_items("keyword-libraries", 4, page=3)
    assert seen[0].url.path == "/api/v1/materials/keyword_libraries/4/items"
    assert dict(seen[0].url.params) == {"page": "3", "per_page": "50"}
    with pytest.raises(ValueError):
        await client.material_items("../../articles", 4)


async def test_task_resource_endpoints_require_login_and_preserve_pagination(platform, monkeypatch):
    from tests.conftest import browser, login

    app, _ = platform
    geo = GeoFlowClient("https://geo.example.test", "token")
    app.state.runtime.geoflow = geo

    async def items(material_type, material_id, page=1):
        assert (material_type, material_id, page) == ("keywords", 4, 2)
        return {"items": [{"id": 7, "keyword": "品牌词"}], "pagination": {"page": 2}}

    async def accounts():
        return {"items": [{"id": 8, "account_name": "品牌账号"}]}

    monkeypatch.setattr(geo, "material_items", items)
    monkeypatch.setattr(geo, "social_accounts", accounts)
    async with browser(app) as client:
        path = "/api/geoflow/materials/keywords/4/items?page=2"
        assert (await client.get(path)).status_code == 401
        assert (await client.get("/api/geoflow/social/accounts")).status_code == 401
        await login(client)
        assert (await client.get(path)).json()["items"][0]["keyword"] == "品牌词"
        assert (await client.get("/api/geoflow/social/accounts")).json()["items"][0]["id"] == 8
        assert (await client.get("/api/geoflow/social/secrets")).status_code == 422


@pytest.mark.parametrize("invalid", [None, "library", "keyword", "account"])
async def test_selected_task_resources_are_validated_and_forwarded(platform, monkeypatch, invalid):
    from tests.conftest import browser, login

    app, _ = platform
    geo = GeoFlowClient("https://geo.example.test", "token")
    app.state.runtime.geoflow = geo
    captured = []

    async def catalog():
        return {
            "knowledge_bases": [{"id": 1, "name": "品牌知识"}],
            "title_libraries": [{"id": 2, "name": "选题"}],
            "keyword_libraries": [{"id": 3, "name": "种子词库"}],
            "image_libraries": [{"id": 4, "name": "品牌配图"}],
        }

    async def items(material_type, material_id, page=1):
        assert (material_type, material_id, page) == ("keywords", 3, 2)
        return {"items": [{"id": 6, "keyword": "真实关键词"}]}

    async def accounts():
        return {"items": [{"id": 5, "account_name": "品牌账号", "platform": "weibo"}]}

    monkeypatch.setattr(geo, "catalog", catalog)
    monkeypatch.setattr(geo, "material_items", items)
    monkeypatch.setattr(geo, "social_accounts", accounts)
    monkeypatch.setattr(app.state.runtime, "start", lambda *args: captured.append(args[4]))
    context = {
        "knowledge_base_ids": [1],
        "title_library_ids": [2],
        "keyword_library_ids": [3],
        "image_library_ids": [4],
        "social_account_ids": [5],
        "keywords": [{"library_id": 3, "item_id": 6, "page": 2}],
    }
    if invalid == "library":
        context["keyword_library_ids"] = [99]
    elif invalid == "keyword":
        context["keywords"][0]["item_id"] = 99
    elif invalid == "account":
        context["social_account_ids"] = [99]
    async with browser(app) as client:
        await login(client)
        thread = (await client.post("/api/threads")).json()["id"]
        response = await client.post(
            f"/api/threads/{thread}/messages",
            json={"content": "执行所选任务", "geoflow_context": context},
        )
    if invalid:
        assert response.status_code == 422
        assert not captured
        assert not app.state.store.query("SELECT * FROM runs")
    else:
        assert response.status_code == 202, response.text
        assert captured[0]["keywords"] == [{"id": 6, "library_id": 3, "name": "真实关键词"}]
        prompt = app.state.runtime._geoflow_context_prompt(captured[0])
        for expected in (
            "品牌知识",
            "种子词库",
            "真实关键词",
            "品牌配图",
            "品牌账号",
            "platform=weibo",
        ):
            assert expected in prompt


async def test_social_publish_calls_use_selected_account_and_idempotency(monkeypatch):
    seen = []

    def handle(request):
        seen.append(request)
        if request.url.path.endswith("/social-publication/jobs"):
            return httpx.Response(
                202, json={"success": True, "data": {"job_id": 12, "job_state": "queued"}}
            )
        return httpx.Response(200, json={"success": True, "data": {"items": []}})

    factory = httpx.AsyncClient
    monkeypatch.setattr(
        "app.geoflow.httpx.AsyncClient",
        lambda **kwargs: factory(transport=httpx.MockTransport(handle), **kwargs),
    )
    client = GeoFlowClient("https://geo.example.test", "token")

    await client.social_platforms()
    await client.social_accounts("xiaohongshu")
    queued = await client.enqueue_social_publication(
        8, "系统介绍", "介绍正文", "job-key-1", images=["https://assets.example.test/cover.jpg"]
    )
    await client.get_social_job(12)

    assert queued["job_state"] == "queued"
    assert seen[0].url.path == "/api/v1/social-publication/platforms"
    assert dict(seen[1].url.params) == {"platform": "xiaohongshu"}
    assert json.loads(seen[2].content)["account_id"] == 8
    assert seen[2].headers["x-idempotency-key"] == "job-key-1"
    assert seen[3].url.path == "/api/v1/social-publication/jobs/12"


async def test_save_article_draft_cannot_publish(monkeypatch):
    seen = []
    factory = httpx.AsyncClient

    def handle(request):
        seen.append(request)
        return httpx.Response(201, json={"success": True, "data": {"id": 21}})

    monkeypatch.setattr(
        "app.geoflow.httpx.AsyncClient",
        lambda **kwargs: factory(transport=httpx.MockTransport(handle), **kwargs),
    )
    await GeoFlowClient("https://geo.example.test", "token").save_article_draft(
        {"title": "系统介绍", "content": "正文", "status": "published"}, "draft-key"
    )
    payload = json.loads(seen[0].content)
    assert payload["status"] == "draft"
    assert payload["review_status"] == "pending"


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
