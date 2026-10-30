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

from app.config import Settings
from app.runtime import ContextBudgetExceeded, InputBudget, json_bytes, text_page
from app.store import Store
from tests.conftest import browser, login, run_message


def payload(items, instructions="rules", tools=None):
    return SimpleNamespace(
        model_data=ModelInputData(input=items, instructions=instructions),
        agent=Agent(name="test", tools=tools or []),
    )


def test_default_history_limits_bound_replayed_context():
    settings = Settings()
    assert settings.history_turns == 4
    assert settings.history_message_chars == 4000
    assert settings.max_input_bytes == 128000
    assert settings.max_tool_output_chars == 12000
    assert settings.max_run_input_bytes == 512000


def test_tool_results_are_compacted_before_current_turn_is_rejected(settings):
    settings.max_input_bytes = 5000
    settings.max_tool_output_chars = 1000
    budget = InputBudget(settings)
    items = [
        {"role": "user", "content": "写文章"},
        {"type": "function_call", "call_id": "a", "name": "search", "arguments": "{}"},
        {"type": "function_call_output", "call_id": "a", "output": "A" * 4000},
        {"type": "function_call", "call_id": "b", "name": "search", "arguments": "{}"},
        {"type": "function_call_output", "call_id": "b", "output": "B" * 4000},
    ]
    result = budget.filter(payload(items))
    assert json.loads(result.input[-1]["output"])["preview"].startswith("B")
    assert len(result.input[2]["output"]) < 4000


def test_mcp_text_blocks_are_compacted_before_the_hard_limit(settings):
    items = [{"role": "user", "content": "write"}]
    for index in range(4):
        items.extend([
            {"type": "function_call", "call_id": str(index),
             "name": "read", "arguments": "{}"},
            {"type": "function_call_output", "call_id": str(index),
             "output": [{"type": "input_text", "text": "中" * 3500}]},
        ])
    original = copy.deepcopy(items)
    budget = InputBudget(settings)
    result = budget.filter(payload(items))
    assert isinstance(result.input[-1]["output"], str)
    assert result.input[-1]["output"] == "中" * 3500
    # A lower per-output limit exercises proactive compaction of structured MCP results.
    settings.max_tool_output_chars = 6000
    result = budget.filter(payload(items))
    assert len(json.loads(result.input[2]["output"])["preview"]) == 2000
    assert items == original


async def test_material_reader_bounds_and_ranks_evidence(platform, monkeypatch):
    from app.geoflow import GeoFlowClient

    app, _ = platform
    app.state.runtime.geoflow = GeoFlowClient("https://geo.example.test", "test-only")
    listing = AsyncMock(return_value={"items": [
        {"id": 1, "content": "unrelated " * 3000},
        {"id": 2, "content": "target " * 3000},
    ]})
    monkeypatch.setattr(app.state.runtime.geoflow, "material_items", listing)
    tool = next(t for t in app.state.runtime.tools("thread", [])
                if t.name == "geoflow_read_material")
    args = json.dumps({"material_type": "knowledge_bases", "material_id": 1,
                       "query": "target", "page": 1})
    context = ToolContext(context=None, tool_name=tool.name,
                          tool_call_id="read", tool_arguments=args)
    result = await tool.on_invoke_tool(context, args)
    assert result["excerpts"][0]["id"] == 2
    assert sum(len(row["content"]) for row in result["excerpts"]) <= 3200
    assert result["scope"] == "current_page"
    listing.assert_awaited_once_with("knowledge_bases", 1, page=1, per_page=20)


def test_history_keeps_conversation_without_replaying_tools_or_saved_images(settings):
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
    assert len(items) == 2
    assert budget.omitted_history_items == 2
    assert "data:image" not in json.dumps(items)
    assert history == original and items[-1] == new[0]
    assert budget.trimmed_turns == 1


def test_history_omits_reasoning_and_large_write_arguments_but_keeps_final_answer(settings):
    budget = InputBudget(settings)
    history = [
        {"role": "user", "content": "create a report"},
        {"type": "reasoning", "summary": [{"text": "secret chain"}]},
        {"type": "function_call", "arguments": "X" * 100000},
        {"type": "function_call_output", "output": "Y" * 100000},
        {"type": "message", "role": "assistant", "id": "provider-id",
         "content": [{"type": "output_text", "text": "Report saved."}]},
    ]
    original = copy.deepcopy(history)
    new = [{"role": "user", "content": "next"}]
    result = budget.session_input(history, new)
    assert len(result) == 3
    assert "Report saved." in json.dumps(result)
    assert "provider-id" not in json.dumps(result)
    assert budget.omitted_history_items == 3
    assert history == original


