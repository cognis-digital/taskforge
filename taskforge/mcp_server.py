"""taskforge MCP server — stdio JSON-RPC 2.0. Standard library only.

    {"command": "python", "args": ["-m", "taskforge", "mcp"]}
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, Optional

from taskforge import TOOL_NAME, TOOL_VERSION
from taskforge.core import (
    TaskforgeError,
    list_tasks,
    load_taskfile,
    plan_commands,
    run,
)

PROTOCOL_VERSION = "2024-11-05"

_TOOLS = [
    {
        "name": "list",
        "description": "List the tasks defined in a taskforge file.",
        "inputSchema": {
            "type": "object",
            "properties": {"file": {"type": "string"}},
            "required": ["file"], "additionalProperties": False,
        },
    },
    {
        "name": "plan",
        "description": "Compute the ordered command plan for a task (deps + "
                       "matrix + variable interpolation), without executing.",
        "inputSchema": {
            "type": "object",
            "properties": {"file": {"type": "string"}, "task": {"type": "string"}},
            "required": ["file", "task"], "additionalProperties": False,
        },
    },
    {
        "name": "run",
        "description": "Run a task and its dependencies; returns per-command "
                       "exit codes and output.",
        "inputSchema": {
            "type": "object",
            "properties": {"file": {"type": "string"}, "task": {"type": "string"},
                           "dry_run": {"type": "boolean"}},
            "required": ["file", "task"], "additionalProperties": False,
        },
    },
]


def _result(req_id, result): return {"jsonrpc": "2.0", "id": req_id, "result": result}
def _error(req_id, code, msg): return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": msg}}


def _call_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    f = args.get("file")
    if not isinstance(f, str) or not f:
        raise ValueError("`file` (string) is required")
    tf = load_taskfile(f)
    if name == "list":
        payload = {"tasks": list_tasks(tf)}
        is_error = False
    elif name == "plan":
        task = args.get("task")
        if not isinstance(task, str):
            raise ValueError("`task` (string) is required")
        payload = {"steps": plan_commands(tf, task)}
        is_error = False
    elif name == "run":
        task = args.get("task")
        if not isinstance(task, str):
            raise ValueError("`task` (string) is required")
        payload = run(tf, task, dry_run=bool(args.get("dry_run", False)))
        is_error = not payload.get("ok", True)
    else:
        raise ValueError(f"unknown tool: {name}")
    return {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}],
            "isError": is_error}


def handle_request(req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    method = req.get("method")
    req_id = req.get("id")
    params = req.get("params") or {}
    is_notification = "id" not in req

    if method == "initialize":
        res = _result(req_id, {"protocolVersion": PROTOCOL_VERSION,
                               "capabilities": {"tools": {"listChanged": False}},
                               "serverInfo": {"name": TOOL_NAME, "version": TOOL_VERSION}})
        return None if is_notification else res
    if method in ("notifications/initialized", "initialized"):
        return None
    if method == "ping":
        return None if is_notification else _result(req_id, {})
    if method == "tools/list":
        return _result(req_id, {"tools": _TOOLS})
    if method == "tools/call":
        name = params.get("name", "")
        args = params.get("arguments") or {}
        try:
            return _result(req_id, _call_tool(name, args))
        except (ValueError, OSError, TaskforgeError) as exc:
            return _error(req_id, -32602, str(exc))
        except Exception as exc:  # pragma: no cover
            return _error(req_id, -32603, f"internal error: {exc}")
    if is_notification:
        return None
    return _error(req_id, -32601, f"method not found: {method}")


def run_mcp_server(stdin=None, stdout=None) -> None:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            stdout.write(json.dumps(_error(None, -32700, "parse error")) + "\n")
            stdout.flush()
            continue
        response = handle_request(req)
        if response is not None:
            stdout.write(json.dumps(response) + "\n")
            stdout.flush()


if __name__ == "__main__":
    run_mcp_server()
