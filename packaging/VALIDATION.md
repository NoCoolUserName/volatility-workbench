# macOS packaging validation

The following checks were performed on an ARM64 Mac with macOS 26.4.1. They
exercise the packaged runtime; native-window interaction is recorded separately
in the Workbench UI validation documentation.

- Nine deterministic offline packaging tests pass: lock/inventory references,
  corrupt cached download rejection and atomic activation, archive traversal
  rejection, dirty-build installation refusal, active bundled-process refusal,
  simulated installation rollback after activation failure, real launcher layout/target/icon and deferred old-launcher removal, launcher activation rollback, and symlink refusal. A compiled Cocoa helper also resolved its temporary app target successfully without opening it.
- A complete application and ZIP were built from fresh, hash-pinned standalone
  CPython 3.12.15 runtimes, independent app/analyzer package environments and exact
  dependency locks. No development virtualenv was copied. The candidate carried
  an explicit uncommitted-source label; release installation requires a clean
  commit and records its exact revision.
- The embedded native executable's fixed runtime self-check passed with no LANG
  variable, a minimal PATH, and a temporary HOME/cwd. UTF-8 source labels survive
  a real subprocess round trip. Bundled Python import paths remain within the
  application, with runtime bytecode writes disabled.
- The actual bundled core revision matches the immutable pin, including VCS
  provenance. Native imports for Capstone, YARA, cryptography support, Pillow,
  EVTX and pypykatz passed. The bundled catalog discovers **200 plugins** and no
  import failures: 197 official plus XP compatibility, pypykatz and EVTX. Source
  attribution remains native/community/local. These numbers describe this build.
- The official MCP SDK initialized a real bundled stdio server and called its
  catalog tool. A synthetic byte file exercised one real `banners.Banners`
  subprocess per validator run and recovered its expected test string. No private
  memory image, recovered executable, real investigation or model service was
  used by this validator.
- The `.app` path includes spaces. Native libraries require system paths or
  bundle-relative dependencies; a dylib's own identifier is checked separately
  from a dependency load path. Strict/deep signature verification passes **after**
  runtime imports, catalog discovery, MCP and fixture execution, confirming that
  these operations did not alter sealed bundle resources.

Concrete defects found and repaired: Python's isolated mode ignores the
`PYTHONDONTWRITEBYTECODE` environment variable, so prebuilt bootstrap caches and
an installed site hook now prevent bytecode mutations. Finder's missing shell
locale initially caused ASCII decoding of Unicode catalog labels; the native
launcher now initializes UTF-8 before CPython starts and has a direct regression
check. The validator initially mistook universal Mach-O architecture headers and
YARA's own dylib identifier for loaded external libraries; it now inspects those
separately while continuing to reject external build-library dependencies.

Installed distribution RECORD entries are recomputed after relocatable entrypoint
normalization and native signing. Only existing RECORD members are updated, so
additional plugins are not falsely promoted to official Volatility files.
Original wheel hashes and upstream notices remain available for provenance.

Local signing is ad-hoc. No Developer ID signing or notarization was performed.
Synthetic import/contract checks do not establish forensic accuracy, correctness
on real memory images, or support for every OS/kernel. Windows/container builds
and a public notarized release remain untested. The optional community profile
retains explicit upstream download because selected upstream license/source
obligations are unresolved for public bundling.

## Release machinery checks — 2026-10-18

The optional release path is implemented in `scripts/release_macos.py`; its
operator checklist is [MACOS_RELEASE.md](../docs/MACOS_RELEASE.md). These checks
used harmless fixtures or a temporary copy of the existing app. The installed
application and private images were not modified by packaging checks.

- **Automated/offline:** 25 packaging/release tests pass (nine existing packaging
  tests and sixteen release tests). They cover explicit native signing flags,
  valid Developer ID identity selection, universal Mach-O parsing, symlink escape
  rejection before metadata reads, selected private-file guards, reviewed profile
  and excluded-addon checks, read-only dry run, ad-hoc submission refusal,
  immutable inputs/new output directories, simulated Apple acceptance/rejection,
  mixed-team/debug/runtime rejection, Gatekeeper failure, timeouts with partial
  logs and interruption. Apple responses in these tests are simulated.
