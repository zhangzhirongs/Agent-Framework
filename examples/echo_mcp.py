"""Local MCP smoke-test server. No credentials or external requests."""

from mcp.server.mcpserver import MCPServer

server = MCPServer("example")


@server.tool()
def ping(value: str) -> str:
    """Echo a value to verify the MCP connection."""
    return "pong: " + value


if __name__ == "__main__":
    server.run(transport="stdio")
