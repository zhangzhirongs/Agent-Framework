import json
from pathlib import Path

import httpx
import pytest
from agents import OpenAIChatCompletionsModel
from openai import AsyncOpenAI

from app.api import create_app
from app.config import Settings


@pytest.fixture
def settings(tmp_path):
    source = Path(__file__).resolve().parents[1]
    return Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        skills_dir=source / "skills",
        mcp_config=tmp_path / "mcp.json",
    )


class Provider:
    def __init__(self):
        self.requests = []
        self.report_usage = True
        self.file_content = "# Note\nDone"
        self.client = AsyncOpenAI(
            api_key="test-only",
            base_url="http://model.example.test/v1",
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(self.handle)),
        )
        self.model = OpenAIChatCompletionsModel(model="test-only", openai_client=self.client)

    async def handle(self, request):
        body = json.loads(request.content)
        self.requests.append(body)
        last = body["messages"][-1]
        text = json.dumps(last, ensure_ascii=False)
        tool_name = None
        arguments = {}
        if last["role"] == "user" and "use-skill" in text:
            tool_name, arguments = "load_skill", {"name": "example-note"}
        elif last["role"] == "user" and "write-file" in text:
            tool_name, arguments = (
                "write_text_file",
                {"filename": "note.md", "content": self.file_content},
            )
        elif last["role"] == "user" and "use-mcp" in text:
            tool_name, arguments = "find_tools", {"query": "ping", "offset": 0}
        elif last["role"] == "tool":
            try:
                result = json.loads(last["content"])
            except (json.JSONDecodeError, TypeError):
                result = {}
            if not isinstance(result, dict):
                result = {}
            found = result.get("tools", [])
            if found and found[0].get("function"):
                tool_name = found[0]["function"]
                if tool_name == "load_skill":
                    arguments = {"name": "example-note"}
                elif tool_name == "write_text_file":
                    arguments = {"filename": "note.md", "content": self.file_content}
                else:
                    arguments = {"value": "hello"}
        names = {tool["function"]["name"] for tool in body.get("tools", [])}
        if tool_name and tool_name not in names:
            arguments, tool_name = {"query": tool_name, "offset": 0}, "find_tools"
        delta = (
            {
                "tool_calls": [
                    {
                        "index": 0,
                        "id": f"call-test-{len(self.requests)}",
                        "type": "function",
                        "function": {"name": tool_name, "arguments": json.dumps(arguments)},
                    }
                ]
            }
            if tool_name
            else {"content": "工具已完成" if last["role"] == "tool" else "你好，这是一条测试回复"}
        )
        chunks = [
            {
                "id": "test",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "test-only",
                "choices": [
                    {"index": 0, "delta": {"role": "assistant", **delta}, "finish_reason": None}
                ],
            },
            {
                "id": "test",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "test-only",
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": "tool_calls" if tool_name else "stop",
                    }
                ],
            },
        ]
        if self.report_usage:
            chunks.append({
                "id": "test", "object": "chat.completion.chunk", "created": 1,
                "model": "test-only", "choices": [],
                "usage": {"prompt_tokens": 20, "completion_tokens": 5, "total_tokens": 25},
            })
        content = "".join("data: " + json.dumps(c, ensure_ascii=False) + "\n\n" for c in chunks)
        return httpx.Response(
            200, content=content + "data: [DONE]\n\n", headers={"content-type": "text/event-stream"}
        )


@pytest.fixture
async def platform(settings):
    provider = Provider()
    app = create_app(settings, provider.model)
    yield app, provider
    await app.state.runtime.close()
    await provider.client.close()


def browser(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost")


async def login(client, username="admin", password="123"):
    response = await client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return response.json()


async def run_message(client, app, thread, content, **extra):
    response = await client.post(
        f"/api/threads/{thread}/messages", json={"content": content, **extra}
    )
    assert response.status_code == 202, response.text
    run = response.json()
    if task := app.state.runtime.tasks.get(run["id"]):
        await task
    saved = app.state.store.query("SELECT * FROM runs WHERE id=?", (run["id"],))[0]
    assert saved["status"] == "completed", saved
    return saved
