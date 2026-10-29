import copy
import json
import sqlite3
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from agents import Agent
from agents.mcp import MCPServerStdio
from agents.run_config import ModelInputData
from agents.tool_context import ToolContext
from mcp.types import Tool

from app.runtime import ContextBudgetExceeded, InputBudget, json_bytes
from app.store import Store
from tests.conftest import browser, login, run_message


def payload(items, instructions="rules", tools=None):
    return SimpleNamespace(
        model_data=ModelInputData(input=items, instructions=instructions),
        agent=Agent(name="test", tools=tools or []),
    )


def test_history_keeps_whole_recent_turns_and_never_mutates_saved_images(settings):
    settings.history_turns = 1
    budget = InputBudget(settings)
    history = [
        {"role": "user", "content": "old"},
        {"role": "assistant", "content": "old answer"},
        {"role": "user", "content": [
            {"type": "input_text", "text": "recent"},
            {"type": "input_image", "image_url": "data:image/png;base64," + "X" * 600000},
        ]},
        {"type": "function_call", "call_id": "a", "name": "tool", "arguments": "{}"},
        {"type": "function_call_output", "call_id": "a", "output": "result"},
    ]
    original = copy.deepcopy(history)
    new = [{"role": "user", "content": "now"}]
    items = budget.session_input(history, new)
    assert len(items) == 4
    assert items[-3]["call_id"] == items[-2]["call_id"]
    assert "data:image" not in json.dumps(items)
    assert history == original and items[-1] == new[0]
    assert budget.trimmed_turns == 1


def test_zero_history_and_orphan_tool_items_are_not_replayed(settings):
    budget = InputBudget(settings)
    new = [{"role": "user", "content": "now"}]
    assert budget.session_input([{"type": "function_call_output", "output": "orphan"}], new) == new
    settings.history_turns = 0
    assert budget.session_input([{"role": "user", "content": "old"}], new) == new


@pytest.mark.parametrize(
    "output", ["X" * 100000, [{"type": "text", "text": "中" * 100000}]],
    ids=["text", "structured"],
)
def test_tool_outputs_are_bounded_in_every_model_call(settings, output):
    budget = InputBudget(settings)
    items = [
        {"role": "user", "content": "question"},
        {"type": "function_call", "call_id": "a", "name": "tool", "arguments": "{}"},
        {"type": "function_call_output", "call_id": "a", "output": output},
    ]
    original = copy.deepcopy(items)
    for _ in range(2):
        result = budget.filter(payload(items))
        truncated = json.loads(result.input[-1]["output"])
        assert truncated["truncated"] is True
        assert len(truncated["preview"]) == settings.max_tool_output_chars
        assert result.input[-1]["call_id"] == result.input[-2]["call_id"]
    assert items == original and budget.requests == 2


def test_byte_limit_removes_complete_turns_and_counts_chinese_utf8(settings):
    settings.max_input_bytes = 4000
    budget = InputBudget(settings)
    items = [
        {"role": "user", "content": "旧" * 2000},
        {"type": "function_call", "call_id": "a"},
        {"type": "function_call_output", "call_id": "a", "output": "ok"},
        {"role": "user", "content": "new"},
    ]
    result = budget.filter(payload(items))
    assert result.input == items[-1:]
    assert budget.input_bytes < settings.max_input_bytes
    assert budget.trimmed_turns == 1


@pytest.mark.parametrize(
    "instructions,content", [("X" * 5000, "hi"), ("rules", "中" * 2000)],
    ids=["instructions", "current-input"],
)
def test_oversized_current_turn_or_instructions_stop_before_request(
    settings, instructions, content
):
    settings.max_input_bytes = 4000
    budget = InputBudget(settings)
    with pytest.raises(ContextBudgetExceeded, match="本轮输入"):
        budget.filter(payload([{"role": "user", "content": content}], instructions))
    assert budget.requests == budget.input_bytes == 0


def test_tool_schemas_are_included_in_request_budget(settings):
    settings.max_input_bytes = 4000
    tool = SimpleNamespace(name="huge", description="X" * 5000, params_json_schema={})
    budget = InputBudget(settings)
    with pytest.raises(ContextBudgetExceeded):
        budget.filter(SimpleNamespace(
            model_data=ModelInputData(input=[{"role": "user", "content": "hi"}], instructions=""),
            agent=SimpleNamespace(tools=[tool]),
        ))
    assert budget.requests == 0


def test_cumulative_budget_stops_tool_loops_before_next_request(settings):
    settings.max_run_input_bytes = 4000
    budget = InputBudget(settings)
    data = payload([{"role": "user", "content": "X" * 2500}])
    budget.filter(data)
    with pytest.raises(ContextBudgetExceeded, match="累计输入预算"):
        budget.filter(data)
    assert budget.requests == 1


