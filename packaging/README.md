# macOS distribution profile

The application uses the shared Workbench backend and UI. Its small native ARM64
launcher embeds the pinned standalone CPython runtime and starts
`volatility_workbench.desktop`. It is a decorated Cocoa/WKWebView window through
pywebview. Browser and CLI entry points stay available.

`distribution.json` selects the Python, Volatility, plugin and symbol profiles.
It references the repository's immutable `core-dependency.json` and core's
packaged addon inventory, rather than duplicating community-plugin contracts.
`macos/desktop.lock.txt` adds Cocoa dependencies to the ordinary core lock.
`macos/analyzer.lock.txt` records official `volatility3[full]` plus the supported
addon dependencies. Cloud filesystem and Arrow export extras are optional
upstream features, outside this local-file profile. The tested host is ARM64
macOS; no Windows or container distribution has been built.

## Build, validate, install

On an ARM64 Mac with Python 3.12+ and Apple's command-line compiler tools:

```sh
python3 scripts/build_macos.py --output dist/macos
python3 scripts/validate_macos.py 'dist/macos/Volatility Workbench.app'
python3 scripts/install_macos.py 'dist/macos/Volatility Workbench.app' --desktop-launcher
open "$HOME/Applications/Volatility Workbench.app"
```

The build downloads hash-pinned official Python distributions and installs exact
package versions in clean runtimes. It never copies a development virtualenv.
The Python build host is needed only to build; the installed app needs neither
Python/Homebrew nor the source checkout. `--allow-dirty` builds are explicitly
marked development candidates and the installer refuses them. The release
manifest records the Git revision, package-source digest, core VCS revision,
package versions and artifact hashes. The dependency wheelhouse and Python,
package and plugin notices are retained. The ZIP is an installable archive, not
a signed/notarized installer package.

The native build installs the full MCP release wheel pinned by URL and SHA-256 in
`distribution.json`, verifies its source revision against `core-dependency.json`,
and checks every embedded symbol pack. Update both pins together. Source/CLI
installs retain the VCS dependency; the native app includes all four packs and
their upstream notices. The large wheel remains in the build cache rather than
being duplicated in the app wheelhouse. Fresh setup provisions local copies through
the shared MCP API and never falls back to downloads for a missing bundle.
The native validator exercises that path with network access forbidden.

The default signing is local ad-hoc signing. The optional `--sign-identity`
path requires a valid Developer ID Application identity, explicitly signs native
components with secure timestamps/hardened runtime where appropriate, updates
package inventories and seals the app last. The separate
[release command and checklist](../docs/MACOS_RELEASE.md) audit a build, support a
read-only dry run and, only when explicitly invoked with a Keychain profile,
submit a staged copy to Apple, staple its ticket and produce a verified archive.
Actual Developer ID runtime compatibility and Apple acceptance remain unverified
without a credentialed release. No Gatekeeper setting is changed.

Installation validates before replacing a bundle and refuses to replace a
running native app. Quit normally while idle; it never kills an investigation.
An existing app is retained in
`~/Library/Application Support/Volatility Workbench/rollback/<timestamp>/`.
Only the application is replaced; configuration, evidence and case storage stay
outside it. Roll back while idle by restoring that previous bundle, preserving
user data. `--desktop-launcher` creates a real small
`~/Desktop/Launch Volatility Workbench.app` using a bundled native Cocoa helper.
It opens the installed application with NSWorkspace and reuses its icon. It is
neither an alias/symlink nor a shell script, and it opens no Terminal window.
The installer verifies the final target and signature before removing the old
`.command`; `ditto` retains that old launcher and Finder metadata under the same
rollback timestamp in `Desktop/`. An earlier application is under `Applications/`.
If launcher activation fails, the earlier app and launcher are restored. No Dock
preferences change. No compiler is required to install or use this helper.
First installation has no prior main application bundle to back up.

## Runtime layout and immutability

`Contents/Resources/runtime/bin/python3` is the real app/core interpreter, and
`analyzer/bin/python3` is the separate real analyzer interpreter. Case-scoped MCP
uses the former, and core invokes the latter with the explicit `analyzer/bin/vol`
script. `sys.executable` is a genuine interpreter, not the app executable. Dynamic
plugin discovery, distribution RECORD metadata, resources and extension modules
remain on disk. The native executable sets `VOLATILITY_WORKBENCH_RESOURCES` from
its own bundle location; runtime resolution does not depend on a shell or cwd.

A packaged site hook disables runtime bytecode writes even for `python -I`;
bootstrap bytecode is compiled before signing. Mutable caches, overlays, symbols,
settings and logs belong outside the bundle. A fresh managed overlay is created
at its permanent private path with the bundled Python's `venv` command, then
populated from the analyzer wheelhouse; an existing venv is never moved. Plugin
updates are explicit, staged and idle-only. The configured external analyzer may
also be reused unchanged.

## Project licenses and matching source

The original Workbench and MCP source is offered under VSL 1.0 and MIT. The
integrated application follows VSL's source and notice requirements; no advance
Foundation approval is required when using those terms. Both license texts and
the component map ship in wheel metadata. Native builds also retain Workbench
notices under `notices/dependencies`, core notices under `notices/core`, and
`notices/SOURCE_CODE.json` with the exact Workbench/core revisions and upstream
Volatility source location. The release audit checks these files and revisions.

Before public distribution, publish the matching project source under VSL at a
freely accessible location and verify access without signing in. A private source
URL in the notice does not satisfy this requirement; publish a reviewed matching
source archive or make the intended source repository public at release time.
See [LICENSING.md](../LICENSING.md) for the license map. Third-party art and plugins
retain their own rights and notices.

## Bundled plugin scope

The base public artifact includes official Volatility plugins, core's independent
XP compatibility addon, the pinned MIT pypykatz wrapper/dependencies, and MIT EVTX
from the core community profile, plus the independent VSL-1.0 CryptoMem plugin.
CryptoMem is fetched unchanged from the core inventory pin; its original source
and complete LICENSE/standards notices are retained under `notices/`. The app
contains no separate detector implementation. Catalog attribution distinguishes
these sources. The actual discovered count is generated by validation, not hardcoded
as a promise. Import success does not establish image compatibility or forensic
accuracy.

The remaining profile sources use explicit upstream download into a managed
writable overlay or the existing compatible analyzer. At the pinned revisions,
forensicxlab and browser-history have no explicit redistribution permission;
f-block includes GPL-derived portions. They are deliberately absent from the
redistributable base bundle until permission/source-distribution obligations are
resolved. Their existing local copies are not removed. The upstream downloader
uses core's source hashes, compatibility adaptation, notices and execution lock.
No new marketplace or arbitrary plugin-directory tool is introduced.

## Verification scope

`validate_macos.py` launches bundled interpreters from a temporary directory with
a minimal GUI-like environment. It verifies core commit provenance, native
imports, real catalog/source attribution, a real MCP handshake/catalog call, and
one synthetic banner-plugin execution. It checks signing after runtime execution
and rejects non-system absolute native-library dependencies. No private image is
opened. This does not by itself verify native UI/window lifecycle; those are
separate installed-application checks recorded in the validation document.

Primary packaging references:
[clean-install acceptance](../docs/CLEAN_INSTALL_ACCEPTANCE.md),
[standalone Python distributions](https://github.com/astral-sh/python-build-standalone/blob/main/docs/distributions.rst),
[CPython embedding configuration](https://docs.python.org/3.12/c-api/init_config.html),
[pywebview macOS backend](https://pywebview.flowrl.com/guide/renderer.html), and
[pywebview FAQ](https://pywebview.flowrl.com/guide/faq).
