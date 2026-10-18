# Volatility Workbench

A local application for existing memory acquisitions, with an optional native macOS window and browser/CLI modes: case navigation,
sequential jobs, a case conversation, report exploration, saved evidence, coverage,
a searchable installed-plugin catalog, and decorative image coins. It uses the separately maintained
[volatility-mcp](https://github.com/NoCoolUserName/volatility-mcp) core; there is one
implementation of execution, integrity, result reuse, artifact inspection, queries,
references, citation validation and forensic coverage.

Experimental. macOS ARM64 is the tested local host. POSIX/Linux uses path entry
and folder browsing; Finder is macOS-only. Windows hosts are unsupported. The Codex adapter reuses existing sign-in. An optional compatible chat/tool API adapter supports explicitly configured endpoints after a synthetic capability check. Desktop dependencies are optional; browser mode retains the core-only dependency set. See [AI providers](docs/AI_PROVIDERS.md).

## Native macOS application

The macOS ARM64 distribution opens the same UI/backend in a decorated system
WebView with a Dock icon, native menus and Settings. It includes separate,
relocatable Python application/analyzer runtimes; no checkout, Homebrew, shell
startup file or development venv is needed. Closing the window hides it; Dock
reopen restores it. Quit asks before cancelling active work. Existing configuration
and case roots can be reused without moving evidence. Images explicitly added
from different physical folders stay in place; Settings lists their registered
locations and counts while MCP access remains limited to each case’s selected files.

See [build, install and rollback](packaging/README.md), [native application](docs/MACOS_APP.md),
and [Settings, symbols and optional plugins](docs/SETTINGS_AND_SYMBOLS.md).
The distribution manifest selects pinned core, Volatility and optional addon
profiles. Public bundles contain redistributable additions; optional community
sources are downloaded explicitly into a separate managed environment. Catalog
counts come from the configured runtime. Local builds are ad-hoc signed unless
an explicit release identity is supplied. The optional [release machinery](docs/MACOS_RELEASE.md)
provides package auditing, a read-only plan, and staged notarization/stapling with
operator-supplied Apple credentials. No credentialed release has been validated yet.

## Browser / CLI install and launch

Use Python 3.12+ and Git. Install official Volatility separately as described in
[core setup](https://github.com/NoCoolUserName/volatility-mcp#quick-start-1-use-the-mcp-server).
Keep an existing configured Volatility environment intact. Clone only Workbench:

```sh
git clone https://github.com/NoCoolUserName/volatility-workbench.git
cd volatility-workbench
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python scripts/install_core_pin.py
.venv/bin/python -m pip install .
.venv/bin/python -m volatility_mcp setup --help
.venv/bin/volatility-workbench --config /absolute/path/to/config.json --state-dir /absolute/path/to/private/workbench
```

`pip install .` automatically installs its full-commit core dependency. The lock
file also pins all runtime dependencies for the tested release. The core-pin
helper checks installed Git provenance and replaces a stale wheel even when two
core commits share the same package version. No PyPI publication
of either project is required. The console command or `python -m volatility_workbench`
works from any directory; no source checkout is needed after installation. Assets,
the presentation template, and the core report contract ship in the wheels.

Use an existing private config/state directory to reopen existing cases. Without
`--state-dir`, the default is `<configured output_root>/workbench`. No source images
are copied. Point private configuration and launchers at the actual evidence and
output directories. If those directories were physically moved, back up and
rebase mutable saved-case path metadata before relying on saved-result queries;
sealed report bundles and recorded command lines remain historical records. The
launcher does not create filesystem aliases. `--project` is
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
as the output path and omit the launcher argument. This optional browser-mode fallback opens Terminal. The native application uses
the same artwork as a packaged `.icns` and does not open Terminal or a browser tab.

## Optional analysis plugins

The core dependency provides a pinned, opt-in community profile for PteMalfind /
Ptenum, ImgMalfind, Prefetch, AnyDesk, EVTXLog, Browser History Extractor and
KeePass. Install only while analysis clients are idle:

```sh
.venv/bin/python -m volatility_mcp plugins-install --config /absolute/path/to/config.json
```

Then refresh **Plugins**; restart idle clients that retain an older catalog. The
profile installs into the configured analyzer, preserves official Volatility, and
adds source labels/compatibility notes to the existing UI. It includes the callable
SimplePteEnumerator and the supporting ApiSearch command. The app does not install
plugins silently. See the [pinned profile, licenses and validation limits](https://github.com/NoCoolUserName/volatility-mcp/blob/main/docs/COMMUNITY_PLUGINS.md).

## Develop both repositories

Place the two checkouts alongside each other, then use Workbench's environment:

```sh
cd volatility-workbench
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python scripts/install_core_pin.py
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
.venv/bin/python scripts/install_core_pin.py
.venv/bin/python -m pip install .
.venv/bin/python -m unittest discover -s tests -q
.venv/bin/python scripts/package_smoke.py
```

Review and commit the generated files only after validation. A core minor/API change
requires explicit maintainer review of compatibility policy. To roll back, install a
previous tested Workbench commit and its lock file in a separate environment, switch
the launcher while idle, and retain the same private data roots. Existing bundles
are never regenerated or rewritten by an upgrade/rollback.