async def test_usage_and_output_limit_reach_api_and_provider(platform):
    app, provider = platform
    async with browser(app) as client:
        await login(client)
        thread = (await client.post("/api/threads")).json()["id"]
        run = await run_message(client, app, thread, "hello")
        detail = (await client.get(f"/api/threads/{thread}")).json()
        usage = detail["runs"][0]["usage"]
        assert usage["requests"] == 1
        assert usage["input_tokens"] == 20 and usage["output_tokens"] == 5
        assert usage["total_tokens"] == 25 and usage["usage_reported"] is True
        assert usage["input_bytes"] > json_bytes("hello")
        assert json.loads(run["usage"]) == usage
    assert provider.requests[0]["max_tokens"] == app.state.runtime.settings.max_output_tokens


async def test_long_history_is_bounded_without_deleting_conversation(platform):
    app, provider = platform
    app.state.runtime.settings.history_turns = 1
    async with browser(app) as client:
        await login(client)
        thread = (await client.post("/api/threads")).json()["id"]
        for question in ("First question", "Second question", "Third question"):
            await run_message(client, app, thread, question)
        sent = json.dumps(provider.requests[-1]["messages"])
        assert "First question" not in sent
        assert "Second question" in sent and "Third question" in sent
        detail = (await client.get(f"/api/threads/{thread}")).json()
        assert len(detail["messages"]) == 6


async def test_budget_failure_is_actionable_and_does_not_call_provider(platform):
    app, provider = platform
    app.state.runtime.settings.max_input_bytes = 4000
    async with browser(app) as client:
        await login(client)
        thread = (await client.post("/api/threads")).json()["id"]
        run = (await client.post(
            f"/api/threads/{thread}/messages", json={"content": "中" * 2000}
        )).json()
        if task := app.state.runtime.tasks.get(run["id"]):
            await task
        detail = (await client.get(f"/api/threads/{thread}")).json()
        assert detail["runs"][0]["status"] == "failed"
        assert "上下文预算" in detail["runs"][0]["error"]
        assert detail["runs"][0]["usage"]["requests"] == 0
    assert provider.requests == []


async def test_large_mcp_catalog_is_lazy_paginated_and_preserves_approval(platform, monkeypatch):
    app, _ = platform
    server = MCPServerStdio(
        params={"command": sys.executable}, name="large", require_approval="always",
    )
    definitions = [
        Tool(
            name=f"tool_{i}", description="description " * 1000,
            inputSchema={"type": "object", "properties": {"value": {"type": "string"}}},
        ) for i in range(100)
    ]
    listing = AsyncMock(return_value=definitions)
    monkeypatch.setattr(server, "list_tools", listing)
    agent = Agent(name="test")
    directory, load = app.state.runtime.mcp_tools([server], agent)
    agent.tools.extend([directory, load])
    assert not listing.called and len(agent.tools) == 2
    context = ToolContext(
        context=None, tool_name=directory.name, tool_call_id="catalog", tool_arguments="{}",
    )
    first = json.loads(await directory.on_invoke_tool(context, json.dumps({
        "server": "large", "query": "", "offset": 0,
    })))
    assert first["total"] == 100 and first["next_offset"] == 10
    assert len(first["tools"]) == 10
    assert "inputSchema" not in json.dumps(first)
    assert len(first["tools"][0]["description"]) == 200
    arguments = json.dumps({"server": "large", "name": "tool_25"})
    loaded = json.loads(await load.on_invoke_tool(context, arguments))
    assert len(agent.tools) == 3
    assert agent.tools[-1].name == loaded["function"]
    assert agent.tools[-1].needs_approval is True
    assert agent.tools[-1].params_json_schema["properties"]["value"]["type"] == "string"
    assert json.loads(await load.on_invoke_tool(context, arguments)) == loaded
    assert len(agent.tools) == 3
    missing = json.loads(await load.on_invoke_tool(context, json.dumps({
        "server": "large", "name": "not_allowed",
    })))
    assert "error" in missing and len(agent.tools) == 3


async def test_missing_provider_usage_is_explicitly_unknown(platform):
    app, provider = platform
    provider.report_usage = False
    async with browser(app) as client:
        await login(client)
        thread = (await client.post("/api/threads")).json()["id"]
        await run_message(client, app, thread, "hello")
        detail = (await client.get(f"/api/threads/{thread}")).json()
        usage = detail["runs"][0]["usage"]
        assert usage["requests"] == 1 and usage["usage_reported"] is False
        assert usage["input_bytes"] > 0


def test_usage_migration_keeps_existing_runs_and_is_repeatable(tmp_path):
    with sqlite3.connect(tmp_path / "agent.sqlite") as db:
        db.executescript("""
            CREATE TABLE runs(id TEXT PRIMARY KEY, thread_id TEXT, status TEXT, output TEXT,
                              error TEXT, created REAL, finished REAL);
            INSERT INTO runs VALUES('old', 'thread', 'completed', 'kept', '', 1, 2);
        """)
    store = Store(tmp_path)
    assert store.query("SELECT output,usage FROM runs WHERE id='old'") == [
        {"output": "kept", "usage": "{}"},
    ]
    store.save_run_usage("old", {"requests": 2})
    reopened = Store(tmp_path)
    assert json.loads(reopened.query("SELECT usage FROM runs WHERE id='old'")[0]["usage"]) == {
        "requests": 2,
    }
