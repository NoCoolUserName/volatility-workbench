# Volatility Workbench

*22,847 lines of code*

*Latest measured macOS ARM64 build: app 1,289.76 MiB (1,352,409,792 bytes); distribution ZIP 1,073.95 MiB (1,126,118,845 bytes). Built from `4120e7097d0d3421c5bfe15707a546929fd70d3f`, measured 2026-10-31; excludes symlink aliases and private evidence, case state and caches.*

An experimental local application for exploring existing memory acquisitions with
[volatility-mcp](https://github.com/NoCoolUserName/volatility-mcp). It provides saved
cases, sequential analysis jobs, resumable case conversations, versioned reports,
saved evidence and citations, coverage views, and a searchable plugin catalog.
Use the native macOS application or the same interface in a browser. The optional
[Colossal Cave Adventure Easter egg](docs/ADVENTURE.md) has a separate license and game-data
provenance review for both the 1977 and 1995 editions.

Workbench provides the interface. The separate core handles forensic execution,
integrity checks, saved-result reuse, artifact inspection, queries, citations, and
coverage.

Workbench 0.1.3 pins MCP 0.1.4 and CryptoMem 0.5.0: opt-in English BIP-39, Bitcoin WIF/xprv/tprv and explicitly ambiguous transaction-ID candidates. Secrets remain masked in ordinary outputs; complete extraction is explicit and local-only. Existing address defaults, three OS adapters and ten MCP tools remain. Exact captured-kernel symbols are required; real-memory Linux/macOS validation remains outstanding.

Original project code is available under MIT and the Volatility Software License 1.0. Integrated Volatility distributions follow VSL's source and notice requirements; see [LICENSING.md](LICENSING.md) for the component map and release steps.

## Implemented workflow

- Register existing images by physical path, folder browser or macOS file picker.
  Images stay in place. Unrelated images get separate cases; explicitly related
  captures can share a case even when they live in different folders. Each case's
  MCP server can access only its selected files.
- Check readiness, generate a report, ask follow-up questions, and create a new
  report revision. Jobs run sequentially with progress, Stop, cancellation and
  interrupted-work recovery. A successful readiness check allows analysis to be attempted;
  it does not establish a clean result or guarantee matching symbols.
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
- Open the case's **Console / VolShell** for manual Python commands, reviewable
  **AI command suggestions**, or **AI investigation** through the existing case
  agent. Suggestions remain inert until explicitly run. AI investigation uses
  saved evidence and the existing extraction approvals without creating a report
  revision; manual input pauses while it runs. The VolShell bezel button connects
  or disconnects the local interpreter, with its light reflecting confirmed
  connection state. See [VolShell modes and limits](docs/LOCAL_UI.md).

See [the local workflow](docs/LOCAL_UI.md), [Settings and symbols](docs/SETTINGS_AND_SYMBOLS.md),
and [ownership and recovery](docs/SEPARATION.md).

## Native macOS application

The tested distribution targets Apple silicon and macOS 13 or later. It opens a
decorated system WebKit window with native menus, Settings, saved geometry and a
Dock icon. Closing hides the window while work continues; reopening restores it.
Quit asks before cancelling active work. Separate relocatable Python application
and analyzer runtimes mean the installed app needs no source checkout, Homebrew,
development environment or shell startup file.

Download the [Workbench 0.1.3 macOS ARM64 prerelease](https://github.com/NoCoolUserName/volatility-workbench/releases/tag/v0.1.3)
and its `Volatility-Workbench-macos-arm64.zip` asset. Verify the archive against
the release's `SHA256SUMS`, then extract it to access `Volatility Workbench.app`.
This published app is ad-hoc signed, without Developer ID signing or Apple
notarization; downloaded-app Gatekeeper acceptance remains unvalidated. See
[native setup and limits](docs/MACOS_APP.md) and the installation/rollback guidance
below before replacing an existing app.

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
optional Desktop launcher is a native `.app` and opens no Terminal window.
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
Before moving existing roots, back up and update their mutable path metadata;
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

The tested core pin is MCP 0.1.4 at `2887c77283da4a45860d8ac2f3042027401257a0`, API revision 1.
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
scans one selected Windows, Linux x86-64 or experimental legacy Intel64 Mac process for Bitcoin, Ethereum-style,
XRP classic and Monero address candidates and bounded payment requests. Find
`windows.cryptomem.CryptoMem`, `linux.cryptomem.CryptoMem` or
`mac.cryptomem.CryptoMem` in Plugins and supply a
process PID (not a Linux thread ID). It runs offline through the shared core, preserves
process/virtual-offset provenance, and remains manual-only. Address validation
does not establish wallet ownership; real-memory recovery is still unvalidated.
Existing external analyzers receive it through the same explicit plugin installer.
See [CryptoMem capabilities and limits](https://github.com/NoCoolUserName/volatility-mcp/blob/main/docs/CRYPTOMEM.md).
CryptoMem 0.5.0 retains `--currency xmr` (also included by `all`) for standard,
subaddress and integrated Monero address candidates with encoding/checksum
validation. Monero wallet/curve validity, Monero keys/seeds and Monero payment-URI
interpretation are outside its scope. Linux symbols must
match the captured kernel exactly. Core's explicit symbol installer can provision
the pinned 10,255-table x86-64 collection into the shared offline store; see
[package setup](docs/MACOS_APP.md). Other Linux architectures remain unsupported
until tested. The Mac adapter requires exact Darwin kernel symbols; the legacy
Mac pack is not universal coverage. Nested submaps fail as incomplete, including
ordinary shared-region submaps. Apple silicon/Intel32 Mac captures and modern
macOS are unsupported; real-memory Mac validation remains outstanding. Running
this ARM64 app is distinct from analyzing an ARM64 capture. The app still uses
the same ten MCP tools.

Redistribution restrictions keep selected upstream sources out of the public app;
install them explicitly through idle Settings maintenance or core's installer:

```sh
.venv/bin/python -m volatility_mcp plugins-install --config /absolute/path/to/config.json
```

Refresh Plugins afterwards; restart idle clients that retain an older catalog.
See [core's profile, source attribution, licenses and limitations](https://github.com/NoCoolUserName/volatility-mcp/blob/main/docs/COMMUNITY_PLUGINS.md).
The UI and help text use decimal KB/MB; a 4,096-byte page is 4.096 KB. This conversion
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
as a validation-only dependency; `check_themes_browser.cjs` checks all 37 skins under
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
