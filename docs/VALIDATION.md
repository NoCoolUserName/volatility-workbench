# Validation ownership

Application and separation checks are recorded in [UI_VALIDATION.md](UI_VALIDATION.md).
Core execution/reuse, artifact inspection, saved-evidence/citation, coverage, and
protocol checks are maintained in the
[core validation record](https://github.com/NoCoolUserName/volatility-mcp/blob/main/docs/VALIDATION.md).

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
