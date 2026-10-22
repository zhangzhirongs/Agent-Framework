import sys

import httpx
import pytest

from app.connectors import ConnectorError, Connectors, connection_reason
from scripts.geoflow_mcp import command
from tests.conftest import browser, login


def test_connector_reads_dotenv_without_exporting_secrets(tmp_path, monkeypatch):
    monkeypatch.setattr("app.connectors.ROOT", tmp_path)
    (tmp_path / ".env").write_text("MCP_TEST_TOKEN=dotenv-secret\n", "utf-8")
    monkeypatch.delenv("MCP_TEST_TOKEN", raising=False)
    registry = Connectors(tmp_path / "mcp.json")
    config = {"url": "https://example.test/mcp", "headers": {"Auth": "${MCP_TEST_TOKEN}"}}
    assert registry.parameters(config)["headers"] == {"Auth": "dotenv-secret"}
    monkeypatch.setenv("MCP_TEST_TOKEN", "process-secret")
    assert registry.parameters(config)["headers"] == {"Auth": "process-secret"}


def test_python_uses_backend_interpreter_and_stable_working_directory(tmp_path):
    from app.config import ROOT

    params = Connectors(tmp_path / "mcp.json").parameters(
        {"command": "python", "args": ["examples/echo_mcp.py"]}
    )
    assert params["command"] == sys.executable
    assert params["cwd"] == str(ROOT)


@pytest.mark.parametrize(
    ("config", "message"),
    [
        ({"command": "missing-mcp-command-fixture"}, "找不到启动命令"),
        ({"command": "python", "args": ["missing-script.py"]}, "Python 启动脚本不存在"),
        ({"url": "https://example.test/${MCP_TEST_UNSET}"}, "MCP_TEST_UNSET"),
    ],
)
async def test_connection_errors_identify_server_without_credentials(
    platform, monkeypatch, config, message
):
    monkeypatch.delenv("MCP_TEST_UNSET", raising=False)
    app, _ = platform
    app.state.runtime.connectors.save({"broken": config})
    async with browser(app) as client:
        await login(client)
        response = await client.post("/api/connectors/test")
    assert response.status_code == 502
    assert "broken" in response.json()["detail"]
    assert message in response.json()["detail"]


def test_transport_error_details_never_include_provider_secrets():
    error = httpx.HTTPStatusError(
        "secret-token", request=httpx.Request("GET", "https://example.test/secret-token"),
        response=httpx.Response(401),
    )
    reason = connection_reason(ExceptionGroup("secret-token", [error]))
    assert "401" in reason
    assert "secret-token" not in reason
    assert "secret-token" not in connection_reason(RuntimeError("secret-token"))


def test_geoflow_docker_transport_preserves_stdio(monkeypatch):
    monkeypatch.setattr("scripts.geoflow_mcp.shutil.which", lambda name: name)
    args, cwd = command({"GEOFLOW_DOCKER_CONTAINER": "geoflow-app"})
    assert args == ["docker", "exec", "-i", "geoflow-app", "php", "artisan", "boost:mcp"]
    assert cwd is None
    args, _ = command({"GEOFLOW_DOCKER_CONTAINER": "geoflow-app", "GEOFLOW_ARTISAN_ENV": "local"})
    assert args[-1] == "--env=local"


def test_geoflow_local_transport_requires_php(tmp_path, monkeypatch):
    (tmp_path / "artisan").touch()
    (tmp_path / "vendor").mkdir()
    (tmp_path / "vendor" / "autoload.php").touch()
    monkeypatch.setattr("scripts.geoflow_mcp.shutil.which", lambda name: None)
    with pytest.raises(ValueError, match="找不到 PHP"):
        command({"GEOFLOW_ROOT": str(tmp_path)})


def test_missing_env_error_has_no_values(monkeypatch):
    from app.connectors import expand

    monkeypatch.delenv("MCP_TEST_UNSET", raising=False)
    with pytest.raises(ConnectorError, match="MCP_TEST_UNSET"):
        expand("${MCP_TEST_UNSET}")