- **Installed-package integration:** the isolated `scripts/package_smoke.py` run
  passed its real SDK/HTTP checks and all 89 tests then present, using an installed
  wheel outside the checkout. Three additional timeout/team/staged-audit regressions were added
  afterward and passed in the 25-test targeted run. The initial restricted suite
  hit three loopback `PermissionError` failures; the installed-package run with
  loopback permission passed those checks. No product change was needed for that
  execution-environment restriction.
- **Real native signing:** compiled a tiny ARM64 executable and dylib, signed
  their individual files ad hoc, wrote synthetic inventory before the final app
  seal, and verified both execution and a `ditto` ZIP/extraction round trip.
  Deliberate post-seal resource modification correctly failed signature checking.
- **Real complete-app regression:** copied the prior clean native build into a
  temporary directory, explicitly signed all 301 Mach-O components ad hoc and
  sealed the outer app using the new code. Existing `validate_macos.py` passed:
  bundled native imports/UTF-8 self-check, actual stdio MCP catalog call, 200
  discovered plugins with zero import failures, one synthetic `banners.Banners`
  invocation, portable native linkage and strict/deep signature verification after
  runtime use. Zero private images were opened. This reused the prior app; it was
  not a fresh dependency rebuild or a Developer ID runtime test.
- **Read-only real-package audit:** the installed clean app passed profile,
  notices, addon, symlink, selected private-name and file-inventory checks. Its
  dry-run plan completed without creating a release directory or submitting it.

Review repaired a potentially misleading runtime check: it now reads the actual
CodeDirectory hardened-runtime flag, rather than accepting the word `runtime`
which can also occur in an executable path. The regression includes that path.
Timeout diagnostics preserve captured partial output. The staged copy is audited
and its signatures rechecked before upload, guarding against content changing
between the initial audit and copy; a regression verifies that newly introduced
private configuration blocks submission. Inspection of outgoing
source excludes all local audit logs, inventories, private state and case data.

No valid Developer ID identity is installed on the validation host. No real Apple
submission, stapled production ticket, credentialed hardened-runtime launch or
fresh downloaded-app Gatekeeper test has been performed. No entitlement exceptions
were added speculatively. Those checks are required before a public notarized
binary release; this change prepares the machinery and does not claim one exists.

## Community inventory revision 4 adoption — 2026-10-18

Workbench pins merged core `5bede5123abf7286ddea0a05cf0482920d94ac2e`.
The installed-wheel smoke passed outside the checkout: all 118 application tests,
real MCP negotiation in both protocol modes, HTTP/assets and zero analysis/model
subprocesses during the UI smoke. The source review and optional-download manifest
now include the six added commands; upstream implementations remain owned by core.
Manual-only extraction is excluded from automatic investigation instructions.

The public bundle retains its eligible 200-command baseline. The existing local
configured analyzer has 214 commands, all original 208 preserved, zero import
failures, verified adapted hashes and both SSH symbol schemas. This configured
analyzer is independent of the bundled baseline. Native build/install verification
is recorded with each artifact's exact source/core commits and the installation
report; synthetic contract success is not a broad forensic-accuracy claim.

## Theme assets and decimal-unit core pin — 2026-10-18

The theme follow-up pins core `7f7cc1f0c4f4f6e6a17dfecca8c27db02e53c1d6`
(core PR #12), retaining API revision 1 and community inventory revision 4. This
changes descriptive KB/MB values exactly while preserving adapter hashes, runtime
bounds and commands. The public eligible baseline remains 200; the existing
configured analyzer remains the separately provisioned 214-command environment.

The final fresh installed-wheel smoke passed 118 Workbench tests, dependency
checks, ten-tool MCP discovery in both SDK modes and startup from outside the
checkout. All 30 SVG scene assets, the generated Halloween PNG, shared theme
JavaScript/CSS and other packaged assets were present and served successfully.
The smoke forbade analysis/model subprocesses and used only temporary synthetic
state. The native validator now independently requires all 30 scenes and the new
shared assets. Browser checks under production CSP loaded every scene with no
external requests or policy violations; UI_VALIDATION.md records interaction and
contrast checks. The only later runtime change was the readiness annotation's CSS
alignment, covered by the original header and all-theme browser checks.

The final server-route repair removes request text from filesystem path assembly:
only packaged SVG names enter the static asset map. An authenticated HTTP fixture
covers a valid scene plus missing and plain/encoded traversal names. This followed
CodeQL's path-injection warning; the gate remains enforced.
