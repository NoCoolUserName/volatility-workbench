# Volatility Workbench

*12,681 lines of code*

An experimental local application for exploring existing memory acquisitions with
[volatility-mcp](https://github.com/NoCoolUserName/volatility-mcp). It provides saved
cases, sequential analysis jobs, resumable case conversations, versioned reports,
saved evidence and citations, coverage views, and a searchable plugin catalog.
Use the native macOS application or the same interface in a browser.

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

The header and Settings share 31 locally bundled appearance choices. A new browser
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

The tested core pin is `7f7cc1f0c4f4f6e6a17dfecca8c27db02e53c1d6`, API revision 1.
`core-dependency.json`, `pyproject.toml` and `requirements.lock.txt` agree on the
immutable commit. `pip install .` brings in that dependency; the pin helper checks
installed Git provenance even when successive core commits share a package version.

The validated portable public bundle baseline has **200 commands**. The existing
configured local analyzer has **214 commands**, preserving all original 208 names,
with zero import failures. These are different installation profiles. Counts are
measured from the selected runtime and do not establish image compatibility.

Core's single opt-in community inventory includes PteMalfind/Ptenum, ImgMalfind,
Prefetch, AnyDesk, EVTXLog, Browser History Extractor and KeePass, plus CobaltStrike,
RichHeader, ZoneID3, PteResolve, PasswordManager and SSHKeys. The six recent additions
are forced offline. PasswordManager and SSHKeys are manual-only sensitive extraction
commands, excluded from automatic investigation/report flows. PasswordManager needs
an explicit browser PID; SSHKeys needs a Linux PID and one suspected `sshenc` address.
No installed command is silently removed.

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
as a validation-only dependency; `check_themes_browser.cjs` checks all 31 skins under
the production content-security policy. Normal application use needs no Playwright.
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
