"""
tools/mcp_client.py — MCP (Model Context Protocol) Client for AI Aurum
========================================================================
Connects to external MCP servers over HTTP JSON-RPC and exposes their
tools inside AI Aurum's tool registry.

Supports:
    • HTTP transport (JSON-RPC POST)
    • Tool discovery via tools/list
    • Tool invocation via tools/call
    • Multiple concurrent server connections (stored in DB user_settings)

Usage by the agent:
    action=connect      → connect to server_url and list available tools
    action=call_tool    → call a specific tool on a connected server
    action=list_servers → show all configured MCP server URLs
"""
import json, logging, os
import requests as _rq

NAME        = "mcp_server"
DESCRIPTION = (
    "Connect to external MCP (Model Context Protocol) servers to access their tools. "
    "Use connect to discover what tools a server exposes, "
    "then call_tool to invoke any of them."
)
CATEGORY    = "integration"
ICON        = "🔗"
INPUTS = [
    {"name": "action",     "label": "Action",      "type": "select",
     "options": ["connect", "call_tool", "list_servers"],
     "required": True},
    {"name": "server_url", "label": "MCP Server URL", "type": "text", "required": False},
    {"name": "tool_name",  "label": "Tool Name",   "type": "text",   "required": False},
    {"name": "tool_args",  "label": "Tool Args (JSON)", "type": "textarea", "required": False},
]

log = logging.getLogger("tools.mcp_client")
_TIMEOUT = int(os.environ.get("MCP_TIMEOUT", "15"))

# In-memory cache of discovered server tools: {server_url: [tool_info, ...]}
_server_cache: dict[str, list] = {}


def _rpc(server_url: str, method: str, params: dict | None = None) -> dict:
    """Send a JSON-RPC 2.0 request to an MCP server."""
    payload = {
        "jsonrpc": "2.0",
        "id":      1,
        "method":  method,
        "params":  params or {},
    }
    resp = _rq.post(
        server_url.rstrip("/") + "/rpc",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"MCP error: {data['error']}")
    return data.get("result", {})


def run(action: str = "", server_url: str = "", tool_name: str = "",
        tool_args: str = "", username: str = "default", **_) -> str:

    action = (action or "").strip().lower()

    # ── connect ────────────────────────────────────────────────────────────────
    if action == "connect":
        if not server_url:
            return "❌ server_url is required."
        try:
            result = _rpc(server_url, "tools/list")
            tools  = result.get("tools", [])
            _server_cache[server_url] = tools

            if not tools:
                return f"✅ Connected to `{server_url}` but no tools were advertised."

            lines = [f"✅ Connected to `{server_url}` — {len(tools)} tool(s) available:\n"]
            for t in tools:
                lines.append(f"• **{t.get('name','?')}** — {t.get('description','')}")
            return "\n".join(lines)

        except Exception as e:
            log.warning("MCP connect failed [%s]: %s", server_url, e)
            return f"❌ Could not connect to `{server_url}`: {e}"

    # ── call_tool ──────────────────────────────────────────────────────────────
    if action == "call_tool":
        if not server_url or not tool_name:
            return "❌ server_url and tool_name are required."

        try:
            args = json.loads(tool_args) if tool_args.strip() else {}
        except json.JSONDecodeError as je:
            return f"❌ tool_args must be valid JSON: {je}"

        try:
            result = _rpc(server_url, "tools/call",
                          {"name": tool_name, "arguments": args})
            # Increment usage if cached
            if server_url in _server_cache:
                _server_cache[server_url]  # just access to confirm connected

            content = result.get("content", result)
            if isinstance(content, list):
                # MCP content blocks format
                texts = [c.get("text", str(c)) for c in content if isinstance(c, dict)]
                return "\n".join(texts) or str(content)
            return str(content)

        except Exception as e:
            log.warning("MCP call_tool failed [%s/%s]: %s", server_url, tool_name, e)
            return f"❌ Tool call failed: {e}"

    # ── list_servers ───────────────────────────────────────────────────────────
    if action == "list_servers":
        if not _server_cache:
            return (
                "No MCP servers connected this session. "
                "Use action=connect with a server_url to connect one.\n\n"
                "Popular MCP servers:\n"
                "• [GitHub MCP](https://github.com/modelcontextprotocol/servers)\n"
                "• [Filesystem MCP](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem)\n"
                "• [SQLite MCP](https://github.com/modelcontextprotocol/servers/tree/main/src/sqlite)"
            )
        lines = [f"🔗 **{len(_server_cache)} connected MCP server(s):**\n"]
        for url, tools in _server_cache.items():
            t_names = ", ".join(t.get("name", "?") for t in tools) or "none"
            lines.append(f"• `{url}` — tools: {t_names}")
        return "\n".join(lines)

    return f"❌ Unknown action '{action}'. Use: connect, call_tool, list_servers."