def test_historical_text_is_bounded_but_current_question_is_unchanged(settings):
    settings.history_message_chars = 256
    budget = InputBudget(settings)
    new = [{"role": "user", "content": "N" * 600}]
    history = [
        {"role": "user", "content": "U" * 10000},
        {"role": "assistant", "content": [
            {"type": "output_text", "text": "A" * 10000},
            {"type": "output_text", "text": "B" * 10000},
        ]},
    ]
    result = budget.session_input(history, new)
    assert len(result[0]["content"]) < 300
    assert len(result[1]["content"]) < 300
    assert "B" not in result[1]["content"]
    assert result[-1] == new[0]


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


@pytest.mark.parametrize("python_repr", [False, True])
def test_successful_file_write_does_not_replay_the_entire_document(settings, python_repr):
    budget = InputBudget(settings)
    saved = {"id": "saved-file", "name": "report.md"}
    items = [
        {"role": "user", "content": "create a report"},
        {"type": "function_call", "name": "write_text_file", "call_id": "write",
         "arguments": json.dumps({"filename": "report.md", "content": "X" * 50000})},
        {"type": "function_call_output", "call_id": "write",
         "output": str(saved) if python_repr else json.dumps(saved)},
    ]
    original = copy.deepcopy(items)
    result = budget.filter(payload(items))
    args = json.loads(result.input[1]["arguments"])
    assert args["filename"] == "report.md"
    assert "saved-file" in args["content"] and len(args["content"]) < 200
    assert items == original and budget.compacted_tool_arguments == 1


def test_failed_file_write_arguments_remain_available_for_retry(settings):
    items = [
        {"role": "user", "content": "create a report"},
        {"type": "function_call", "name": "write_text_file", "call_id": "write",
         "arguments": json.dumps({"filename": "report.md", "content": "X" * 5000})},
        {"type": "function_call_output", "call_id": "write", "output": "failed to save"},
    ]
    assert InputBudget(settings).filter(payload(items)).input == items


def test_text_pages_cover_the_document_without_repeating_the_first_page():
    text = "A" * 500 + "B" * 500
    first = text_page(text, 0, 500, 1000)
    second = text_page(text, 500, 500, 1000)
    assert "next_offset=500" in first and first.endswith("A" * 500)
    assert "next_offset=none" in second and second.endswith("B" * 500)
    assert len(text_page(text, -5, 100000, 1000)) <= 1000


def test_keyword_read_returns_a_matching_excerpt_instead_of_the_full_file():
    text = "A" * 5000 + "Target detail" + "B" * 5000
    result = text_page(text, 0, 500, 1000, "target")
    assert "Target detail" in result and len(result) < 600
    assert "未找到" in text_page(text, 0, 500, 1000, "missing")


async def test_unneeded_integrations_and_skill_catalog_add_no_initial_prompt_cost(platform):
    from app.geoflow import GeoFlowClient

    app, provider = platform
    async with browser(app) as client:
        await login(client)
        thread = (await client.post("/api/threads")).json()["id"]
        await run_message(client, app, thread, "hello")
        basic = provider.requests[-1]
        app.state.runtime.geoflow = GeoFlowClient("https://geo.example.test", "test-only")
        app.state.runtime.settings.search_provider = "tavily"
        thread = (await client.post("/api/threads")).json()["id"]
        await run_message(client, app, thread, "hello")
        integrated = provider.requests[-1]
        assert integrated["tools"] == basic["tools"]
        assert integrated["messages"] == basic["messages"]
        assert [t["function"]["name"] for t in integrated["tools"]] == ["find_tools"]
        assert "example-note" not in json.dumps(integrated["messages"])
        assert len(provider.requests) == 2


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


async def test_followup_does_not_send_previous_tool_transcripts_to_provider(platform):
    app, provider = platform
    async with browser(app) as client:
        await login(client)
        thread = (await client.post("/api/threads")).json()["id"]
        await run_message(client, app, thread, "write-file")
        assert any(m["role"] == "tool" for m in provider.requests[-1]["messages"])
        await run_message(client, app, thread, "follow up")
        sent = provider.requests[-1]["messages"]
        assert not any(m["role"] == "tool" or m.get("tool_calls") for m in sent)
        assert any(m["role"] == "assistant" for m in sent)


