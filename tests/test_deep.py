"""Deep tests for taskforge — deps, cycles, matrix, includes, run, MCP."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from taskforge import (
    draft_taskfile,
    expand_matrix,
    interpolate,
    load_taskfile,
    parse_yaml_subset,
    plan_commands,
    resolve_order,
    run,
)
from taskforge.core import TaskforgeError
from taskforge import mcp_server

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(REPO_ROOT, "demos", "01-basic", "taskforge.yaml")


def _write(tmp, name, text):
    p = os.path.join(tmp, name)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text)
    return p


class TestInterpolation(unittest.TestCase):
    def test_var_and_env(self):
        os.environ["TF_TEST_ENV"] = "envval"
        self.assertEqual(interpolate("${a}-${TF_TEST_ENV}", {"a": "x"}), "x-envval")

    def test_unknown_left_intact(self):
        self.assertEqual(interpolate("${nope}", {}), "${nope}")


class TestMatrix(unittest.TestCase):
    def test_product(self):
        combos = expand_matrix({"a": [1, 2], "b": ["x", "y"]})
        self.assertEqual(len(combos), 4)

    def test_empty(self):
        self.assertEqual(expand_matrix({}), [{}])


class TestDeps(unittest.TestCase):
    def test_order(self):
        tf = load_taskfile(DEMO)
        self.assertEqual(resolve_order(tf, "build"), ["clean", "build"])

    def test_cycle_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(tmp, "t.yaml",
                       "tasks:\n  a:\n    deps: [b]\n  b:\n    deps: [a]\n")
            tf = load_taskfile(p)
            with self.assertRaises(TaskforgeError):
                resolve_order(tf, "a")

    def test_unknown_dep(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(tmp, "t.yaml", "tasks:\n  a:\n    deps: [ghost]\n")
            tf = load_taskfile(p)
            with self.assertRaises(TaskforgeError):
                resolve_order(tf, "a")


class TestIncludes(unittest.TestCase):
    def test_include_merges_and_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, "base.yaml",
                   "vars:\n  shared: base\ntasks:\n  common:\n    cmds:\n      - echo common\n")
            main_path = _write(tmp, "main.yaml",
                               "includes:\n  - base.yaml\nvars:\n  app: x\n"
                               "tasks:\n  go:\n    deps: [common]\n    cmds:\n      - echo ${shared}-${app}\n")
            tf = load_taskfile(main_path)
            self.assertIn("common", tf.tasks)
            self.assertIn("go", tf.tasks)
            steps = plan_commands(tf, "go")
            self.assertTrue(any("base-x" in s["command"] for s in steps))

    def test_include_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, "a.yaml", "includes:\n  - b.yaml\ntasks: {}\n")
            _write(tmp, "b.yaml", "includes:\n  - a.yaml\ntasks: {}\n")
            with self.assertRaises(TaskforgeError):
                load_taskfile(os.path.join(tmp, "a.yaml"))


class TestRun(unittest.TestCase):
    def test_real_run_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(tmp, "t.yaml",
                       "tasks:\n  hi:\n    cmds:\n      - echo hello\n")
            res = run(load_taskfile(p), "hi")
            self.assertTrue(res["ok"])
            self.assertEqual(res["executed"][0]["returncode"], 0)

    def test_fail_fast(self):
        with tempfile.TemporaryDirectory() as tmp:
            # First command fails -> second never runs.
            p = _write(tmp, "t.yaml",
                       "tasks:\n  bad:\n    cmds:\n      - exit 3\n      - echo never\n")
            res = run(load_taskfile(p), "bad")
            self.assertFalse(res["ok"])
            self.assertEqual(len(res["executed"]), 1)


class TestYaml(unittest.TestCase):
    def test_parse_nested(self):
        data = parse_yaml_subset("tasks:\n  a:\n    cmds:\n      - echo x\n    deps:\n      - b\n")
        self.assertEqual(data["tasks"]["a"]["deps"], ["b"])


class TestMcp(unittest.TestCase):
    def test_list_and_plan(self):
        tl = mcp_server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        names = {t["name"] for t in tl["result"]["tools"]}
        self.assertEqual(names, {"list", "plan", "run"})
        r = mcp_server.handle_request({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "plan", "arguments": {"file": DEMO, "task": "build"}}})
        payload = json.loads(r["result"]["content"][0]["text"])
        self.assertEqual([s["task"] for s in payload["steps"]], ["clean", "build"])

    def test_run_via_mcp(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(tmp, "t.yaml", "tasks:\n  hi:\n    cmds:\n      - echo ok\n")
            r = mcp_server.handle_request({
                "jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {"name": "run", "arguments": {"file": p, "task": "hi"}}})
            self.assertFalse(r["result"]["isError"])


class TestAiHook(unittest.TestCase):
    def test_off_by_default(self):
        for v in ("COGNIS_AI_BACKEND", "COGNIS_AI_ENDPOINT"):
            os.environ.pop(v, None)
        out = draft_taskfile("build test and deploy a python app")
        self.assertTrue(out["_ai"].startswith("disabled"))
        self.assertIn("tasks", out)


if __name__ == "__main__":
    unittest.main()
