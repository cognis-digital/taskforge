"""Core engine for taskforge — a declarative task runner.

taskforge runs tasks declared in a small ``taskforge.yaml`` (or ``.json``). A
task has a name, an optional list of dependency tasks, an optional set of
shell ``cmds``, variables, and an optional ``matrix`` that fans the task out
across combinations of values.

Features, all standard library:

  * dependency resolution with cycle detection (topological order)
  * variable interpolation (``${VAR}``) from task vars, file-level vars, env,
    and matrix values
  * ``matrix`` expansion — run a task once per combination of named value lists
  * ``includes`` — compose task files (later files override earlier names)
  * ``--dry-run`` — print the exact command plan without executing
  * deterministic, fail-fast execution with per-command exit handling

This is original Cognis Digital work; it shares no code, names, or branding
with any other task runner.
"""

from __future__ import annotations

import itertools
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

TOOL_NAME = "taskforge"
TOOL_VERSION = "0.1.0"

_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class TaskforgeError(Exception):
    """User-facing task-file / execution error."""


# --------------------------------------------------------------------------- #
# YAML subset parser (shared shape with the rest of the suite)
# --------------------------------------------------------------------------- #

def _coerce(text: str) -> Any:
    s = text.strip()
    if s in ("", "~", "null"):
        return None
    if s in ("true", "false"):
        return s == "true"
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    # Inline flow sequence: [a, b, c]
    if len(s) >= 2 and s[0] == "[" and s[-1] == "]":
        inner = s[1:-1].strip()
        if inner == "":
            return []
        return [_coerce(part) for part in _split_flow(inner)]
    # Inline flow mapping: {k: v, ...}
    if len(s) >= 2 and s[0] == "{" and s[-1] == "}":
        inner = s[1:-1].strip()
        obj: Dict[str, Any] = {}
        if inner:
            for part in _split_flow(inner):
                if ":" in part:
                    k, v = part.split(":", 1)
                    obj[k.strip().strip("\"'")] = _coerce(v)
        return obj
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def _split_flow(inner: str) -> List[str]:
    """Split a flow-collection body on top-level commas (respecting quotes/brackets)."""
    parts: List[str] = []
    depth = 0
    cur: List[str] = []
    sgl = dbl = False
    for ch in inner:
        if ch == "'" and not dbl:
            sgl = not sgl
        elif ch == '"' and not sgl:
            dbl = not dbl
        if not sgl and not dbl:
            if ch in "[{":
                depth += 1
            elif ch in "]}":
                depth -= 1
            elif ch == "," and depth == 0:
                parts.append("".join(cur).strip())
                cur = []
                continue
        cur.append(ch)
    if "".join(cur).strip():
        parts.append("".join(cur).strip())
    return parts


def parse_yaml_subset(text: str) -> Any:
    lines = text.replace("\t", "  ").splitlines()
    toks: List[Tuple[int, str]] = []
    for raw in lines:
        out, sgl, dbl = [], False, False
        for i, ch in enumerate(raw):
            if ch == "'" and not dbl:
                sgl = not sgl
            elif ch == '"' and not sgl:
                dbl = not dbl
            elif ch == "#" and not sgl and not dbl and (i == 0 or raw[i-1] in " \t"):
                break
            out.append(ch)
        line = "".join(out).rstrip()
        if not line.strip() or line.strip() == "---":
            continue
        indent = len(line) - len(line.lstrip(" "))
        toks.append((indent, line.strip()))
    if not toks:
        return {}
    pos = [0]

    def kv(s: str) -> Tuple[str, str]:
        i = s.find(":")
        if i == -1:
            return s, ""
        k, v = s[:i].strip(), s[i+1:].strip()
        if len(k) >= 2 and k[0] == k[-1] and k[0] in "\"'":
            k = k[1:-1]
        return k, v

    def parse_block(indent):
        if pos[0] >= len(toks):
            return None
        _cur, content = toks[pos[0]]
        return parse_list(indent) if content.startswith("- ") else parse_map(indent)

    def parse_list(indent):
        items = []
        while pos[0] < len(toks):
            cur, content = toks[pos[0]]
            if cur != indent or not content.startswith("- "):
                break
            inner = content[2:].strip()
            pos[0] += 1
            if ":" in inner and not (inner.find(":")+1 < len(inner)
                                     and inner[inner.find(":")+1] != " "):
                k, v = kv(inner)
                obj = {k: (_coerce(v) if v else _child(indent + 2))}
                obj.update(cont_map(indent + 2))
                items.append(obj)
            elif inner == "":
                items.append(_child(indent + 2))
            else:
                items.append(_coerce(inner))
        return items

    def cont_map(indent):
        obj = {}
        while pos[0] < len(toks):
            cur, content = toks[pos[0]]
            if cur != indent or content.startswith("- "):
                break
            k, v = kv(content)
            pos[0] += 1
            obj[k] = _coerce(v) if v else _child(indent + 2)
        return obj

    def parse_map(indent):
        obj = {}
        while pos[0] < len(toks):
            cur, content = toks[pos[0]]
            if cur != indent or content.startswith("- "):
                break
            k, v = kv(content)
            pos[0] += 1
            obj[k] = _coerce(v) if v else _child(indent + 1)
        return obj

    def _child(min_indent):
        if pos[0] >= len(toks):
            return None
        cur, content = toks[pos[0]]
        if cur < min_indent:
            return None
        return parse_list(cur) if content.startswith("- ") else parse_map(cur)

    result = parse_block(0)
    return result if result is not None else {}


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #

