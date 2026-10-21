"""Standard mcpServers registry with environment-only secret references."""

import json
import os
import re
import tempfile
from contextlib import AsyncExitStack, asynccontextmanager

from agents.mcp import MCPServerSse, MCPServerStdio, MCPServerStreamableHttp

from app.skills import NAME

ENV = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def expand(value):
    def resolve(match):
        result = os.getenv(match.group(1), "")
        if not result:
            raise ValueError("MCP 所需环境变量尚未配置")
        return result

    return ENV.sub(resolve, value)


class Connectors:
    def __init__(self, path):
        self.path = path

    def configs(self):
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text("utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("mcpServers"), dict):
            raise ValueError("MCP 配置必须包含 mcpServers 对象")
        self.validate(data["mcpServers"])
        return data["mcpServers"]

    @staticmethod
    def validate(servers):
        if not isinstance(servers, dict) or len(servers) > 32:
            raise ValueError("最多配置 32 个 MCP 连接器")
        for name, config in servers.items():
            if (
                not isinstance(name, str)
                or not NAME.fullmatch(name)
                or not isinstance(config, dict)
            ):
                raise ValueError("MCP 名称或配置无效")
            if not config.get("command") and not config.get("url"):
                raise ValueError("MCP 需要 command 或 url")
            if config.get("command") and not isinstance(config["command"], str):
                raise ValueError("command 必须是字符串")
            args = config.get("args", [])
            if not isinstance(args, list) or any(not isinstance(arg, str) for arg in args):
                raise ValueError("args 必须是字符串数组")
            if not isinstance(config.get("enabled", True), bool):
                raise ValueError("enabled 必须是布尔值")
            allowed = config.get("allowed_tools")
            if allowed is not None and (
                not isinstance(allowed, list) or any(not isinstance(v, str) for v in allowed)
            ):
                raise ValueError("allowed_tools 必须是字符串数组")
            if config.get("type", "streamable_http") not in ("stdio", "streamable_http", "sse"):
                raise ValueError("MCP 传输类型无效")
            for values in (config.get("env", {}), config.get("headers", {})):
                if not isinstance(values, dict) or any(
                    not isinstance(v, str) or not ENV.search(v) for v in values.values()
                ):
                    raise ValueError("MCP 的 env 和 headers 必须引用 ${ENV_NAME} 环境变量")
            url = config.get("url", "")
            if not isinstance(url, str) or (url and not url.startswith(("https://", "http://"))):
                raise ValueError("MCP 地址必须是 HTTP 或 HTTPS")

    def save(self, servers):
        self.validate(servers)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=self.path.parent, prefix=".mcp-")
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump({"mcpServers": servers}, stream, ensure_ascii=False, indent=2)
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @asynccontextmanager
    async def connect(self):
        async with AsyncExitStack() as stack:
            servers = []
            for name, config in self.configs().items():
                if config.get("enabled", True) is False:
                    continue
                options = {
                    "name": name,
                    "client_session_timeout_seconds": 60,
                    "cache_tools_list": True,
                }
                allowed = config.get("allowed_tools")
                if allowed is not None:
                    options["tool_filter"] = {"allowed_tool_names": allowed}
                if config.get("command"):
                    params = {
                        "command": config["command"],
                        "args": config.get("args", []),
                        "env": {k: expand(v) for k, v in config.get("env", {}).items()},
                    }
                    server = MCPServerStdio(params=params, **options)
                else:
                    params = {
                        "url": expand(config["url"]),
                        "headers": {k: expand(v) for k, v in config.get("headers", {}).items()},
                    }
                    factory = (
                        MCPServerSse if config.get("type") == "sse" else MCPServerStreamableHttp
                    )
                    server = factory(params=params, **options)
                servers.append(await stack.enter_async_context(server))
            yield servers
