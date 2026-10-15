# Volatility Workbench

A local browser application for existing memory acquisitions: case navigation,
sequential jobs, a case conversation, report exploration, saved evidence, coverage,
and decorative image coins. It uses the separately maintained
[volatility-mcp](https://github.com/NoCoolUserName/volatility-mcp) core; there is one
implementation of execution, integrity, result reuse, artifact inspection, queries,
references, citation validation and forensic coverage.

Experimental. macOS ARM64 is the tested local host. POSIX/Linux uses path entry
and folder browsing; Finder is macOS-only. Windows hosts are unsupported. Codex
app-server 0.160.0 is the existing model adapter; this separation does not change
provider/account selection. The UI adds no runtime dependency beyond core.

## Install and launch

Use Python 3.12+ and Git. Install official Volatility separately as described in
[core setup](https://github.com/NoCoolUserName/volatility-mcp#quick-start-1-use-the-mcp-server).
Keep an existing configured Volatility environment intact. Clone only Workbench:

```sh
git clone https://github.com/NoCoolUserName/volatility-workbench.git
cd volatility-workbench
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m pip install .
.venv/bin/python -m volatility_mcp setup --help
.venv/bin/volatility-workbench --config /absolute/path/to/config.json --state-dir /absolute/path/to/private/workbench
```

`pip install .` automatically installs its full-commit core dependency. The lock
file also pins all runtime dependencies for the tested release. No PyPI publication
of either project is required. The console command or `python -m volatility_workbench`
works from any directory; no source checkout is needed after installation. Assets,
the presentation template, and the core report contract ship in the wheels.

Use an existing private config/state directory to reopen existing cases. Without
`--state-dir`, the default is `<configured output_root>/workbench`. No source images
are copied. For an existing administrative relocation, export the same
`VOLATILITY_MCP_RELOCATION` file and retain its compatibility symlink. Never change
these roots merely because the source repositories were separated. `--project` is
accepted for old launchers but is no longer needed for packaged assets/contracts.

See [workflow and limits](docs/LOCAL_UI.md), [validation](docs/UI_VALIDATION.md),
[ownership and recovery](docs/SEPARATION.md), and [security](SECURITY.md).

On macOS, launch and reopen use the system's default browser through `/usr/bin/open`.
If opening fails, Workbench prints an explicit message and keeps the private launch
URL available in Terminal. `--no-open` skips browser opening.

The packaged icon also appears in the browser tab. To apply the same custom icon
to an existing macOS `.command` launcher (without changing its command):

```sh
swift scripts/macos-icon.swift /tmp/workbench-icon.png "/absolute/path/to/Launch Volatility Workbench.command"
```

The Swift source draws the icon using AppKit; it requires Apple's Swift tools.
To regenerate the packaged image, use `src/volatility_workbench/static/icon.png`
as the output path and omit the launcher argument. The launcher remains a Terminal
script, with no separate desktop application to install.

## Develop both repositories

Place the two checkouts alongside each other, then use Workbench's environment:

```sh
cd volatility-workbench
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m pip install --no-deps -e ../volatility-mcp -e .
.venv/bin/python -m unittest discover -s tests -q
```

Edit shared code once in `../volatility-mcp`. Python source changes are read from
that checkout after restarting idle Workbench and its relevant MCP process. Packaging,
entry-point or dependency changes require reinstalling. Never restart an active job.
No source copying, PYTHONPATH setting, or submodule is used. The independent core
checkout retains its own environment and existing standalone MCP registration.

## Core releases and rollback

`core-dependency.json`, `pyproject.toml`, and `requirements.lock.txt` record the tested
core version and immutable commit. Eligible updates are stable `v0.1.x` core releases
with API revision 1. The weekly/manual `Update core` workflow selects a new release,
updates the pin and core runtime lock, installs and tests the candidate (including
wheel/outside-checkout checks), then proposes one PR per commit. No automatic merge
or startup update occurs. Incompatible versions fail before publication of a PR.

The updater validates directly in its own run because token-created PR workflows
may require approval. The PR links that successful run; maintainers can also run
CI manually on its branch. It uses the repository GITHUB_TOKEN with only contents
and pull-request write permissions, no PAT. See
[GitHub's token event rules](https://docs.github.com/en/actions/concepts/security/github_token).

Manual equivalent:

```sh
.venv/bin/python scripts/update_core.py --dry-run
.venv/bin/python scripts/update_core.py
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m pip install .
.venv/bin/python -m unittest discover -s tests -q
.venv/bin/python scripts/package_smoke.py
```

Review and commit the generated files only after validation. A core minor/API change
requires explicit maintainer review of compatibility policy. To roll back, install a
previous tested Workbench commit and its lock file in a separate environment, switch
the launcher while idle, and retain the same private data roots. Existing bundles
are never regenerated or rewritten by an upgrade/rollback.
