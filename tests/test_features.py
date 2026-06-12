"""Feature tests for taskforge — var overrides, validate, CLI."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from taskforge import load_taskfile, plan_commands, run, validate_taskfile
from taskforge.cli import main

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(REPO_ROOT, "demos", "01-basic", "taskforge.yaml")


def _write(tmp, text):
    p = os.path.join(tmp, "t.yaml")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text)
    return p


class TestOverrides(unittest.TestCase):
    def test_override_wins(self):
        tf = load_taskfile(DEMO)
        steps = plan_commands(tf, "build", overrides={"app": "OVERRIDDEN"})
        self.assertTrue(any("OVERRIDDEN" in s["command"] for s in steps))

    def test_run_with_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(tmp, "vars:\n  who: world\n"
                            "tasks:\n  hi:\n    cmds:\n      - echo hello ${who}\n")
            res = run(load_taskfile(p), "hi", overrides={"who": "cognis"})
            self.assertTrue(res["ok"])
            self.assertIn("cognis", res["executed"][0]["command"])


class TestValidate(unittest.TestCase):
    def test_demo_valid(self):
        self.assertTrue(validate_taskfile(load_taskfile(DEMO))["ok"])

    def test_unknown_dep(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(tmp, "tasks:\n  a:\n    deps: [ghost]\n    cmds:\n      - echo x\n")
            res = validate_taskfile(load_taskfile(p))
            self.assertFalse(res["ok"])
            self.assertTrue(any("ghost" in pr for pr in res["problems"]))

    def test_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(tmp, "tasks:\n  a:\n    deps: [b]\n    cmds:\n      - echo a\n"
                            "  b:\n    deps: [a]\n    cmds:\n      - echo b\n")
            res = validate_taskfile(load_taskfile(p))
            self.assertFalse(res["ok"])
            self.assertTrue(any("cycle" in pr for pr in res["problems"]))

    def test_no_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(tmp, "tasks:\n  a:\n    desc: nothing\n")
            res = validate_taskfile(load_taskfile(p))
            self.assertFalse(res["ok"])


class TestCliFeatures(unittest.TestCase):
    def test_run_with_var_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(tmp, "tasks:\n  hi:\n    cmds:\n      - echo ${x}\n")
            self.assertEqual(main(["-f", p, "run", "hi", "--var", "x=1",
                                   "--dry-run"]), 0)

    def test_validate_cli_pass(self):
        self.assertEqual(main(["-f", DEMO, "validate"]), 0)

    def test_validate_cli_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(tmp, "tasks:\n  a:\n    deps: [ghost]\n    cmds:\n      - echo x\n")
            self.assertEqual(main(["-f", p, "validate"]), 1)

    def test_bad_var_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(tmp, "tasks:\n  hi:\n    cmds:\n      - echo x\n")
            self.assertEqual(main(["-f", p, "run", "hi", "--var", "noequals",
                                   "--dry-run"]), 2)


if __name__ == "__main__":
    unittest.main()
