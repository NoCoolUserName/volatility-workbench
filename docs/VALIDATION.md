# Validation ownership

Application and separation checks are recorded in [UI_VALIDATION.md](UI_VALIDATION.md).
Core execution/reuse, artifact inspection, saved-evidence/citation, coverage, and
protocol checks are maintained in the
[core validation record](https://github.com/NoCoolUserName/volatility-mcp/blob/main/docs/VALIDATION.md).

## Native Adventure CI scope

The compatibility workflow always starts for pull requests and main pushes. Its
Ubuntu `adventure-changes` job uses full Git history, not a capped changed-files
API. Pull requests compare their unique merge base to the PR head; pushes compare
the event's before/after trees across the complete push, including force pushes.
Renames are treated as deletion plus addition so both paths are checked.

Only `ARM64 Adventure build and gameplay` is conditional. Its repository inputs
are `scripts/build_adventure.py` and `scripts/build_bsd_adventure.py`: these embed
the pinned upstream source/data/PyYAML downloads, hashes, portability patches and
build commands. They import no other project modules or local build data. Changes
to any `.github/workflows/` file, `scripts/adventure_changes.py`,
`tests/test_adventure_changes.py`, `tests/test_adventure.py`, the Adventure browser
regression, application adapter, JavaScript, or theme SVG also run the native
job. Extend the detector's input set if either builder gains a local dependency.
README/release prose and ordinary application changes do not allocate that game
runner when the complete comparison establishes that these inputs are unchanged.

Use **Actions → Workbench compatibility → Run workflow** on the intended ref for
explicit full CI validation, including both native games. Manual dispatch always
runs the native job; it does not replace the PR-triggered checks required for merge.
Missing/invalid event data or commits, shallow history, inconsistent checkout,
ambiguous merge bases, Git failures/timeouts and malformed diff output run native
validation. Detection job failure or missing output also schedules the native job;
only successful detection with the exact output `false` skips it. Cancellation
still cancels work. The existing job name and workflow triggers remain unchanged;
there is no whole-workflow path filter or merge-safeguard configuration change.
GitHub documents [conditional job skips versus missing workflow checks](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks).

Python 3.12/3.13 compatibility, installed-package tests, synthetic browser checks,
lint, secret scanning and security workflows remain unconditional as before.
The native job checks only the two games, not the desktop application. Its skip
does not satisfy or replace the native application build, signing, downloaded-app
and release acceptance requirements in [MACOS_RELEASE.md](MACOS_RELEASE.md) and
[packaging validation](../packaging/VALIDATION.md).

Focused local regression command:

```sh
python3 -m unittest discover -s tests -p test_adventure_changes.py -v
```

The suite uses disposable real Git repositories and synthetic event payloads.
It covers relevant/unrelated inputs, large diffs, renames/deletions, multi-commit
and force pushes, divergent PR history, manual validation and fail-open cases.
These checks do not establish hosted scheduling or ARM64 build/signature success.

## Native application and optional providers (2026-10-18)

The complete Workbench suite passed 73 tests at the initial desktop integration
checkpoint, including authenticated loopback host startup/reuse/cleanup, geometry
and navigation boundaries, configuration import without changing original state,
runtime rebase/rollback, exclusive settings operations, symbols, endpoint-bound
credentials, compatible tool rounds and cancellation. The existing core suite
passed 101 tests with one expected optional XP fixture skip. The installed-wheel
package smoke check passed from outside the checkout without desktop dependencies.
These are synthetic contract/regression checks, not new malware investigations.

The actual native candidate opened from a path containing spaces using Finder's
minimal environment. Native window chrome and rounded corners were visually
inspected. Its catalog displayed 200 plugins and correct Native/local/community
sources; the All checkbox cleared and restored the catalog. Authenticated Settings
and the real macOS folder picker worked. Idle menu Quit removed the backend
listener. A locale failure observed under Finder was fixed by initializing UTF-8
in the native executable, then verified by a real embedded-runtime subprocess
round trip. Further final-installation checks are recorded below when performed.

Real bundled MCP initialization/catalog and native dependency imports are detailed
in packaging/VALIDATION.md. The packaging validator performs one harmless
synthetic banner scan per invocation; no private image or existing report is
analyzed or regenerated. An actual native Codex initialize/account-read reused
the existing sign-in without a model turn. Synthetic Keychain create/read/update/
delete passed; no real provider key was copied. Compatible API behavior is tested
with mocked services and case-scoped MCP, not claimed as a live hosted-model test.

Five pinned official symbol files passed Volatility's ISF validation. A real HTTPS
pack download resumed from a saved partial download and matched its pinned size
and SHA-256. These exact legacy kernels/PDBs do not establish general OS coverage.
No macOS symbol pack is advertised as complete.

Native follow-up verification used one hand-authored saved report/citation and a
loopback synthetic model service. The report, nested evidence and decorative coin
opened in the actual app; untrusted script text stayed text. Native full-screen
and return to decorated mode worked. Closing/reopening retained the backend.
Cmd-Q during a simulated question displayed both choices: Keep working retained
the running job; Cancel work and quit closed the listener and recorded the job
as incomplete while preserving its report. No real model or analyzer ran for
this exercise. The packaged optional community overlay was also actually installed
in temporary storage: 200 to 208 plugins, no import failures, clean pip check,
unchanged bundled source hashes and valid signature afterward.

Final candidate checks: 76 Workbench tests passed. A genuinely empty temporary
home launched directly into authenticated Settings without credentials, downloads
or analysis. Native Cut/Paste worked. The saved fixture reopened after rebasing
its recognized bundled analyzer; global and case-scoped MCP configs agreed. The
coin Save image action opened NSSavePanel and wrote byte-identical SVG output.
This is an explicit fallback alongside WebKit context menus; automated right-click
menu selection itself was not established by the native control harness.

The native build-information dialog was observed to show application/core/Python/
WebView versions and exact source/core revisions. The standard About menu routes
to this information in the final application. The installed-wheel check was
repeated after the final settings and save-link asset changes: all 76 tests passed.
