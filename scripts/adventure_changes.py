"""Decide whether native Adventure CI is needed; uncertainty always runs it."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess

# Both builders embed all upstream source/data/dependency pins and build logic.
# They read no other repository files. Include CI and gate tests so changes to
# validation itself exercise the native job too. Keep this list in sync if a
# builder starts reading local inputs or imports another project module.
INPUTS = frozenset({
    "scripts/build_adventure.py",
    "scripts/build_bsd_adventure.py",
    "scripts/adventure_changes.py",
    "tests/test_adventure.py",
    "tests/test_adventure_changes.py",
    "scripts/check_adventure_browser.cjs",
    "src/volatility_workbench/adventure.py",
    "src/volatility_workbench/static/adventure.js",
    "src/volatility_workbench/static/theme-adventure.svg",
})
SHA = re.compile(r"[0-9a-f]{40}")


def git(repo: Path, *arguments: str) -> bytes:
    return subprocess.check_output(
        ["git", *arguments], cwd=repo, stderr=subprocess.PIPE, timeout=30)


def commit(value: object) -> str:
    if not isinstance(value, str) or not SHA.fullmatch(value) or set(value) == {"0"}:
        raise ValueError("missing or invalid comparison commit")
    return value


def relevant(path: str) -> bool:
    return path in INPUTS or path.startswith(".github/workflows/")


def decide(repo: Path, event_name: str, event: dict, checkout_sha: str) -> tuple[bool, str]:
    if event_name == "workflow_dispatch":
        return True, "manual full validation"
    if event_name not in {"pull_request", "push"}:
        return True, "event has no supported comparison"
    checkout = commit(checkout_sha)
    if git(repo, "rev-parse", "HEAD").decode().strip() != checkout:
        raise ValueError("checkout does not match the event revision")
    if git(repo, "rev-parse", "--is-shallow-repository").strip() != b"false":
        raise ValueError("history is incomplete")
    if event_name == "pull_request":
        pull = event["pull_request"]
        base = commit(pull["base"]["sha"])
        head = commit(pull["head"]["sha"])
        # Checkout is normally GitHub's test merge commit. Both endpoints must
        # belong to it; do not trust a stale/inconsistent event/checkout pair.
        for endpoint in (base, head):
            git(repo, "merge-base", "--is-ancestor", endpoint, checkout)
        bases = git(repo, "merge-base", "--all", base, head).decode().splitlines()
        if len(bases) != 1:
            raise ValueError("comparison has no unique merge base")
        base = commit(bases[0])
    else:
        if event.get("created") or event.get("deleted"):
            raise ValueError("branch creation/deletion has no complete comparison")
        base, head = commit(event["before"]), commit(event["after"])
        if head != checkout:
            raise ValueError("push after revision does not match checkout")
    # No rename detection: renames become deletion + addition, checking BOTH
    # old and new names. NUL records also preserve spaces/newlines in filenames.
    changed = git(repo, "diff", "--no-ext-diff", "--no-textconv", "--no-renames",
                  "--name-only", "-z", base, head, "--")
    if changed and not changed.endswith(b"\0"):
        raise ValueError("truncated changed-file output")
    paths = [part.decode("utf-8") for part in changed.split(b"\0") if part]
    if any(relevant(path) for path in paths):
        return True, "native build or validation inputs changed"
    return False, "complete comparison contains no native Adventure inputs"


def main() -> None:
    run_native, reason = True, "comparison unavailable"
    try:
        event_name = os.environ["GITHUB_EVENT_NAME"]
        if event_name == "workflow_dispatch":
            run_native, reason = True, "manual full validation"
        else:
            event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
            run_native, reason = decide(Path.cwd(), event_name, event, os.environ["GITHUB_SHA"])
    except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError):
        # Avoid logging payloads, paths or subprocess stderr. Failed comparisons
        # are observable while still scheduling native validation.
        reason = "comparison unavailable or incomplete; running native validation"
    print(f"Adventure: {reason}")
    with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
        output.write(f"run_native={str(run_native).lower()}\n")


if __name__ == "__main__":
    main()
