"""Command-line interface for taskforge."""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from taskforge import TOOL_NAME, TOOL_VERSION
from taskforge.core import (
    TaskforgeError,
    list_tasks,
    load_taskfile,
    plan_commands,
    run,
)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Declarative task runner — deps, variable interpolation, "
                    "matrix fan-out, includes, and dry-run command plans.")
    p.add_argument("--version", action="version",
                   version=f"{TOOL_NAME} {TOOL_VERSION}")
    p.add_argument("-f", "--file", default="taskforge.yaml",
                   help="Task file (default: taskforge.yaml).")
    sub = p.add_subparsers(dest="command")

    r = sub.add_parser("run", help="Run a task (and its dependencies).")
    r.add_argument("task")
    r.add_argument("--dry-run", action="store_true",
                   help="Print the command plan without executing.")
    r.add_argument("--format", choices=("table", "json"), default="table")

    sub.add_parser("list", help="List the tasks defined in the file.")

    g = sub.add_parser("graph", help="Show the resolved run order for a task.")
    g.add_argument("task")

    sub.add_parser("mcp", help="Run as an MCP server (stdio JSON-RPC).")
    return p


def _run_run(a) -> int:
    try:
        tf = load_taskfile(a.file)
        res = run(tf, a.task, dry_run=a.dry_run)
    except (OSError, TaskforgeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if a.format == "json":
        print(json.dumps(res, indent=2))
    else:
        mode = "DRY RUN — nothing executed" if res["dry_run"] else "RUN"
        print(f"taskforge {a.task}  [{mode}]")
        print("=" * 60)
        for step in res["steps"]:
            mlabel = f" {step['matrix']}" if step.get("matrix") else ""
            print(f"  [{step['task']}{mlabel}] $ {step['command']}")
        if not res["dry_run"]:
            print("-" * 60)
            for e in res["executed"]:
                tag = "ok" if e["returncode"] == 0 else f"rc={e['returncode']}"
                print(f"  [{tag}] {e['task']}: {e['command']}")
                if e["returncode"] != 0 and e["stderr"]:
                    print(f"        {e['stderr'].strip()}")
            print("RESULT: " + ("PASS" if res["ok"] else "FAIL"))
    return 0 if res["ok"] else 1


def _run_list(a) -> int:
    try:
        tf = load_taskfile(a.file)
    except (OSError, TaskforgeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    tasks = list_tasks(tf)
    print(f"taskforge — {len(tasks)} task(s) in {a.file}")
    print("=" * 60)
    for t in tasks:
        deps = f"  (deps: {', '.join(t['deps'])})" if t["deps"] else ""
        mtx = f"  [matrix: {', '.join(t['matrix'])}]" if t["matrix"] else ""
        print(f"  {t['name']:<16} {t['desc']}{deps}{mtx}")
    return 0


def _run_graph(a) -> int:
    from taskforge.core import resolve_order
    try:
        tf = load_taskfile(a.file)
        order = resolve_order(tf, a.task)
    except (OSError, TaskforgeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(" -> ".join(order))
    return 0


def _run_mcp() -> int:
    from taskforge.mcp_server import run_mcp_server
    run_mcp_server()
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return _run_run(args)
    if args.command == "list":
        return _run_list(args)
    if args.command == "graph":
        return _run_graph(args)
    if args.command == "mcp":
        return _run_mcp()
    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