@dataclass
class Task:
    name: str
    desc: str = ""
    deps: List[str] = field(default_factory=list)
    cmds: List[str] = field(default_factory=list)
    vars: Dict[str, Any] = field(default_factory=dict)
    matrix: Dict[str, List[Any]] = field(default_factory=dict)
    dir: Optional[str] = None


@dataclass
class TaskFile:
    vars: Dict[str, Any]
    tasks: Dict[str, Task]
    base_dir: str


def load_taskfile(path: str, _seen: Optional[set] = None) -> TaskFile:
    """Load a task file, recursively merging ``includes``."""
    _seen = _seen or set()
    apath = os.path.abspath(path)
    if apath in _seen:
        raise TaskforgeError(f"include cycle at {path}")
    _seen.add(apath)
    if not os.path.isfile(path):
        raise TaskforgeError(f"task file not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    ext = os.path.splitext(path)[1].lower()
    try:
        data = (json.loads(text) if ext == ".json"
                else parse_yaml_subset(text))
    except (json.JSONDecodeError, ValueError) as exc:
        raise TaskforgeError(f"could not parse {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise TaskforgeError("task file root must be a mapping")

    base_dir = os.path.dirname(apath)
    merged_vars: Dict[str, Any] = {}
    merged_tasks: Dict[str, Task] = {}

    for inc in data.get("includes", []) or []:
        inc_path = inc if os.path.isabs(inc) else os.path.join(base_dir, inc)
        sub = load_taskfile(inc_path, _seen)
        merged_vars.update(sub.vars)
        merged_tasks.update(sub.tasks)

    merged_vars.update(data.get("vars", {}) or {})

    raw_tasks = data.get("tasks", {}) or {}
    if not isinstance(raw_tasks, dict):
        raise TaskforgeError("`tasks` must be a mapping of name -> task")
    for name, spec in raw_tasks.items():
        spec = spec or {}
        cmds = spec.get("cmds", spec.get("cmd", []))
        if isinstance(cmds, str):
            cmds = [cmds]
        deps = spec.get("deps", [])
        if isinstance(deps, str):
            deps = [deps]
        matrix = spec.get("matrix", {}) or {}
        for mk, mv in matrix.items():
            if not isinstance(mv, list):
                matrix[mk] = [mv]
        merged_tasks[name] = Task(
            name=name, desc=spec.get("desc", ""), deps=list(deps),
            cmds=list(cmds or []), vars=spec.get("vars", {}) or {},
            matrix=matrix, dir=spec.get("dir"))

    return TaskFile(vars=merged_vars, tasks=merged_tasks, base_dir=base_dir)


# --------------------------------------------------------------------------- #
# Dependency resolution
# --------------------------------------------------------------------------- #

def resolve_order(tf: TaskFile, target: str) -> List[str]:
    """Return a topologically ordered list of tasks to run for ``target``."""
    if target not in tf.tasks:
        raise TaskforgeError(f"unknown task: {target}")
    order: List[str] = []
    visiting: set = set()
    done: set = set()

    def visit(name: str, stack: List[str]) -> None:
        if name in done:
            return
        if name in visiting:
            cyc = " -> ".join(stack + [name])
            raise TaskforgeError(f"dependency cycle: {cyc}")
        if name not in tf.tasks:
            raise TaskforgeError(f"unknown dependency: {name} "
                                 f"(via {' -> '.join(stack)})")
        visiting.add(name)
        for dep in tf.tasks[name].deps:
            visit(dep, stack + [name])
        visiting.discard(name)
        done.add(name)
        order.append(name)

    visit(target, [])
    return order


# --------------------------------------------------------------------------- #
# Interpolation + matrix expansion
# --------------------------------------------------------------------------- #

def interpolate(text: str, scope: Dict[str, Any]) -> str:
    def repl(m):
        key = m.group(1)
        if key in scope:
            return str(scope[key])
        if key in os.environ:
            return os.environ[key]
        return m.group(0)  # leave ${UNKNOWN} untouched
    return _VAR_RE.sub(repl, text)


def expand_matrix(matrix: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
    """Cartesian product of named value lists -> list of scope dicts."""
    if not matrix:
        return [{}]
    keys = list(matrix.keys())
    combos = itertools.product(*(matrix[k] for k in keys))
    return [dict(zip(keys, c)) for c in combos]


def plan_commands(tf: TaskFile, target: str) -> List[Dict[str, Any]]:
    """Compute the full ordered command plan (with matrix + interpolation)."""
    plan: List[Dict[str, Any]] = []
    for name in resolve_order(tf, target):
        task = tf.tasks[name]
        for mscope in expand_matrix(task.matrix):
            scope: Dict[str, Any] = {}
            scope.update(tf.vars)
            scope.update(task.vars)
            scope.update(mscope)
            for cmd in task.cmds:
                plan.append({
                    "task": name,
                    "matrix": mscope or None,
                    "command": interpolate(cmd, scope),
                    "dir": task.dir,
                })
    return plan


# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #

def run(tf: TaskFile, target: str, *, dry_run: bool = False,
        cwd: Optional[str] = None) -> Dict[str, Any]:
    """Execute (or with dry_run, just plan) the command plan for ``target``."""
    plan = plan_commands(tf, target)
    base = cwd or tf.base_dir
    if dry_run:
        return {"target": target, "dry_run": True, "steps": plan,
                "executed": [], "ok": True}

    executed: List[Dict[str, Any]] = []
    ok = True
    for step in plan:
        run_dir = step["dir"] or base
        if not os.path.isabs(run_dir):
            run_dir = os.path.join(base, run_dir)
        try:
            proc = subprocess.run(step["command"], shell=True, cwd=run_dir,
                                  capture_output=True, text=True, timeout=600)
            rc = proc.returncode
            executed.append({"task": step["task"], "command": step["command"],
                             "returncode": rc,
                             "stdout": proc.stdout[-4000:],
                             "stderr": proc.stderr[-4000:]})
            if rc != 0:
                ok = False
                break  # fail fast
        except (subprocess.TimeoutExpired, OSError) as exc:
            executed.append({"task": step["task"], "command": step["command"],
                             "returncode": 1, "stdout": "", "stderr": str(exc)})
            ok = False
            break
    return {"target": target, "dry_run": False, "steps": plan,
            "executed": executed, "ok": ok}


def list_tasks(tf: TaskFile) -> List[Dict[str, Any]]:
    return [{"name": t.name, "desc": t.desc, "deps": t.deps,
             "matrix": list(t.matrix.keys()), "cmd_count": len(t.cmds)}
            for t in sorted(tf.tasks.values(), key=lambda x: x.name)]


# --------------------------------------------------------------------------- #
# AI hook (opt-in, default OFF)
# --------------------------------------------------------------------------- #

def draft_taskfile(description: str) -> Dict[str, Any]:
    """Draft a taskforge file from a plain-English pipeline description.

    Off by default; deterministic scaffold unless COGNIS_AI_* is configured.
    """
    out = {"vars": {}, "tasks": {"default": {"desc": description.strip()[:120],
                                             "cmds": ["echo configure me"]}},
           "_ai": "disabled — set COGNIS_AI_BACKEND to enable"}
    backend = _load_ai_backend()
    if backend is None or not backend.is_enabled() or not backend.health():
        return out
    prompt = ("Output ONLY JSON for a task runner with keys 'vars' (map) and "
              "'tasks' (map of name -> {desc, deps[], cmds[]}). No prose.\n\n"
              f"PIPELINE:\n{description}\n")
    try:
        content = backend._chat("Return strict JSON only.", prompt)
    except Exception:
        return out
    parsed = _extract_json_object(content or "")
    if isinstance(parsed, dict) and "tasks" in parsed:
        parsed.setdefault("vars", {})
        parsed["_ai"] = "drafted by local fleet"
        return parsed
    return out


def _load_ai_backend():
    import importlib.util
    here = os.path.dirname(os.path.abspath(__file__))
    cand = os.path.abspath(os.path.join(here, "..", "..", "..", "_shared",
                                        "cognis_ai_backend.py"))
    if os.path.isfile(cand):
        try:
            spec = importlib.util.spec_from_file_location("cognis_ai_backend", cand)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            return mod.CognisAIBackend()
        except Exception:
            return None
    return None


def _extract_json_object(text: str) -> Any:
    text = (text or "").strip()
    if "```" in text:
        m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if m:
            text = m.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
