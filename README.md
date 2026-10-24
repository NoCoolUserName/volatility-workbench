# Volatility Workbench

*22,572 lines of code*

*Latest measured macOS ARM64 build: `Volatility Workbench.app` 403.46 MiB (423,060,401 regular-file bytes, excluding symlink aliases); `Volatility-Workbench-macos-arm64.zip` 187.77 MiB (196,885,947 bytes). Built from 26abdaf23e3d4e1a000e65320fec9ad6c9479751, measured 2026-10-23.*

Original project code is available under MIT and the Volatility Software License 1.0. Integrated Volatility distributions follow VSL's source and notice requirements; see [LICENSING.md](LICENSING.md) for the component map and release steps.

An experimental local application for exploring existing memory acquisitions with
[volatility-mcp](https://github.com/NoCoolUserName/volatility-mcp). It provides saved
cases, sequential analysis jobs, resumable case conversations, versioned reports,
saved evidence and citations, coverage views, and a searchable plugin catalog.
Use the native macOS application or the same interface in a browser. The optional
[Adventure Easter egg](docs/ADVENTURE.md) has a separate license and game-data
provenance review for both the 1977 and 1995 editions.

Workbench owns the application and presentation. The separately maintained core
owns forensic execution, integrity checks, saved-result reuse, artifact inspection,
queries, citations and coverage. Shared forensic code is not duplicated here.

## Implemented workflow

- Register existing images by physical path, folder browser or macOS file picker.
  Images stay in place. Unrelated images get separate cases; explicitly related
  captures can share a case even when they live in different folders. Each case's
  MCP server can access only its selected files.
- Check readiness, generate a report, ask follow-up questions, and create a new
  report revision. Jobs run sequentially with progress, Stop, cancellation and
  interrupted-work recovery. Readiness is permission to attempt analysis, not a
  clean verdict or a guarantee of matching symbols.
- Reopen saved cases and conversations. Explore report sections, source artifacts,
  checked citations, coverage, and activity/failures. The displayed report revision
  stays visibly selected. Refreshing saved views does not start new analysis.
- Inspect **Plugins used in this report** for the selected revision's saved
  execution inventory: exact plugin names, arguments, outcomes and run/call IDs.
  Reused outputs and requests without a recorded execution are distinguished.
  New portable reports include the same mechanical inventory; historical bundles
  are read without rewriting them. Missing legacy metadata stays explicit.
- Keep sealed report versions immutable. New revisions record available model,
  reasoning-effort and generation-turn token provenance; historical unknowns stay
  explicit. Optional decorative coins are stable per image. Hide retains files;
  explicit Delete removes only the selected eligible report bundle, preserving
  source evidence, shared results and history.
- Inspect the configured analyzer's plugin names, descriptions, versions, source
  attribution, compatibility notes and import failures. Search and filter by OS
  and source without starting an investigation.
- Use Settings for explicit AI connections, registered evidence locations, idle-only
  community-plugin maintenance, bounded symbol downloads and exact-identity local
  symbol imports. Existing case roots cannot be moved through a settings save.

See [the local workflow](docs/LOCAL_UI.md), [Settings and symbols](docs/SETTINGS_AND_SYMBOLS.md),
and [ownership and recovery](docs/SEPARATION.md).

## Themes

The header and Settings share 33 locally bundled appearance choices. A new browser
without a saved preference starts with the original Matrix green appearance.
Existing Soft black and white and Light blue preferences remain supported.
Theme changes affect presentation; case contents and saved reports are unchanged.

| Collection | Choices |
| --- | --- |
| Fallout — one skin per released game/table experience | Fallout; Fallout 2; Fallout Tactics: Brotherhood of Steel; Fallout: Brotherhood of Steel; Fallout 3; Fallout: New Vegas; Fallout Shelter; Fallout 4; Fallout Pinball; Fallout 4 VR; Fallout 76; Fallout Shelter Online |
| Seasonal | Friendly Halloween; adult, non-cartoon Halloween; The Nightmare Before Christmas |
| Arcade and adventure | 8-bit; Colossal Cave Adventure; Metroid; Silpheed (Sega CD); Elevator Action (NES) |
| Neon and terminals | Vaporwave; retrowave; hacker |
| Cinema and anime | Top Gun; Cyber City Oedo 808; Cyberpunk 2077; Golgo 13; The Punisher — War Journal #53 |
| Classic choices | Matrix green; Soft black and white; Light blue |

Original SVG scenes and the original generated adult-Halloween raster ship inside
the package. Themes make no external asset requests. Opaque work surfaces, semantic
warning colors, visible keyboard focus and selection indicators keep the forensic
UI readable. The saved preference is local to the browser/native WebView profile.

[Theme references and artwork provenance](docs/THEMES.md) document the official
Fallout release audit, version-specific references and the comic correction:
War Journal #53's signed cover is credited to Gary Kwapisz, rather than Jim Lee.
The skin follows the verified issue's visual cues.

## Native macOS application

The tested distribution targets Apple silicon and macOS 13 or later. It opens a
decorated system WebKit window with native menus, Settings, saved geometry and a
Dock icon. Closing hides the window while work continues; reopening restores it.
Quit asks before cancelling active work. Separate relocatable Python application
and analyzer runtimes mean the installed app needs no source checkout, Homebrew,
development environment or shell startup file.

Build from a clean, configured checkout with Python 3.12+ and Apple's command-line
tools:

```sh
python3 scripts/build_macos.py --cache /tmp/workbench-build-cache --output dist/macos
python3 scripts/validate_macos.py 'dist/macos/Volatility Workbench.app'
python3 scripts/install_macos.py 'dist/macos/Volatility Workbench.app' --desktop-launcher
open "$HOME/Applications/Volatility Workbench.app"
```

Quit only while idle before replacement. The installer refuses a running target
and retains the old app and Desktop launcher in timestamped rollback storage.
Configuration, evidence and case state remain outside the replaced bundle. The
optional Desktop launcher is a real native `.app` and opens no Terminal window.
An established external analyzer and existing case roots can be reused intact.

See [build/install/rollback](packaging/README.md), [native behavior and limits](docs/MACOS_APP.md),
and [release auditing and signing](docs/MACOS_RELEASE.md). Local builds are ad-hoc
signed unless an explicit release identity is supplied. Credentialed Developer ID,
notarization and downloaded-app Gatekeeper acceptance remain unvalidated.

## Browser / CLI setup

Use Python 3.12+ and Git. Set up official Volatility separately following
[core setup](https://github.com/NoCoolUserName/volatility-mcp#quick-start-1-use-the-mcp-server),
or keep an existing configured analyzer. Clone only Workbench:

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

The console entry point and `python -m volatility_workbench` work outside the
checkout after installation. Assets and templates ship in the wheel. macOS browser
launch uses the system default browser; `--no-open` prints the private launch URL
without opening it. Desktop dependencies are optional for browser/CLI use.

Reuse the established private config and state directory to reopen existing cases.
Without `--state-dir`, state defaults to `<configured output_root>/workbench`.
Keep configuration, evidence, histories, outputs and environments out of Git.
Physically moving existing roots requires backed-up mutable metadata rebasing;
launching does not create aliases or rewrite sealed historical records.

## AI connections and data

Codex is the default and reuses its existing supported sign-in. A separate,
experimental compatible chat/tool API adapter accepts an explicitly configured
endpoint/model after a synthetic tool-capability check. Provider changes for an
idle case are explicit and preserve earlier sessions. New API secrets can use
macOS Keychain or session-only storage. Workbench does not mirror another chat's
model selection or provide a Codex model/effort picker.

Images remain local. Questions, image metadata and selected evidence excerpts may
reach the chosen AI service. This is a local, single-user application; same-user
plugin subprocesses are not a malware sandbox. Recovered content is untrusted and
must never be executed. Reports require human review. See [AI connections](docs/AI_PROVIDERS.md)
and [security](SECURITY.md).

## Pinned core and plugins

The tested core pin is `62855a071fe085112d690b207e595c664fe7b158`, API revision 1.
`core-dependency.json`, `pyproject.toml` and `requirements.lock.txt` agree on the
immutable commit. `pip install .` brings in that dependency; the pin helper checks
installed Git provenance even when successive core commits share a package version.

The public bundle includes CryptoMem alongside the native and previously bundled
plugins. The configured analyzer may include additional optional community
plugins. Exact counts are measured during validation; discovery does not
establish image compatibility.

Core's single opt-in community inventory includes PteMalfind/Ptenum, ImgMalfind,
Prefetch, AnyDesk, EVTXLog, Browser History Extractor and KeePass, plus CobaltStrike,
RichHeader, ZoneID3, PteResolve, PasswordManager and SSHKeys. The six recent additions
are forced offline. PasswordManager is eligible for automatic investigation when relevant to the authorized
case scope and needs an observed browser PID. SSHKeys remains manual-only, excluded
from automatic flows, and needs a Linux PID and one suspected `sshenc` address.
No installed command is silently removed.

The runtime batch adds a BitLocker AES-schedule candidate scanner, ten Go commands
and twelve Python commands through that same core inventory. All 23 require manual
selection and run offline. They have bounded process/address/layout requirements:
Python currently requires the explicitly verified pinned CPython 3.8 research
layout; Go version gates are not an accuracy matrix; AES candidates do not establish
BitLocker key roles or cipher modes. See the
[core runtime-addon checks and limitations](https://github.com/NoCoolUserName/volatility-mcp/blob/main/docs/RUNTIME_ADDONS.md).

The bundled [CryptoMem plugin](https://github.com/NoCoolUserName/volatility3-cryptomem)
scans one selected Windows process for Bitcoin, Ethereum-style and XRP classic
address candidates and bounded payment requests. Find `windows.cryptomem.CryptoMem`
in Plugins and supply a PID. It runs offline through the shared core, preserves
process/virtual-offset provenance, and remains manual-only. Address validation
does not establish wallet ownership; real-memory recovery is still unvalidated.
Existing external analyzers receive it through the same explicit plugin installer.
See [CryptoMem capabilities and limits](https://github.com/NoCoolUserName/volatility-mcp/blob/main/docs/CRYPTOMEM.md).

Redistribution restrictions keep selected upstream sources out of the public app;
install them explicitly through idle Settings maintenance or core's installer:

```sh
.venv/bin/python -m volatility_mcp plugins-install --config /absolute/path/to/config.json
```

Refresh Plugins afterwards; restart idle clients that retain an older catalog.
See [core's profile, source attribution, licenses and limitations](https://github.com/NoCoolUserName/volatility-mcp/blob/main/docs/COMMUNITY_PLUGINS.md).
UI metadata/help uses decimal KB/MB; a 4,096-byte page is 4.096 KB. This conversion
does not change binary page arithmetic, scan/read/output limits or upstream files.

## Development and validation

For shared-code development, keep the repositories alongside each other and install
both editable into Workbench's environment:

```sh
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python scripts/install_core_pin.py
.venv/bin/python -m pip install --no-deps -e ../volatility-mcp -e .
```

Run focused checks for changed behavior during development. Before release, run
`scripts/package_smoke.py` once on the final change: it builds and installs isolated
wheels, checks dependencies, assets, HTTP startup and both MCP protocol modes, then
runs the full Workbench suite against installed packages outside the checkout.
Browser scripts under `scripts/check_*_browser.cjs` use synthetic data and Playwright
as a validation-only dependency; `check_themes_browser.cjs` checks all 33 skins under
the production content-security policy. `check_theme_persistence_browser.cjs` checks
restart/port changes, shared preferences, migration and save races;
`check_volshell_browser.cjs` checks the VolShell connection toggle and confirmed-disconnect lifecycle.
Normal application use needs no Playwright.
CI retains Python 3.12 and 3.13 compatibility checks.

[UI validation](docs/UI_VALIDATION.md), [packaging validation](packaging/VALIDATION.md),
and [the roadmap](docs/ROADMAP.md) distinguish actual checks from remaining work.
No private case is a test fixture. Synthetic checks establish application contracts,
not broad forensic accuracy. Remaining gaps include a clean-account/second-Mac
acceptance run, independent multi-OS accuracy evidence, wider symbol/plugin
compatibility, interruption/storage limits, broader accessibility testing and
credentialed release acceptance. Intel/Windows distributions, parallel analysis and
polished report exports remain future work. **Quick triage and compatibility sweep
buttons are proposals and are not implemented.**

The weekly/manual core updater proposes eligible stable `v0.1.x` API-1 updates in a
PR; startup never updates or merges automatically. Review and validate each new pin.
To roll back, restore a tested app/environment while idle and keep the same private
data roots. Existing evidence and sealed reports are not regenerated by an upgrade.
