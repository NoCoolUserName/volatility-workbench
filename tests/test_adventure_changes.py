"""Real Git event comparisons plus fail-open and workflow regression checks."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/adventure_changes.py"
spec = importlib.util.spec_from_file_location("adventure_changes", SCRIPT)
assert spec and spec.loader
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class AdventureChangesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.write("README.md", "base\n")
        self.write("scripts/build_adventure.py", "base\n")
        self.write("scripts/build_bsd_adventure.py", "base\n")
        self.base = self.save()

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.repo,
                                       stderr=subprocess.PIPE).decode().strip()

    def write(self, path, content="changed\n"):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def save(self):
        self.git("add", "-A")
        self.git("commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    def event(self, head):
        return {"before": self.base, "after": head, "created": False, "deleted": False}

    def run_cli(self, event_name="push", event=None, sha=None, raw=None):
        head = self.git("rev-parse", "HEAD")
        payload = self.repo / "event.json"
        payload.write_text(raw if raw is not None else json.dumps(
            event if event is not None else self.event(head)))
        output = self.repo / "output.txt"
        output.unlink(missing_ok=True)
        env = {**os.environ, "GITHUB_EVENT_NAME": event_name,
               "GITHUB_EVENT_PATH": str(payload), "GITHUB_SHA": sha or head,
               "GITHUB_OUTPUT": str(output)}
        result = subprocess.run([os.sys.executable, str(SCRIPT)], cwd=self.repo,
                                env=env, capture_output=True, text=True, check=True)
        return output.read_text(), result.stdout

    def test_push_relevant_inputs(self):
        for path in gate.INPUTS:
            with self.subTest(path=path):
                self.write(path)
                head = self.save()
                self.assertTrue(gate.decide(self.repo, "push", self.event(head), head)[0])

    def test_push_unrelated_and_unusual_names(self):
        for path in ("README.md", "docs/release.md", "src/volatility_workbench/ui.py",
                     "notes with spaces\nand newline.txt", "notes-α.txt"):
            self.write(path)
        head = self.save()
        self.assertFalse(gate.decide(self.repo, "push", self.event(head), head)[0])
        self.assertEqual(self.run_cli()[0], "run_native=false\n")

    def test_push_compares_all_commits(self):
        self.write("scripts/build_adventure.py")
        self.save()
        self.write("README.md")
        head = self.save()
        self.assertTrue(gate.decide(self.repo, "push", self.event(head), head)[0])

    def test_unrelated_workflow_does_not_rebuild_game(self):
        self.write(".github/workflows/security.yml")
        head = self.save()
        self.assertFalse(gate.decide(self.repo, "push", self.event(head), head)[0])
        self.assertEqual(self.run_cli()[0], "run_native=false\n")

    def test_large_diff_is_not_api_truncated(self):
        for index in range(350):
            self.write(f"docs/{index:04}.md")
        self.write("scripts/build_adventure.py")
        head = self.save()
        self.assertTrue(gate.decide(self.repo, "push", self.event(head), head)[0])

    def test_pr_rename_away_from_input(self):
        self.git("checkout", "-qb", "topic")
        self.git("mv", "scripts/build_adventure.py", "archived.txt")
        head = self.save()
        self.git("checkout", "-q", "main")
        self.git("merge", "--no-ff", "-qm", "test merge", "topic")
        checkout = self.git("rev-parse", "HEAD")
        event = {"pull_request": {"base": {"sha": self.base}, "head": {"sha": head}}}
        self.assertTrue(gate.decide(self.repo, "pull_request", event, checkout)[0])

    def test_deletion(self):
        (self.repo / "scripts/build_adventure.py").unlink()
        head = self.save()
        self.assertTrue(gate.decide(self.repo, "push", self.event(head), head)[0])

    def test_rename_away_from_input(self):
        self.git("mv", "scripts/build_adventure.py", "archived.txt")
        head = self.save()
        self.assertTrue(gate.decide(self.repo, "push", self.event(head), head)[0])

    def test_rename_into_input(self):
        self.git("mv", "README.md", "scripts/adventure_changes.py")
        head = self.save()
        self.assertTrue(gate.decide(self.repo, "push", self.event(head), head)[0])

    def test_unrelated_rename_and_deletion(self):
        self.git("mv", "README.md", "guide.md")
        head = self.save()
        self.assertFalse(gate.decide(self.repo, "push", self.event(head), head)[0])
        (self.repo / "guide.md").unlink()
        head = self.save()
        self.assertFalse(gate.decide(self.repo, "push", self.event(head), head)[0])

    def pull_request(self, relevant):
        self.git("checkout", "-qb", "topic")
        self.write("scripts/build_adventure.py" if relevant else "docs/guide.md")
        head = self.save()
        self.git("checkout", "-q", "main")
        # An input changed only on main must NOT be mistaken for a PR change.
        self.write("scripts/build_bsd_adventure.py", "base branch update\n")
        base = self.save()
        self.git("merge", "--no-ff", "-qm", "test merge", "topic")
        checkout = self.git("rev-parse", "HEAD")
        event = {"pull_request": {"base": {"sha": base}, "head": {"sha": head}}}
        return event, checkout

    def test_pr_unrelated_uses_merge_base(self):
        event, checkout = self.pull_request(False)
        self.assertFalse(gate.decide(self.repo, "pull_request", event, checkout)[0])
        self.assertEqual(self.run_cli("pull_request", event)[0], "run_native=false\n")

    def test_pr_relevant_uses_head_not_merge_commit(self):
        event, checkout = self.pull_request(True)
        self.assertTrue(gate.decide(self.repo, "pull_request", event, checkout)[0])

    def test_pr_missing_endpoint(self):
        event, checkout = self.pull_request(False)
        event["pull_request"]["head"]["sha"] = "1" * 40
        self.assertEqual(self.run_cli("pull_request", event)[0], "run_native=true\n")

    def test_force_push_compares_trees(self):
        self.write("scripts/build_adventure.py")
        before = self.save()
        self.git("checkout", "--detach", "-q", self.base)
        self.write("docs/guide.md")
        head = self.save()
        self.assertTrue(gate.decide(self.repo, "push", {"before": before, "after": head}, head)[0])

    def test_manual_always_runs_without_payload(self):
        self.assertTrue(gate.decide(self.repo, "workflow_dispatch", {}, "")[0])
        self.assertEqual(self.run_cli("workflow_dispatch", raw="invalid")[0], "run_native=true\n")

    def test_unknown_event_runs(self):
        self.assertEqual(self.run_cli("merge_group", {})[0], "run_native=true\n")

    def test_invalid_payloads_run(self):
        for raw in ("invalid", "{}", "null", "[]", '{"before": "--bad"}'):
            with self.subTest(raw=raw):
                self.assertEqual(self.run_cli(raw=raw)[0], "run_native=true\n")

    def test_invalid_or_missing_push_commits_run(self):
        for value in ("0" * 40, "1" * 40, "--option", "", None):
            with self.subTest(value=value):
                self.assertEqual(self.run_cli(event={"before": value, "after": self.base})[0],
                                 "run_native=true\n")

    def test_created_or_deleted_branch_runs(self):
        for flag in ("created", "deleted"):
            event = self.event(self.base)
            event[flag] = True
            self.assertEqual(self.run_cli(event=event)[0], "run_native=true\n")

    def test_mismatched_checkout_runs(self):
        self.assertEqual(self.run_cli(sha="1" * 40)[0], "run_native=true\n")
        event = self.event("1" * 40)
        self.assertEqual(self.run_cli(event=event)[0], "run_native=true\n")

    def test_shallow_history_runs(self):
        (self.repo / ".git/shallow").write_text(self.base + "\n")
        self.assertEqual(self.run_cli()[0], "run_native=true\n")

    def test_subprocess_failures_run(self):
        for failure in (subprocess.CalledProcessError(1, "git"),
                        subprocess.TimeoutExpired("git", 30), FileNotFoundError("git")):
            with self.subTest(failure=type(failure).__name__):
                with patch.dict(os.environ, {"GITHUB_EVENT_NAME": "push",
                                             "GITHUB_EVENT_PATH": str(self.repo / "event"),
                                             "GITHUB_SHA": self.base,
                                             "GITHUB_OUTPUT": str(self.repo / "out")}):
                    (self.repo / "event").write_text(json.dumps(self.event(self.base)))
                    with patch.object(gate, "git", side_effect=failure):
                        gate.main()
                self.assertTrue((self.repo / "out").read_text().endswith("run_native=true\n"))

    def test_ambiguous_pr_merge_base_runs(self):
        event, checkout = self.pull_request(False)
        original = gate.git

        def ambiguous(repo, *args):
            if args[:2] == ("merge-base", "--all"):
                return (self.base + "\n" + checkout + "\n").encode()
            return original(repo, *args)

        with patch.object(gate, "git", side_effect=ambiguous):
            with self.assertRaisesRegex(ValueError, "unique merge base"):
                gate.decide(self.repo, "pull_request", event, checkout)

    def test_incomplete_diff_rejected(self):
        original = gate.git

        def truncated(repo, *args):
            return b"README.md" if args[0] == "diff" else original(repo, *args)

        with patch.object(gate, "git", side_effect=truncated):
            with self.assertRaisesRegex(ValueError, "truncated"):
                gate.decide(self.repo, "push", self.event(self.base), self.base)


class WorkflowTests(unittest.TestCase):
    def test_native_condition_fails_open(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        self.assertIn("fetch-depth: 0", workflow)
        self.assertIn("needs: adventure-changes", workflow)
        self.assertIn("always() && !cancelled()", workflow)
        self.assertIn("needs.adventure-changes.result != 'success'", workflow)
        self.assertIn("needs.adventure-changes.outputs.run_native != 'false'", workflow)
        self.assertNotIn("    paths:", workflow)
        self.assertNotIn("    paths-ignore:", workflow)
        # The condition runs for failed/skipped detection and missing outputs.
        for result in ("success", "failure", "skipped", "cancelled"):
            for output in ("true", "false", "", None):
                should_run = result != "success" or output != "false"
                self.assertEqual(should_run, (result, output) != ("success", "false"))


if __name__ == "__main__":
    unittest.main()
