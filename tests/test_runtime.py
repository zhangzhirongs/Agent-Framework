import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

from app.geoflow import GeoFlowClient
from tests.conftest import browser, login, run_message


async def test_chat_stream_and_history_persist(platform):
    app, provider = platform
    async with browser(app) as client:
        await login(client)
        thread = (await client.post("/api/threads")).json()["id"]
        first = await run_message(client, app, thread, "First question")
        events = await client.get(f"/api/runs/{first['id']}/events")
        assert "event: delta" in events.text and "event: done" in events.text
        await run_message(client, app, thread, "Second question")
        sent = json.dumps(provider.requests[-1]["messages"])
        assert "First question" in sent and "Second question" in sent
        detail = (await client.get(f"/api/threads/{thread}")).json()
        assert [m["role"] for m in detail["messages"]] == ["user", "assistant", "user", "assistant"]
        assert "test-only" not in (await client.get("/api/capabilities")).text


async def test_selected_model_reaches_provider_request(platform):
    from agents import OpenAIChatCompletionsModel

    app, provider = platform
    runtime = app.state.runtime
    runtime.settings.model = "test-only"
    runtime.client = provider.client
    runtime.model_factory = OpenAIChatCompletionsModel
    runtime.available_models.append("alternate-model")
    async with browser(app) as client:
        await login(client)
        thread = (await client.post("/api/threads")).json()["id"]
        await run_message(client, app, thread, "Use the selected model", model="alternate-model")
    assert provider.requests[-1]["model"] == "alternate-model"


async def test_model_loads_standard_skill_and_generates_downloadable_file(platform):
    app, provider = platform
    async with browser(app) as client:
        await login(client)
        thread = (await client.post("/api/threads")).json()["id"]
        await run_message(client, app, thread, "use-skill", skills=["example-note"])
        tools = [m for m in provider.requests[-1]["messages"] if m["role"] == "tool"]
        assert "工作笔记" in tools[0]["content"]
        await run_message(client, app, thread, "write-file")
        detail = (await client.get(f"/api/threads/{thread}")).json()
        key = detail["messages"][-1]["file_ids"][0]
        response = await client.get(f"/api/files/{key}")
        assert response.content == b"# Note\nDone"
        assert "attachment" in response.headers["content-disposition"]


async def test_real_stdio_mcp_is_called_by_agent(platform, settings):
    app, provider = platform
    server = Path(__file__).resolve().parents[1] / "examples" / "echo_mcp.py"
    app.state.runtime.connectors.save(
        {"example": {"command": sys.executable, "args": [str(server)], "allowed_tools": ["ping"]}}
    )
    async with browser(app) as client:
        await login(client)
        tested = await client.post("/api/connectors/test")
        assert tested.status_code == 200, tested.text
        assert tested.json()["servers"][0]["tools"] == ["ping"]
        thread = (await client.post("/api/threads")).json()["id"]
        await run_message(client, app, thread, "use-mcp")
        tools = [m for m in provider.requests[-1]["messages"] if m["role"] == "tool"]
        assert "pong: hello" in json.dumps(tools[-1]["content"])


async def test_provider_failure_is_redacted_and_task_has_terminal_state(platform, monkeypatch):
    app, _ = platform

    # A synchronous registry failure is enough to exercise the error boundary.
    monkeypatch.setattr(
        app.state.runtime.connectors,
        "configs",
        lambda: (_ for _ in ()).throw(RuntimeError("secret-fixture-not-for-client")),
    )
    async with browser(app) as client:
        await login(client)
        thread = (await client.post("/api/threads")).json()["id"]
        sent = (
            await client.post(f"/api/threads/{thread}/messages", json={"content": "hello"})
        ).json()
        if task := app.state.runtime.tasks.get(sent["id"]):
            await task
        response = await client.get(f"/api/threads/{thread}")
        assert response.json()["runs"][0]["status"] == "failed"
        assert "secret-fixture-not-for-client" not in response.text


async def test_task_cancelled_before_first_step_does_not_remain_queued(platform):
    app, _ = platform
    runtime = app.state.runtime
    async with browser(app) as client:
        await login(client)
        thread = (await client.post("/api/threads")).json()["id"]
        run = {"id": "cancel-before-start", "thread_id": thread}
        with app.state.store.connect() as db:
            db.execute(
                "INSERT INTO runs(id,thread_id,status,created) VALUES(?,?,'queued',1)",
                (run["id"], thread),
            )
        runtime.start(run, "hello", [], [])
        task = runtime.tasks[run["id"]]
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        saved = app.state.store.query("SELECT * FROM runs WHERE id=?", (run["id"],))[0]
        assert saved["status"] == "cancelled"
        assert run["id"] not in runtime.tasks


@pytest.mark.parametrize("provider", ["tavily", "brave", "searxng"])
async def test_search_uses_selected_provider_and_own_credentials(platform, monkeypatch, provider):
    app, _ = platform
    runtime = app.state.runtime
    from pydantic import SecretStr

    runtime.settings.search_provider = provider
    runtime.settings.search_base_url = "https://search.example.test/search"
    runtime.settings.search_api_key = SecretStr("test-search-only")
    seen = []

    def handle(request):
        seen.append(request)
        return httpx.Response(200, json={"results": [{"title": "example result"}]})

    factory = httpx.AsyncClient
    monkeypatch.setattr(
        "app.runtime.httpx.AsyncClient",
        lambda **kwargs: factory(transport=httpx.MockTransport(handle), **kwargs),
    )
    result = await runtime.search("example query")
    assert "example result" in result["results"]
    assert len(seen) == 1 and seen[0].url.host == "search.example.test"
    if provider == "tavily":
        assert json.loads(seen[0].content)["api_key"] == "test-search-only"
    elif provider == "brave":
        assert seen[0].headers["X-Subscription-Token"] == "test-search-only"
    else:
        assert seen[0].url.params["format"] == "json"


async def test_runtime_registers_geoflow_social_tools(platform):
    app, _ = platform
    app.state.runtime.geoflow = GeoFlowClient("https://geo.example.test", "token")

    names = {tool.name for tool in app.state.runtime.tools("thread", [])}

    assert {
        "geoflow_catalog",
        "geoflow_search_articles",
        "geoflow_get_article",
        "geoflow_save_article_draft",
        "geoflow_list_social_platforms",
        "geoflow_list_social_accounts",
        "geoflow_enqueue_social_publication",
        "geoflow_get_social_job",
    } <= names


async def test_runtime_creates_the_explicitly_selected_model(platform):
    app, _ = platform
    runtime = app.state.runtime
    created = []
    runtime.settings.model = "default-model"
    runtime.client = object()
    runtime.model_factory = lambda *, model, openai_client: created.append(model) or model

    assert runtime.model_for("alternate-model") == "alternate-model"
    assert created == ["alternate-model"]
    assert runtime.model_for("default-model") is runtime.model
    runtime.client = None