async def test_saved_document_is_intact_while_next_model_request_uses_a_reference(platform):
    app, provider = platform
    provider.file_content = "# Report\n" + "body " * 2000
    async with browser(app) as client:
        await login(client)
        thread = (await client.post("/api/threads")).json()["id"]
        run = await run_message(client, app, thread, "write-file")
        detail = (await client.get(f"/api/threads/{thread}")).json()
        file_id = detail["messages"][-1]["file_ids"][0]
        assert (await client.get(f"/api/files/{file_id}")).text == provider.file_content
        sent = json.dumps(provider.requests[-1]["messages"])
        assert "body " * 1000 not in sent
        assert file_id in sent and json.loads(run["usage"])["compacted_tool_arguments"] == 1


async def test_paged_reader_keeps_files_isolated_to_the_current_conversation(platform):
    from app.files import save_file

    app, _ = platform
    async with browser(app) as client:
        await login(client)
        first = (await client.post("/api/threads")).json()["id"]
        second = (await client.post("/api/threads")).json()["id"]
        text = "A" * 5000 + "PRIVATE_TARGET" + "B" * 1000
        file = save_file(app.state.store, first, "large.txt", text.encode())
        args = json.dumps({"file_id": file["id"], "offset": 0, "limit": 500,
                           "query": "private_target"})
        context = ToolContext(
            context=None, tool_name="read_file", tool_call_id="read", tool_arguments=args,
        )
        own = next(t for t in app.state.runtime.tools(first, []) if t.name == "read_file")
        other = next(t for t in app.state.runtime.tools(second, []) if t.name == "read_file")
        result = await own.on_invoke_tool(context, args)
        assert "PRIVATE_TARGET" in result and len(result) < 600
        assert "PRIVATE_TARGET" not in await other.on_invoke_tool(context, args)


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
    directory = app.state.runtime.discovery_tool([], [server], agent)
    agent.tools.append(directory)
    assert not listing.called and len(agent.tools) == 1
    context = ToolContext(
        context=None, tool_name=directory.name, tool_call_id="catalog", tool_arguments="{}",
    )
    first = json.loads(await directory.on_invoke_tool(context, json.dumps({
        "query": "", "offset": 0,
    })))
    assert first["total"] == 100 and first["next_offset"] == 8
    assert len(first["tools"]) == 8
    assert "inputSchema" not in json.dumps(first)
    assert len(first["tools"][0]["description"]) == 160
    arguments = json.dumps({"query": "tool_25", "offset": 0})
    loaded = json.loads(await directory.on_invoke_tool(context, arguments))
    assert len(agent.tools) == 2
    assert agent.tools[-1].name == loaded["tools"][0]["function"]
    assert agent.tools[-1].needs_approval is True
    assert agent.tools[-1].params_json_schema["properties"]["value"]["type"] == "string"
    assert json.loads(await directory.on_invoke_tool(context, arguments)) == loaded
    assert len(agent.tools) == 2
    missing = json.loads(await directory.on_invoke_tool(context, json.dumps({
        "query": "not_allowed", "offset": 0,
    })))
    assert missing["tools"] == [] and len(agent.tools) == 2
    assert listing.call_count == 1


async def test_discovery_matches_topic_words_without_requiring_every_word(platform):
    app, _ = platform
    server = MCPServerStdio(params={"command": sys.executable}, name="geoflow")
    server.list_tools = AsyncMock(return_value=[Tool(
        name="geoflow_get_material_items",
        description="Read knowledge chunks in a library",
        inputSchema={"type": "object", "properties": {}},
    )])
    agent = Agent(name="test")
    directory = app.state.runtime.discovery_tool([], [server], agent)
    context = ToolContext(context=None, tool_name=directory.name,
                          tool_call_id="find", tool_arguments="{}")
    result = json.loads(await directory.on_invoke_tool(context, json.dumps({
        "query": "geoflow knowledge base search", "offset": 0,
    })))
    assert result["tools"][0]["name"] == "geoflow_get_material_items"
    assert len(agent.tools) == 1


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
