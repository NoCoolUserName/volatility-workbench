# Native macOS application

Volatility Workbench's optional macOS application embeds the existing authenticated
loopback UI in the system WebKit view. It uses standard decorated macOS windows,
not an Electron application or a second frontend. Browser/CLI mode remains available.
The native distribution targets Apple silicon and macOS 13 or later; development
verification was performed on an ARM64 Mac running macOS 26.4.1. Intel Macs,
Windows hosts and containers have not been validated by this release. Browser
code sharing does not establish Windows support (the backend currently uses
POSIX process locking).

## Build, install, open

From a configured development checkout, with Xcode command-line tools:

```sh
python scripts/build_macos.py --cache /tmp/workbench-build-cache --output dist/macos
python scripts/install_macos.py 'dist/macos/Volatility Workbench.app' --desktop-launcher
open "$HOME/Applications/Volatility Workbench.app"
```

The builder requires a clean commit for a release and records its full SHA,
exact core revision, package versions, source hashes and notices. `--allow-dirty`
is for development candidates only; the installer refuses those builds. See
[packaging](../packaging/README.md) for signing, validation and release details.
The default installation needs no administrator account. Its bundled standalone
Python and separate analyzer runtime do not require a source checkout, Homebrew,
a development virtual environment or an interactive shell's PATH.

The optional Desktop launcher is a real small `.app`, not an alias or symlink.
It opens the installed app without Terminal or a browser. Installation preserves
the previous application and old command launcher in timestamped rollback storage
under `~/Library/Application Support/Volatility Workbench/rollback`. Quit the
application before replacement; the installer refuses an active target process.
To roll back, quit the app and restore the saved application/launcher from that
folder. Evidence, case state and reports are outside these replaceable bundles.

## Existing and new installations

On first launch, the app imports a compatible configuration from the established
local Forensics installation or the normal core config location, retaining its
physical evidence/output paths and existing case state. It copies configuration
into private application preferences; it does not move evidence or rewrite sealed
reports. An explicitly configured external analyzer remains selected, including
its working local addons. Only recognized bundled runtime paths are rebased after
application relocation, under the same case lock, with configuration backups.

New installations use the bundled analyzer and show Settings with native folder
selection, AI configuration, optional community plugins and bounded symbol packs.
Skip setup to browse saved material. Missing AI authentication does not block the
window, settings or Plugins. Startup and catalog refresh do not analyze or hash
memory images. Readiness means ready to attempt analysis, not that exact image
symbols are present or that an image is clean.

Preferences and WebKit data live in `~/Library/Application Support/Volatility
Workbench`; mutable symbol lookup caches live in `~/Library/Caches/Volatility
Workbench`. Evidence and outputs remain at their configured locations. Settings
can change empty-installation evidence/output roots, but deliberately refuses
moving established cases through a settings save. See [Settings and symbols](SETTINGS_AND_SYMBOLS.md).

## Window and lifecycle

The app has native traffic lights, rounded window corners, resizing/full screen,
standard editing shortcuts, an application menu with build information, Settings
and Quit, and saved monitor-clamped geometry. Closing the window hides it while
work continues. Reopening from the Dock or launcher brings it back. Repeated
launches reuse one compatible backend and its queue.

Quit is immediate when idle. With active work it offers Keep working or Cancel
work and quit; completed evidence is retained and interrupted work remains
explicit. Plugin/symbol maintenance must finish before quitting. An incompatible
already-running backend is reported; it is never killed to make the app start.
The existing backend's version fingerprint and state lock remain authoritative.

The UI uses the existing Host/Origin/cookie and content-security protections.
Only same-origin application navigation stays inside the WebView. Deliberate
external web links open in the system browser. There is no application Python
bridge exposed to page scripts. WebKit's normal copy/save-image controls are
available; a native Save panel handles the explicit coin Save image link. Recovered content is
still rendered by the existing safe viewers. Polished report exports remain
outside this release.

## Components and limits

The current public bundle contains CPython 3.12.15, pywebview 6.2.1, the pinned
core recorded by `core-dependency.json`, and Volatility3 2.28.2 with locked analysis
dependencies. The release builder refuses a core pin that disagrees with
`pyproject.toml` or `requirements.lock.txt`. Its actual catalog contains 200
plugins (197 official, XP addon, pypykatz and EVTX), with no import failures
in packaged discovery. Discovery is
not a claim that every plugin works against every memory image.

The remaining supported community profile is an explicit upstream download into
an idle, validated runtime overlay outside the signed app. Unresolved licensing
or source obligations exclude those components from public binary redistribution.
The configured local analyzer currently has 214 commands, preserving its original
208 names. It can continue to be used intact; the public bundle baseline stays 200.
Unknown local additions are not silently discarded. See the core's
[community plugin policy](https://github.com/NoCoolUserName/volatility-mcp/blob/main/docs/COMMUNITY_PLUGINS.md).

Codex retains its existing supported sign-in. A separate bounded compatible-API
adapter is opt-in and must pass a synthetic tool capability check. Newly saved
secrets use macOS Keychain or session-only storage; provider changes do not move
existing conversation IDs between adapters. See [AI providers](AI_PROVIDERS.md).
Local files remain local, but selected questions/tool excerpts can reach the
chosen AI service. Same-user subprocess separation is not a malware sandbox.

Local builds are ad-hoc signed unless an operator supplies applicable signing
credentials. Ad-hoc signing is not Developer ID signing or notarization; no
Gatekeeper protections are disabled. See the [optional release pipeline](MACOS_RELEASE.md)
for auditing, staged notarization and the credentialed checks still required. See [validation](../packaging/VALIDATION.md)
and [UI validation](VALIDATION.md) for observed checks and remaining limits.
