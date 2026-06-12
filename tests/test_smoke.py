"""Smoke tests for taskforge. Standard library only."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from taskforge import TOOL_NAME, TOOL_VERSION, load_taskfile, plan_commands
from taskforge.cli import main

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(REPO_ROOT, "demos", "01-basic", "taskforge.yaml")


class TestMetadata(unittest.TestCase):
    def test_metadata(self):
        self.assertEqual(TOOL_NAME, "taskforge")
        self.assertTrue(TOOL_VERSION)


class TestPlan(unittest.TestCase):
    def test_release_plan_order_and_matrix(self):
        tf = load_taskfile(DEMO)
        steps = plan_commands(tf, "release")
        tasks_in_order = [s["task"] for s in steps]
        # clean -> build -> test(x2 matrix) -> release
        self.assertEqual(tasks_in_order[0], "clean")
        self.assertEqual(tasks_in_order[1], "build")
        self.assertEqual(tasks_in_order.count("test"), 2)
        self.assertEqual(tasks_in_order[-1], "release")
        # interpolation worked
        self.assertIn("hello-edge", steps[0]["command"])
        self.assertIn("localhost:5000", steps[-1]["command"])


class TestCli(unittest.TestCase):
    def test_dry_run(self):
        self.assertEqual(main(["-f", DEMO, "run", "release", "--dry-run"]), 0)

    def test_list(self):
        self.assertEqual(main(["-f", DEMO, "list"]), 0)

    def test_graph(self):
        self.assertEqual(main(["-f", DEMO, "graph", "release"]), 0)

    def test_unknown_task_exits_2(self):
        self.assertEqual(main(["-f", DEMO, "run", "nope", "--dry-run"]), 2)

    def test_no_command_exits_2(self):
        self.assertEqual(main([]), 2)


if __name__ == "__main__":
    unittest.main()
