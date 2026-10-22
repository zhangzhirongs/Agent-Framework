"""Standard mcpServers registry with environment-only secret references."""

import json
import os
import re
import shutil
import sys
import tempfile
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

import httpx
from agents.mcp import MCPServerSse, MCPServerStdio, MCPServerStreamableHttp
from dotenv import dotenv_values

from app.config import ROOT
from app.skills import NAME

ENV = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class ConnectorError(Exception):
    """A safe, actionable connection failure without provider exception text."""


def expand(value, environment=None):
    environment = os.environ if environment is None else environment

    def resolve(match):
        result = environment.get(match.group(1), "")
        if not result:
            raise ConnectorError(f"缺少环境变量 {match.group(1)}，请在 .env 或服务进程环境中配置")
        return result

    return ENV.sub(resolve, value)


class Connectors:
    def __init__(self, path):
        self.path = path

    def parameters(self, config):
        # Settings reads .env but does not export its values to os.environ.
        environment = {**dotenv_values(ROOT / ".env"), **os.environ}
        if config.get("command"):
            command = expand(config["command"], environment)
            if command in ("python", "python3"):
                command = sys.executable
            if not shutil.which(command):
                raise ConnectorError(
                    "找不到启动命令，请安装所需依赖或将 command 设为可执行文件绝对路径"
                )
            args = [expand(arg, environment) for arg in config.get("args", [])]
            cwd = Path(expand(config.get("cwd", str(ROOT)), environment)).expanduser()
            if not cwd.is_absolute():
                cwd = ROOT / cwd
            if not cwd.is_dir():
                raise ConnectorError("工作目录 cwd 不存在")
            if args and args[0].endswith(".py") and not (cwd / args[0]).is_file():
                raise ConnectorError("Python 启动脚本不存在，请检查 args 中的脚本路径")
            return {
                "command": command,
                "args": args,
                "cwd": str(cwd),
                "env": {k: expand(v, environment) for k, v in config.get("env", {}).items()},
            }
        return {
            "url": expand(config["url"], environment),
            "headers": {k: expand(v, environment) for k, v in config.get("headers", {}).items()},
        }

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
            if "cwd" in config and (not isinstance(config["cwd"], str) or not config["cwd"]):
                raise ValueError("cwd 必须是非空字符串")
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
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
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
                    factory = MCPServerStdio
                else:
                    factory = (
                        MCPServerSse if config.get("type") == "sse" else MCPServerStreamableHttp
                    )
                try:
                    server = factory(params=self.parameters(config), **options)
                    servers.append(await stack.enter_async_context(server))
                except Exception as error:
                    raise ConnectorError(
                        f"MCP「{name}」连接失败：{connection_reason(error)}"
                    ) from None
            yield servers


def connection_reason(error):
    if isinstance(error, ConnectorError):
        return str(error)
    if isinstance(error, BaseExceptionGroup):
        return "；".join(dict.fromkeys(connection_reason(item) for item in error.exceptions))
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        if status in (401, 403):
            return f"认证失败（HTTP {status}），请检查认证环境变量及访问权限"
        return f"服务返回 HTTP {status}，请检查 MCP 端点地址和传输类型"
    if isinstance(error, (TimeoutError, httpx.TimeoutException)):
        return "连接或初始化超时，请检查服务是否启动及网络是否可达"
    if isinstance(error, httpx.ConnectError):
        return "无法访问服务，请检查地址、端口、网络及 TLS 证书"
    return "服务进程退出或 MCP 握手失败，请检查启动脚本、运行依赖和服务端日志"
