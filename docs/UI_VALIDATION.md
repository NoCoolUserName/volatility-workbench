# Workbench validation — experimental first version

## Fallout 76 terminal variants — 2026-10-20

Added Camden Park and Field Terminal to the shared frontend catalog and durable
preference allowlist. Existing catalog-count assertions were updated for 35 themes
and 16 Fallout choices. The initial CSS-only housings were rejected by the user;
their preview files and native build were deleted and never installed.

Replacement transparent frames were edited from the user's references using the
built-in image editor, preserving detailed materials and control placement. Their
alpha channels have empty screen openings. Desktop main-UI and console previews
were rendered in Chrome with synthetic content; glass fill, text insets, control
placement and native frame proportions received visual review. Live console text
is HTML, and the decorative overlay does not intercept input. The new PNGs have
explicit packaged HTTP routes. No local automated tests were run for this theme
batch. These previews do not establish mobile or native WebView behavior. Native
build and installation status are recorded separately; no real investigation ran.

## Report request queue and Coverage — 2026-10-20

Focused synthetic checks passed: 22 Python tests covering FIFO requests,
pending duplicates and request-ID retries, immutable Rerun prompts, continuation
after failures, successive updates selecting the latest successful report,
deferred deletion between jobs, and existing report cleanup safeguards.
Browser checks passed for request submission/estimates, Coverage, running reports,
report cleanup, and report return navigation. They covered preserved unsent text,
double activation, unknown/overrun estimates, all saved scope and attempt pages,
failed reads and stale case responses, and the shared back-to-top button.
The final deletion-error wording received source review after those checks.
These checks used synthetic state and simulated services, without real analysis.
Native installation of this batch has not yet taken place.
## Focused keyboard and accessibility review — 19 October 2026

Reviewed upstream `7da02db009a5a79e11ce3d16e6c0f56e0b4a7b7c` with
synthetic cases and intercepted local browser requests. No private investigation,
saved evidence, real interpreter or provider was used. Four reproduced defects
received targeted corrections:

- Escape/Collapse now returns focus to the visible control that opened the
  monitor, with the existing fallback when that control is unavailable.
- A visually hidden, atomic polite status region outside the normally closed
  connection disclosure exposes case-bound connection transitions. Unchanged
  polling snapshots do not rewrite the announcement; raw output is not included.
- Case buttons retain their DOM identity and keyboard focus across polling and
  reordering. `aria-current` identifies the selected case without changing it.
- The Settings link and return link carry the selected case ID, so returning
  does not silently select a newer case. This does not rebind provider settings.

`scripts/check_accessibility_browser.cjs` passed ten synthetic check groups:

1. Enter opens the monitor; Escape and the Collapse button restore the opener.
2. Tab/Shift+Tab follow visible enabled controls in manual, AI suggestions and
   AI investigation modes, and wrap inside the modal in both directions.
3. The closed disclosure leaves connection status in Chromium's accessibility
   tree; a changed readiness state updates it, while identical refreshes do not.
4. Manual Tab accepts a visible completion without execution; Shift+Tab navigates;
   Escape dismisses completion; Shift+Enter adds a line; Enter submits once with
   the exact synthetic case/session binding.
5. AI suggestion text does not submit on Enter. Requesting a proposal and adopting
   its draft require separate explicit button activations; adoption does not run it.
6. AI investigation text, Enter, Tab and mode changes do not submit work implicitly.
   Explicit investigation/approval/pause/Stop paths remain covered by the existing
   VolShell browser suite.
7. Keyboard selection of another console target hides the old transcript, disables
   mismatched manual input, leaves the main case selected, and submits nothing.
8. Case-button focus survives identical polling and case reordering; Enter changes
   the selected case and its semantic current marker only explicitly.
9. A keyboard Settings round trip restores the older selected case and its own
   console output without POST requests.
10. Mode, Command, Collapse and connection-disclosure names are exposed; keyboard
    focus outlines remain visible in Matrix/New Vegas; reduced motion suppresses
    the indeterminate progress animation, which resumes with no preference.

The existing VolShell, live/saved console, Settings, report-return and case-header
browser suites passed. Report-return includes keyboard evidence opening, exact
focus/scroll restoration, case switches and stale-request rejection. The saved
console test now expects the actual monitor opener, and checks New Vegas text
contrast on its deliberately recessed console surface instead of assuming it
matches the body/header palette. Production theme CSS was unchanged.

Environment limitation: the connector snapshot cannot retrieve the large
`halloween-night.png` asset. The application suite ran all 245 tests: 244 passed,
with one missing-asset error in `test_assets_and_installed_contract`. The standard
package smoke built and installed the Workbench and pinned core wheels and passed
dependency health, but stopped at that same missing asset before HTTP/protocol
smoke completion. No assertion was skipped or weakened to turn these runs green.
The VolShell and live-console browser runs used an external synthetic raster
fixture for unavailable artwork reads; this does not validate the original
Halloween illustration. No replacement artwork is part of the change.

Remaining acceptance requires actual macOS VoiceOver and the packaged pywebview
application: spoken live-region timing/verbosity, native select/disclosure behavior,
Full Keyboard Access and macOS keyboard-navigation preferences, modal focus return
with assistive technology, and system Reduce Motion. Chromium accessibility-tree
and CSS checks do not establish those platform behaviors or full WCAG conformance.

## Theme selector — 2026-10-07

The static Workbench UI was opened in the in-app browser against a local static
server. Selecting Soft black and white produced an almost-black background,
off-white text, and a neutral gray accent. Selecting Light blue changed the
background and accent to the blue palette, and the selected option survived a
reload. This isolated preview has no Workbench API, so its connection error is
expected. The existing 22 UI tests passed under the repository virtual
environment; JavaScript syntax passed. No memory analysis or report operation
was run. The header was also adjusted for the narrow preview viewport.

Validation: 2026-10-04 UTC. Assessment: **ready with stated limitations for the
local Apple-silicon/Codex use case**. This records project-team implementation
review and testing, not an independent security audit or forensic certification.
Private receipts, screenshots, actual paths, and memory outputs are excluded from Git.

## Automated checks with harmless fixtures

- The full suite completed 57 passing tests and one expected skip for the optional
  addon tests that require the separate Volatility environment. This included nine
  initial UI tests. After focused repairs, all 17 affected UI tests passed, for
  65 distinct passing core/protocol/report/UI checks across these runs.
- The UI tests exchange real stdio MCP messages with the existing server code and
  a clearly synthetic analyzer. Codex responses are simulated; no model API or real
  malware is used in CI. Existing protocol checks verify the core's six tools
  without reporting configuration or UI imports.
- Covered: readiness, provenance/links, report sealing, source preservation, same
  conversation follow-ups, immutable prior versions, grouped/separate captures,
  input and artifact path/symlink rejection, bounded large-output reads, duplicate
  request IDs, queued-work cancellation, interrupted readiness, restart recovery,
  missing-symbol limitations, changed evidence/run identity rejection, unsupported
  approvals, explicit command and MCP form decisions, and enforced-policy mismatch.
- Real local HTTP checks covered authentication, cross-origin/Host rejection,
  action requests without Origin, cookie flags, and refresh without new jobs.
- Python compilation and JavaScript syntax checks passed. A wheel built without
  installing dependencies and included all UI static assets. Importing the core
  server in isolated Python imported neither the UI nor reporting module. The UI
  adds no runtime dependency beyond the core's existing dependencies.

## Actual browser checks

Headless installed Chrome was driven with Playwright 1.63.0 from a temporary
validation installation, not a UI dependency. A harmless fixture exercised path
registration, readiness, first report, executive-summary placement, evidence-link
navigation, reload/reconnection, case question, second sealed report, and Stop.
No JavaScript page errors were recorded. UI state and completed work survived
refresh without duplicate scans. The fixture agent/analyzer were simulated.
A final browser check against the real case verified three report versions,
saved-evidence navigation, and inert rendering of controlled HTML/script-like
text and unsafe link syntax, again with no JavaScript errors.

The macOS native file-picker AppleScript compiled successfully. Interactive Finder
selection was not exercised; it remains a manual platform check. Other browsers,
accessibility assistive technologies, and non-macOS hosts remain unverified.

## Real Codex and Volatility integration

- Installed Codex 0.160.0 app-server initialized over stdio and reported existing
  ChatGPT authentication. No model provider, API key, or billing mode was changed.
  The actual generated protocol schema was inspected before implementation.
- A dedicated private case thread reported read-only sandboxing and on-request
  approvals routed to the user. Codex's state database required a specific approved
  execution outside the implementation session's workspace filesystem sandbox;
  the Workbench did not alter global Codex settings or disable its sandbox.
- Browser-driven readiness used a single existing Windows training image. Actual
  MCP banner and Windows info discovery succeeded and saved complete outputs.
  Source integrity checks passed. No exhaustive investigation was performed.
- The first agent-initiated process-list request was rejected before execution
  because MCP form elicitation was not supported yet. The first report correctly
  documented this gap. A sealed report is structurally valid and preserved; it is
  not proof of complete investigative coverage.
- A real follow-up after application restart resumed the same case thread and
  answered from saved outputs. An explicit report update produced a second sealed
  version without changing the first version's checksums or running more analysis.
- The second review repaired MCP form approvals. The exact scoped PsList request
  was inspected and approved once through the browser; the actual process-list
  execution then succeeded with unchanged source identity. No persistent approval
  rule was granted. The earlier failed-request evidence and report versions remain
  preserved. A third sealed revision incorporated the successful process inventory;
  all six readiness/report/question/update jobs completed. The final case has
  exactly three analyzer runs: banners, Windows info, and PsList. Follow-up report
  revisions reused outputs instead of rescanning.

## Two focused review-and-repair cycles

Cycle 1 corrected interruption classification, a turn-start/Stop race, and
synchronous report packaging that could block browser responsiveness. Stop now
marks interrupted work incomplete, handles an accepted turn whose response is
still pending, and waits for outstanding packaging tasks. Packaging checks every
run's source identity against case readiness before combining evidence. Large
activity/message previews are explicitly truncated while private originals remain.
Regression checks covered source mismatch, bounded reads, and policy overrides.

Cycle 2 inspected actual saved run records, exposing the unsupported MCP form
approval rather than accepting a successful chat/report turn as proof that PsList
ran. The form handler now waits for an explicit decision and validates submitted
content. Unsupported forms fail closed. Failed MCP requests without a core run
are preserved as separate artifacts and investigation steps; they are not fabricated
as successful runs or attributed to a different plugin. Both focused regressions
passed and the repaired approval was exercised through the browser/agent/MCP
path. No third review cycle was performed.

## Limits

No independent proof of analytical correctness, complete symbol/plugin coverage,
or malware attribution is claimed. Report content and classification require human
review. Native selection interaction, other host platforms/clients/browsers,
complex/URL/device approval flows, long-running resource exhaustion, and forced
process-death recovery remain limited or unverified. SIGKILL cannot guarantee child
cleanup. Core hashing/conversion can delay cancellation; disk output has no quota.
The app-server/dynamic-tool API is experimental and may change in later Codex builds.
The UI is local-only, not a multi-user service or security sandbox. Model excerpts
may leave the machine through the configured AI service.

## Scoped analysis preauthorization follow-up

Workbench now sets the documented MCP `default_tools_approval_mode = "approve"`
for its case-scoped Volatility server on both thread start and resume. Global
Codex configuration, the read-only sandbox, and disabled shell tools are unchanged.
A regression test checks both new and resumed thread configuration.

The installed Codex 0.160.0 app-server completed a real authenticated turn through
the Workbench and scoped MCP server: a harmless simulated Volatility `run_plugin`
call completed, saved one analysis run, preserved the fixture, and raised zero
approval prompts. This checks the real agent/MCP approval path, not the accuracy
of memory analysis. No private memory image was analyzed. The 18 UI checks passed;
the HTTP check required permission to bind localhost outside the restricted test
sandbox. Tests also exposed an unclosed activity-log reader, repaired with a
context manager. Restart Workbench to apply the policy to loaded case threads.

## Stale running instance follow-up

The reported repeat approval prompts came from a Workbench backend started before
scoped tool preauthorization was committed. Reopening the launcher had reused that
backend; installing new source did not replace code already loaded in memory.
The affected process was gracefully restarted, preserving completed artifacts and
marking its paused request incomplete. The replacement session's application-code
fingerprint matched the installed code.

The launcher now rejects reopening an instance with a stale or absent code
fingerprint and explains how to restart it. Regression checks cover matching,
stale, and legacy fingerprints and exercise the locked-instance launch path to
verify that it does not reopen the browser. All 20 UI checks passed. A real
Codex-to-scoped-MCP turn using the harmless simulated analyzer completed with one
saved run, zero approval prompts, and unchanged source bytes. No private image
was reanalyzed for this verification.

## Readable UTC timestamps

New execution/state timestamps use `YYYY-MM-DD HH:MM:SSZ`. New run/report and
registration-backup directories use `YYYY-MM-DD_HH-MM-SSZ` plus a random suffix.
Tests cover same-second name uniqueness, provenance timestamp parsing, old and
new GUI formats, elapsed-time parsing, and unchanged non-UTC strings. The full
suite ran 71 tests successfully with one optional test skipped. The isolated
symbol-cache helper's CLI was also checked after preserving its standalone import
behavior. No memory analysis was rerun.

A read-only Chrome check against existing private case data verified three report
version labels, 76 evidence labels, and an original evidence link, with no browser
console errors. Initial browser harness waits assumed a disconnected Codex label;
correcting the harness to wait for the loaded case resolved that test-only issue.
The running investigation finished before Workbench was restarted. Existing raw
artifacts, sealed bundles, paths and hashes were not migrated or rewritten.

## U.S. Central display with Zulu reference

The GUI now formats timestamps through `Intl.DateTimeFormat` with the explicit
`America/Chicago` zone, independent of the browser's local timezone. Labels use
the Central calendar date, CST/CDT, and the original UTC clock in parentheses.
UTC metadata, raw artifact content, filenames, and actual link targets stay intact.
The two focused timestamp tests passed, including summer/winter, both 2026 DST
boundaries, midnight, year/date rollover, legacy labels, and elapsed-time parsing.
A live read-only Chrome check verified three report labels, 76 evidence labels,
and an original evidence link without console errors. An active investigation
was left running; refreshing the browser loads the updated static JavaScript.

## Stable per-image decorative coins

The prior private report assets were located and visually inspected: antique
silver concentric rims, graphite metal, emerald circuitry, curved lettering,
and distinct worm/gear and lightning/chip centers. Their original PNG bytes were
reused for their saved image identities; no private artwork or hashes are tracked.
A synthetic SVG companion was rendered and visually inspected against that design
vocabulary. It is a stylized local renderer, not a new image-generation service.

Four focused coin tests and 21 Workbench tests passed. Checks covered stable assets
across cases/reopening, distinct images, escaped labels, symlink rejection,
metadata-only generation with subprocess creation forbidden and nonexistent source
images, authenticated image serving, portable Markdown asset links and checksums,
unchanged prior report revisions, and report completion when artwork fails.
A test fixture initially used the platform's symlinked temporary-directory alias;
resolving that fixture path preserved the production symlink boundary.

Read-only Chrome checks verified both original PNGs byte-for-byte in image and
report areas, successful reopening, and no console errors. A browser-only synthetic
two-image case verified two identity coins and two portable report image links.
The existing incomplete report remained incomplete; its viewer can display the
coin without inventing report content. Eleven historical report/artwork/checksum
markers were unchanged. The standalone core import did not load the UI/coin layer.
No real Volatility analysis or source-image hashing was performed for this feature.
The active user investigation was allowed to finish before reloading Workbench.

## Coin enlargement interaction

A read-only Chrome interaction check verified that clicking a coin opens a larger
image, left-clicking either the image or backdrop dismisses it, right-clicking
keeps it open, and Enter/Escape provide keyboard access. The normal browser
context menu remains available for saving the image; no custom download handler
was added. JavaScript syntax passed and no browser console errors occurred.
No test suite, analysis jobs, or report regeneration ran for this UI change.

## Saved-artifact inspector integration

The case-scoped MCP server now exposes seven tools including `inspect_artifact`;
readiness's expected tool inventory and new/resumed case guidance were updated.
All 21 existing Workbench tests passed, and an additional inspection test packages
and seals a synthetic revision with derived inspection runs, source-artifact links,
and checksums under the existing report schema. The scoped MCP transport was tested
directly with real tool discovery/calls; no generic shell capability was enabled.
See [VALIDATION.md](VALIDATION.md#saved-artifact-inspection-and-regex-repair) for
actual saved-evidence verification and parser limitations.

The idle local Workbench was restarted through its existing desktop launcher after
checking that no jobs were active or queued. Its runtime fingerprint matched the
updated code, and an authenticated read-only HTTP request retrieved the private
inspection supplement. Case IDs, conversation IDs, report records and job count
were preserved. No new job or model turn was submitted; this was an HTTP integration
check, not a new browser interaction test or report-generation run.


## Saved citation viewer — 2026-10-06

Installed Chrome, using existing Playwright tooling and a synthetic local fixture
server, passed citation listing, exact resolved value/status, raw evidence opening,
inline `#citation=F1:0` links and refresh without JS errors. The fixture created no
Workbench jobs or Volatility subprocesses. Core query/value/provenance checks and
legacy compatibility are recorded in [VALIDATION.md](VALIDATION.md). Active private
Workbench sessions were not restarted; live model behavior was not re-evaluated.


## Coverage view — 2026-10-06

Actual Chrome on an isolated synthetic Workbench passed the Coverage tab's declared
scope/unknown question status, not-run planned filter, attempt drill-down and refresh.
The existing citation/report/evidence controls also passed. No jobs or Volatility
subprocesses were submitted by these views. Real private cases were checked separately
through read-only scoped MCP with subprocess/image-hash guards; the active Workbench
was not restarted. See VALIDATION.md for the 78 targeted tests and offline scenarios.

## Initial case selection — 2026-10-06

Installed Chrome with the actual static UI and intercepted synthetic API responses
passed fresh newest-first selection, selected ID/card/details/chat/report agreement,
and manual selection across the actual background refresh when a newer case arrived.
Valid `?case=` links survived launch-token cleanup; stale IDs fell back to the first
displayed case. Empty lists, removal of the selected case, and later list population
also passed. Switching to a case without reports cleared the old report, and a
delayed response from a previously selected case did not overwrite the current one.
No browser errors occurred. JavaScript syntax and both existing timestamp tests
passed. These were browser fixture checks, not a live backend/investigation test;
no analysis/report-generation requests were made, private cases were untouched,
and no running Workbench was restarted.

## Report coverage sealing regression — 2026-10-06

The automatic report-sealing path now supplies the same case-scoped coverage
backend and recorded jobs as the report-save tool. Previously it replaced the
saved coverage with an unavailable-adapter snapshot; a report retaining real gaps
then failed its mechanical-limitations validation. Sealing also synchronizes that
generated block if the saved snapshot changes before sealing. Authored findings
and all existing evidence/report checks remain subject to validation.

Six focused fixture tests passed: full simulated Workbench save/seal with failed,
partial results; ordinary report generation; follow-up revision and historical
bundle immutability; changed-evidence rejection; nonfatal artwork failure; and
snapshot changes between save and seal. The failed/partial regression blocked
subprocess launches during report save/seal and observed zero calls; the saved
coverage regression also used the existing offline subprocess guard. Setup used
the harmless fake analyzer and simulated Codex, not a real memory investigation.
No private report bundle was rewritten and no active Workbench was restarted.

Reproduce the focused regressions with:

```sh
PYTHONPATH=tests .venv/bin/python -m unittest \
  test_ui.UITests.test_report_seals_with_failed_partial_coverage \
  test_ui.UITests.test_stage_a_readiness_report_evidence \
  test_ui.UITests.test_stage_b_continuity_and_immutable_revision \
  test_ui.UITests.test_report_failure_and_changed_evidence_not_complete \
  test_ui.UITests.test_coin_failure_does_not_block_report \
  test_coverage.CoverageTests.test_saved_report_coverage_zero_analysis -q
```

## Pypykatz failure diagnosis — 2026-10-06

The installed third-party plugin was already reachable through Workbench; its
recorded failure was `LSA signature not found!`, followed by `Template guessing
is not applicable for NT5`. A bounded, read-only diagnostic used already-recorded
kernel/process/module metadata to compare the Volatility scanner with direct
page reads inside the affected LSASRV module. Neither found the signature, and
many pages were unreadable. This did not decrypt credentials, dump a process,
scan the whole image, or run the investigation again. The diagnostic and exact
addresses remain private. Missing pages versus an unsupported binary layout is
not fully resolved; credential recovery on that image remains blocked.

The backend now labels that specific failure and supplies actionable guidance;
Workbench investigator instructions discourage unchanged retries. Historical raw
failures are preserved, not relabeled as clean or successful. This is improved
failure handling, not a claim to have repaired missing memory or the upstream
credential parser. The synthetic backend regression checks the saved reason,
failed/nonempty-negative distinction, no reuse, historical response handling
without manifest edits, and no misclassification for unrelated plugins.

The eight-test combined run passed: the six report checks above, the pypykatz
backend regression, and the existing real stdio test in both protocol modes using
the fake analyzer. Fresh connections to both existing Workbench case-scoped MCP
servers discovered the installed plugin and its compatibility guidance without
analysis calls or import failures. These checks do not establish successful
credential extraction or evaluate live-model behavior.

After confirming no active or queued jobs, the local Workbench was gracefully
reloaded and its authenticated state endpoint verified against the updated runtime
fingerprint. Case/image identities, conversations, report records and job statuses
were preserved; 12 historical report/manifest/checksum files retained their hashes.
The browser was reopened with the new local session. No new analysis job or model
turn was submitted, and the earlier failed draft remains preserved as a failed draft.

## Administrative relocation fixture checks

`PYTHONPATH=tests .venv/bin/python -m unittest test_relocation -q` passed three
checks using a physically moved harmless fixture tree and a registered old-root
alias. Saved queries, observable-value citations, history, raw reads, and namespace
identity survived; original manifest bytes remained unchanged. Physical-path inputs
and configuration returned the old logical identity. Inner symlinks, traversal,
invalid mappings, and a retargeted administrative alias were rejected. The saved
query/history check asserted zero subprocess launches. These are local fixture
checks, not an investigation or a claim of unrestricted symlink support.

## Independent Workbench package — 2026-10-07

Extracted from core commit `3ecc22e1275467879005556f5340fbc863bc3281` and tested
against pinned core `376d338494465df402338db9360b48e9e11a7bfc` (0.1.0, API revision 1).
The moved timestamp harness was fixed to evaluate its formatter without executing
DOM-dependent theme startup. All 34 Workbench tests passed, including app/jobs,
report revisions/immutability, inspection provenance, saved citations, coverage,
coins, packaged assets, incompatible-core errors, and updater selection/generation.

`python scripts/package_smoke.py` built a wheel from fresh declared source files,
created an isolated environment, and installed that wheel with its declared core
Git dependency and locked runtime versions. From outside both checkouts it verified
packaged JS/CSS/HTML/template/contract resources, ten tools in both MCP protocol
modes, authenticated HTTP views and console help. The same 34 tests passed against
the installed wheel. A subprocess guard observed zero analysis/model processes for
application startup and viewing. Local editable imports resolved to the sibling
MCP source and this Workbench source; no PYTHONPATH override was used.

The existing Desktop launcher was backed up, updated, and executed from outside
both repositories after the previous Workbench was confirmed idle. It reopened the
same two cases, five report records and 50 jobs. An in-app browser verified newest
case first/initial selection, manual case switching across background refresh,
three historical sealed versions in the older case, original coin loading and zoom,
saved Info evidence-link navigation, case conversation messages and retained failed
job display. Reopening selected the newest case; no browser JavaScript errors were
reported. No readiness/report/question action was submitted.

A read-only saved-data guard inspected 49 history entries and validated existing
sealed bundles with zero subprocess launches. Thirteen historical report, manifest
and checksum markers retained their hashes. No memory-image analysis, re-extraction,
source-image hash, report regeneration or provider change was performed. Existing
configuration, conversation IDs, report identities and the administrative relocation
alias remain in place.

Updater unit fixtures exercised stable-series selection, draft/prerelease rejection,
immutable pin/lock generation, incompatible-series rejection, duplicate-version
no-op and an inert dry run. The live public release lookup found the current tested
core release and made no changes. Candidate PR generation is tested with fixtures;
no fake core release was published merely to manufacture an update PR.

GitHub's Workbench compatibility workflow passed on Python 3.12 and 3.13 after
publication, including installed-wheel tests. Core's separate CI also passed.
The actual manual `Update core` run succeeded as a no-change run against the public
core release. Repository workflow defaults remain read-only; the updater job alone
requests contents/pull-request write access, and the repository permits token-created
PRs. No PAT or additional secret was created. See the
[compatibility run](https://github.com/NoCoolUserName/volatility-workbench/actions/runs/37589967237)
and [manual updater run](https://github.com/NoCoolUserName/volatility-workbench/actions/runs/37590071999).
The moved presentation template's contract link was corrected and the two installed
resource/compatibility checks passed after that documentation-only repair.


## macOS launcher and icon follow-up — 2026-10-07

Browser opening now uses macOS Launch Services through `/usr/bin/open`, avoiding
Python's AppleScript browser automation. Both cold start and reopening use the same
helper. Failure or timeout prints an explicit fallback message without repeating
the private capability in error diagnostics, and the HTTP server remains available.
Other platforms retain Python's standard browser support.

All 37 application tests passed from the editable checkout and from an isolated
wheel installation outside either checkout. Package smoke checks include the PNG
icon's HTTP route. Browser helper tests cover macOS dispatch, failure, timeout and
other-platform fallback; the stale-instance test still prevents browser reopening.

The actual local Desktop command was simplified to call the package CLI, retaining
the existing config, relocation and state roots. With the server confirmed idle,
the command was executed from outside the checkout. Cold start and a second launch
succeeded without browser errors, and the second launch reused the running server.
The native Vivaldi window was visually checked at the new server address with saved
cases loaded. Full saved state compared equal before and after the restart.
No investigation or report-generation request was submitted.

A custom memory-chip/lens icon was drawn with the committed AppKit/Swift source,
packaged as the browser favicon, and installed on the existing Desktop command.
The native icon installer returned success, and Finder's custom-icon flag and
resource fork are present. Direct Finder window automation failed to attach, so
a Finder double-click itself was not tested; the actual Desktop script was tested
directly. No desktop application wrapper was added.

The Workbench checkout now has its GitHub `origin` and `main` upstream configured.
The earlier environment restriction on local Git configuration is resolved.

## Physical-root launcher correction — 2026-10-15

The symlink auto-repair added earlier was removed after the operator clarified
that the case root had moved physically and no alias was desired. With the
Workbench idle, private configuration, the Desktop command, two registered image
paths and two scoped MCP configurations were pointed at the physical root. A
backed-up, offline path-only migration updated 327 mutable run/inspection manifests;
historical argv, raw outputs, source images and sealed report bundles were not
rewritten. Inspection identity digests were updated to match the rebased run
manifests. This migration was local private maintenance, not a general installer.

A cold launch returned two existing cases and 50 prior jobs. The sealed report
reader returned its saved Markdown. Coverage returned saved attempts for both
images with no migration-related issues; one preexisting unsupported XP result
remained unparseable and was not treated as empty. The old path was absent before
and after launch. No Volatility command or investigation job was started.

## Installed-plugin catalog — October 17, 2026

- Full Python suite: 38 tests passed, including real authenticated catalog HTTP,
  explicit refresh, unchanged case-state bytes, and zero analysis/image-hashing/model calls.
- Chromium checks: global view with/without cases, case and tab preservation,
  state polling without rediscovery, search and OS/source filters, source links,
  literal untrusted descriptions, stale/empty inventories, and 390px mobile layout.
- Repeat the optional browser check with Playwright and Chromium available:
  `node scripts/check_plugins_browser.cjs`. The check intercepts every request and
  uses synthetic data; it requires no memory acquisition or model credentials.
  Playwright is a development-only tool, not an application dependency.
- Real Volatility 3 framework 2.28.2 discovery was separately exercised in core.
  This does not establish compatibility with any particular memory image.

## Community analyzer profile — 2026-10-17

- Core pin advanced to merged `e3a74a6e7861b66c6074510093d8b520f6657e16`
  with its runtime lock. The opt-in core installer owns source/dependency hashes,
  compatibility adaptations and notices; Workbench contains no plugin copy.
- The updated analyzer exposes 208 commands and zero import failures on the Mac.
  A real registered stdio MCP check queried all nine added command schemas and
  source labels. No analysis-tool calls, private-image scans or report generation.
- A disposable empty-case Workbench using the real analyzer was inspected in the
  browser: 208 rows, seven source checkbox labels, subset filtering, search and
  expanded Prefetch compatibility/provenance details. The actual plugin algorithms
  were not exercised by the UI check. Existing user case storage was not used.
- Found and repaired a same-version Git-pin upgrade defect: a plain pip install
  left an older 0.1.0 core wheel despite a changed commit pin. The explicit
  `scripts/install_core_pin.py` helper replaces only stale core code with no
  dependency changes, checks installed Git provenance, and is idempotent. A mocked
  regression covers stale revision replacement, a matching revision, and rejection
  of mismatched post-install provenance. README install/update commands include it.
- Workbench unit tests: 39 passed. Installed wheel/package integration passed.
  Core's separate community-profile CI job also passed on Linux Python 3.12 with
  pinned downloads and synthetic parser/API checks, not real memory images.
- PTE algorithms and real-image plugin support remain unvalidated. Two upstream
  source redistribution licenses remain unresolved; future public app/container
  bundling must resolve permission or retain explicit operator download.


## Registered evidence locations — 2026-10-18

Five new fixture checks pass for explicit images in different physical folders:
metadata-only Settings discovery/deduplication, persistence across reopening,
related captures with exact file allowlists, unavailable-folder display, rejection
of symlinks/traversal/output files, and actual stdio MCP discovery rejecting an
unselected sibling. The existing hashing routine also accepts the newly scoped
fixture image. Adding/viewing locations launches zero analyzer processes and does
not hash images; the MCP inventory and fingerprint check hash only tiny synthetic
fixtures. The unchanged default config bytes are checked explicitly.

All 97 application tests pass, including the isolated installed-wheel smoke check
outside the checkout with real SDK/HTTP interfaces. No real memory acquisition or
live model is used. The offline Chromium Settings check passes initial rendering,
2-second refresh, reload, deduplicated counts, safe text rendering and unchanged
default-folder controls. Its screenshot was visually inspected using synthetic
paths. The first browser attempts found a missing old temporary Playwright module
and a bundled-library/browser-cache version mismatch; the successful check used
the existing bundled library and cached Chromium via explicit environment paths,
without installing another browser.

Run the optional browser check with Playwright available in Node's module path:
`node scripts/check_settings_browser.cjs`. If using a separately cached Chromium,
set `WORKBENCH_BROWSER_EXECUTABLE` to its actual executable. This browser fixture
simulates settings data; the real scoped MCP tests exercise backend access limits.
Existing cases retain their saved roots and reports. No legacy manifest is rebased.


## Finder cancellation and remaining folder assumptions — 2026-10-18

Finder's normal AppleScript cancellation (`-128`) is caught at its source and
returned as an explicit cancelled selection. The empty-result newline emitted by
`osascript` is filtered; Cancel neither shows an error nor clears typed paths.
Genuine picker failure remains actionable, without displaying the raw interpreter
trace. Three picker fixtures cover cancellation, failure and successful external
image selection with retained symlink rejection. An actual AppleScript execution
raised `-128` in place of the dialog and passed its real stdout through the picker
handler successfully; no native dialog or evidence was opened by that check.

The single-folder audit found and repaired Finder's remaining default-only
validator and Browse folder's fixed root. Browsing now selects only the default
or an already registered image folder, keeps that root during child/parent
navigation, excludes case/global outputs, and rejects traversal, symlinks and
unregistered roots. It does not add files or widen scoped MCP access. Review
confirmed readiness/report hashing and saved queries/coverage/citations use saved
per-case scope; runtime/symbol changes retain case evidence roots. Standalone
configuration still keeps its deliberate default root.

The 101-test installed-wheel suite passed, followed by nine affected picker/location
checks after the newline refinement. Offline Chromium checks passed quiet Cancel,
preserved input, actionable real failure, external selection and registered-folder
navigation with zero case/job submissions. Tests use synthetic files/responses;
no real memory analysis or live model was launched. Run the optional browser check
with Playwright available: `node scripts/check_picker_browser.cjs`; an existing
Chromium may be selected through `WORKBENCH_BROWSER_EXECUTABLE`.

## Case header and release-readiness backlog — 2026-10-18

The case header now places the saved Ready status below the case title and shows
its recorded check time. The readiness job, not this badge, verifies image access,
SHA-256 and OS/symbol discovery at that time. The badge does not continuously
monitor an external drive. A saved legacy status without a check time is labeled
as unverified for current file access. The path and hash remain visible without
an enclosing panel or duplicate top coin; report coins and their zoom control
remain in the report viewer.

All 101 application tests and the isolated installed-wheel smoke check passed.
An offline Chromium fixture verified badge placement, unboxed evidence metadata,
absence of the header coin, retained report coin, and stable display after a
state refresh with zero analysis requests or JavaScript page errors. The
synthetic screenshot was visually inspected. No private image was opened or
hashed, and no live investigation/report generation was run. The prioritized
follow-up list and acceptance checks are in [ROADMAP.md](ROADMAP.md).

## Combined readiness control and header — 2026-10-18

The saved status and Check Readiness action now share one button under the case
title. Queued/running/stopping checks disable it and show the existing job's live
progress to its right. A successful check shows Ready with fixed green text and
outline in every theme; Ready with limitations keeps its full label and reasons.
Clicking a completed status explicitly requests another check. Failed checks
restore Check Readiness with Blocked and the existing failure reasons. The
saved timestamp still describes the last successful check, not live monitoring.
Theme now follows Plugins; only the application title is enlarged, and its
eyebrow reads Local Memory Forensics.

All 101 application tests and the isolated installed-wheel smoke check passed.
The offline Chromium fixture exercised two simulated readiness submissions,
queued/running progress, reload without duplicate submission, successful status,
explicit recheck, failure/retry display, limitations, green colors in all three
themes, header placement, mobile width and unchanged report coins/title size.
Its synthetic screenshot was inspected. The fixture uses intercepted loopback
requests so browser secure-context request IDs match the actual application.
No private-case readiness job, private-image hash, investigation or report generation was
started. Repeat with `node scripts/check_case_header_browser.cjs`, Playwright in
Node's module path and optionally `WORKBENCH_BROWSER_EXECUTABLE` for an existing
Chromium installation.

## Incomplete report hide/delete — 2026-10-18

Nine new backend checks use temporary synthetic bundles. They verify persistent
hiding without file changes; actual bundle removal with shared analysis, source
bytes, completed reports and history retained; idempotent retries; rejection of
completed/draft, wrong-case, active/queued and predecessor-linked revisions;
traversal, root/nested symlink, source overlap and completed/mismatched manifest
guards; malformed/missing incomplete bundles; partial I/O failure recording and
retry; duplicate/new-job exclusion during cleanup; and shutdown waiting for
cleanup. A real loopback HTTP check verifies authentication and Origin guards
before hiding/deleting harmless files. The full suite and isolated installed-wheel
smoke check pass 110 tests.

The offline Chromium check passes hover/keyboard removal controls, two explicit
choices, safe initial focus, dismissal without requests, hide/reload persistence,
selected-report fallback, deletion failure/retry and completed-card protection.
Newly completed revisions still display automatically when no older revision
has been explicitly selected.
Polling preserves the hovered card. Its synthetic popup screenshot was visually
inspected. The prior readiness/header browser regression also passes. These
checks invoke no private-case jobs or real memory analysis. Repeat the optional
browser workflow with `node scripts/check_report_cleanup_browser.cjs` and the
same Playwright/Chromium setup used for the header check.

Deletion is permanent within the selected bundle; failures can leave partially
removed files until an explicit retry. Case/job metadata and activity are audit
records, not deleted bundles. No actual user's report was hidden or deleted by
this verification, and no general filesystem cleanup or unhide UI is provided.

## Readiness placement and decimal MB labels — 2026-10-18

The offline browser checks place the saved check timestamp beside Ready, align
the silver Settings gear beneath Theme, and keep the title change limited to
the Workbench header. A synthetic 8,388,608-byte symbol pack displays as
8.39 MB. The existing header behavior and three themes remain covered by the
same browser fixture. The full Workbench suite and fresh-wheel package smoke
each passed 110 tests with the merged core pin; the package smoke exercised
ten MCP tools and launched zero analysis/model subprocesses. No private image
was rehashed or analyzed for these checks. The private case's incomplete
revision was inspected read-only; its files and status were not changed.

The first native build revealed that `core-dependency.json` still named the
previous core commit even though package metadata and the lock file had been
updated. No app was installed from that build. The release pin was corrected
and the builder now fails before downloads if these three sources disagree;
an offline regression checks both metadata and lock mismatches. The subsequent
native build and installer validation use the merged core commit.

## Report generation provenance and preamble — 2026-10-18

Focused checks use provider-shaped synthetic Codex notifications: effective
model/effort, repeated cumulative usage, report-turn deltas, missing baseline,
counter reset, malformed counters, case/turn isolation, reroutes, persistence,
missing usage after dispatch, and refusal to revise final metadata from late events.
The stage A/B fixtures verify metadata in sealed Markdown/manifests, one managed
coin per image despite copied duplicate badges, per-turn versus thread totals,
and unchanged prior sealed checksums. No live provider/model was invoked.

The existing failed/partial-coverage report regression passes: mechanical
limitations are refreshed at save and seal, with saved evidence and a subprocess
guard. It addresses the recorded limitations-block sealing failure without
weakening coverage validation. Other malformed reports can still fail validation.

`node scripts/check_report_metadata_browser.cjs` passes against offline synthetic
HTTP responses in local Chrome. It verifies actual assessment text (including a
different assessment and HTML-looking data) beneath the title, model/effort/token
display, historical unknowns, duplicate old-coin suppression, distinct-image coin
retention, and zero work submissions. A screenshot was inspected locally; none
contains private case data. The first assertion assumed inline-code rendering;
it was corrected to check the existing renderer's literal text rather than expand
Markdown behavior. The first local HTTP fixture needed local socket permission;
that one check passed when repeated with the required execution permission.

Development policy now uses focused checks while editing, then the full installed
application suite/package smoke before merge, avoiding a duplicate local full
checkout run when the smoke already executes all tests. CI still exercises the
supported Python versions and installed-package boundary. Simulated provider
contracts do not require additional model subscriptions and are not claims of
live model accuracy or cross-provider compatibility.

The final fresh-wheel smoke passed all 116 installed application tests, dependency
checks and ten-tool MCP discovery in both SDK modes. Its HTTP/assets guard observed
zero analysis/model subprocesses. No real images were opened for those checks.

## Explicit sealed-report Hide/Delete — 2026-10-18

The cleanup path now accepts registered incomplete and sealed revisions. Eleven
focused cleanup tests pass, including durable sealed hide without byte changes,
explicit sealed deletion of only its private bundle, idempotent retry, preserved
shared analysis/source fixtures/history, and active-job/reference/source-overlap
guards. An incomplete record still cannot authorize deleting a completed manifest.
Authentication, Origin, cross-case, traversal, symlink, malformed-draft and partial
I/O failure regressions remain covered. No actual private report was deleted.

The offline Chrome cleanup fixture passes incomplete/sealed hover and keyboard
controls, status-specific dialogs, dismissal, hide/reload/selection fallback,
delete/error/retry and sealed Hide/Delete. It submitted no analysis requests.
The existing one-time private narrative note is removed in a new presentation
revision with checksums/provenance; the sealed source and raw evidence are retained.
The proposed triage/targeted/compatibility-sweep modes in ROADMAP.md are design
intentions only, not implemented buttons or forensic evaluation results.

Final fresh-wheel validation passed all 118 installed application tests, dependency
checks, and ten-tool MCP discovery in both SDK modes. The smoke guard observed
zero analysis/model subprocesses; no private images were analyzed or rehashed.

## Selected report revision — 2026-10-18

The offline Chrome report fixture checks that the opened revision retains an accent
outline and `aria-current` on initial load, switches with a report click, stays
selected through state polling, and falls back to the remaining report after Hide.
It also exercises the existing sealed/incomplete cleanup controls. The fixture
contains only synthetic reports and issues no analysis requests.

The first fixture run exposed an automatic-selection regression: recording the
default latest report as a manual choice prevented a newly added revision from
opening on refresh. The selection marker now follows the displayed report while
manual choice state remains separate. The corrected Chrome fixture passes.
The final installed-wheel smoke passed all 118 application tests, ten MCP-tool
discovery in both SDK modes, HTTP/assets checks, and the zero analysis/model
subprocess guard. No private image was opened.

## Offline theme catalog and decimal units — 2026-10-18

The shared Workbench/Settings catalog has 31 choices, including 12 distinct released
Fallout games/table experiences, every other requested reference and the three
legacy preference IDs. Original local SVGs and a generated adult-Halloween raster
are isolated in a decorative band; forensic surfaces stay opaque. No runtime
external asset requests or new investigation-mode buttons were added. The verified
Punisher #53 attribution correction and official release sources are in THEMES.md.

The synthetic Chrome theme check loads every scene under the exact production CSP:
31 palettes passed primary/muted/control/selection/status/error text contrast of
at least 4.5:1 and control borders of at least 3:1, visible focus, selected-report
preservation, legacy reload preferences, shared Settings, a 390px viewport,
increased contrast and unavailable storage. The corrected final run made 196 local
GET requests with zero external requests, case/job mutations, page errors or CSP
violations. Original SVG art uses packaged same-origin files; embedded data URLs
were replaced during development because the existing policy forbids them. The
policy was retained unchanged. Screenshots of the seasonal, specific game/comic,
terminal and mobile variants were visually inspected using synthetic data.

Existing header, report-metadata, report-cleanup, Settings and plugin-catalog
browser regressions passed. The header check caught a readiness annotation whose
box top shifted 10.4px when controls became 40px tall; matching the annotation's
minimum height retained the original alignment and touch target. Its unchanged
regression and all-theme checks passed after that CSS-only fix. The catalog harness
also had a stale expectation of four rows after excluding one of four sources;
its failure-state assertion now correctly checks the retained three-row filter.
No plugin filtering implementation changed.

The final isolated installed-wheel smoke completed all 118 application tests,
dependency health, ten MCP tools in both protocol modes, HTTP startup and every
one of the 30 SVG routes plus the raster/script/styles. Its subprocess guard
observed zero analysis/model execution. The later CSS alignment change was checked
with the affected header/all-theme browser suites. Core PR #12's exact decimal
KB/MB metadata conversion is pinned at
`7f7cc1f0c4f4f6e6a17dfecca8c27db02e53c1d6`; binary arithmetic and byte bounds,
revision-4 hashes/policies, 214 configured commands and the public 200-command
baseline are unchanged. No private case, source image or saved report was used as
a fixture or modified by validation. Broader assistive-technology, OS/image
compatibility and forensic-accuracy limits remain those in ROADMAP.md.

CI's CodeQL gate then flagged the request-derived SVG filename even though it was
bounded by a filename pattern. The final route now builds its asset map entirely
from packaged filenames and only looks up request keys. A real authenticated HTTP
regression checks the valid scene and rejects missing/plain/encoded traversal
names. Security gates and CSP were not disabled or relaxed. The installed-wheel
smoke was repeated after this server-code repair and again passed all 118 tests,
dependency/protocol checks and every theme asset route with zero analysis/model
subprocesses.

## Fallout 2 CSS console skin — 2026-10-18

The supplied inventory-screen concept now guides Fallout 2's CSS metal housing,
rivets, ventilation rail, recessed dark screens, brass controls and green phosphor
accents. The housing scales through CSS gradients, borders and shadows without
loading the reference screenshot. Evidence and report text remains on opaque,
untextured surfaces. Primary Update report stays green; danger and focus indicators
retain their separate meanings. The overrides are scoped to Fallout 2.

The expanded offline theme browser check passed all 31 palettes, the existing
4.5:1 text and 3:1 control-border token checks, actual green-primary gradient text
contrast, report selection, keyboard focus, legacy preference reloads, and shared
Settings. It verifies that switching back to Matrix, Fallout and Fallout 3 restores
their presentation, and that Fallout 2 uses CSS surfaces with a compact rail.
Desktop layouts, reports at 320px and 390px, plugins at 390px and Settings at 320px
were checked for page overflow, with explicit title/Settings overlap checks. The final run made 235 local
GET requests, with no analysis, case/job mutations, external requests, page errors
or CSP violations. Desktop, narrow-screen, Settings and expanded-console captures
were visually reviewed using synthetic fixtures stored outside the repository.

The affected report-plugin and case-header browser regressions passed, covering
bulk and failed-plugin actions, persistent acknowledgments, selection, readiness
and header alignment. The live/saved-console check now includes Fallout 2 at
desktop, 2560px and 390px widths; it passed actual console text contrast, modal
focus, follow/pause/collapse, saved output reload and case isolation with zero work
requests. Its heading-state assertion reads text content so the skin's uppercase
presentation does not alter the expected application state. Mobile review caught
and resolved a theme-dropdown overflow and a Settings/eyebrow overlap before the
final checks. No real investigation, evidence or saved report was used.

A final decorative refinement added restrained edge oxidation, tarnished screw
heads and small brass vent collars. The theme and live/saved-console checks were
rerun successfully; the theme check made 233 local GET requests with no external,
analysis or mutation requests. Desktop, 320px report and 390px CRT captures were
reviewed again. Decoration remains on the housing, with clean text surfaces and
unchanged geometry and controls.

The expanded CRT now mirrors the live job's amber operation/elapsed label beside
the case title. The focused synthetic console browser check passed exact text and
color matching, a deterministic 162-to-167-second update, stopping status, desktop
placement, mobile wrapping, expand/collapse, and clearing after job, case-stream or
completion changes. Missing or mismatched jobs and saved consoles retain no stale
label. Matrix and Fallout 2 desktop/mobile captures were visually reviewed. The
check made no work or external requests and did not inspect active investigations.

## Interactive VolShell and New Vegas sign console — 2026-10-18

The installed-wheel package smoke passed all 199 application tests, dependency
checks and packaged asset routes. VolShell lifecycle tests use temporary synthetic
captures and a toy interpreter: exact session/case binding, authenticated routes,
persistent variables, multiline input, interrupts, startup failure/timeouts, output
bounds, prompt-spoof resistance and descendant cleanup. A separate smoke launched
the configured official Volatility 3 2.28.2 Volshell against a fresh 64 KiB zero
fixture in generic mode and verified an interactive arithmetic command. No private
capture or live model was used. OS-specific forensic accuracy is not established
by this smoke; symbol availability and upstream support still apply.

The three-mode browser check passed manual Tab completion versus Enter execution,
plain-text output, inert AI drafts including clarification/empty responses, stale
session rejection, explicit AI investigation, pending approval navigation, paused
manual input, resume and Stop. Live/saved console, case header, picker, plugin
catalog, report cleanup/determinations/metadata/plugins/return/running and Settings
browser regressions also passed with synthetic fixtures.

New Vegas uses scalable CSS neon letter discs, a star, aged sign trim and perimeter
bulbs with fixed dark sockets. Its decoration stays outside the text surface. Each
of the 31 palettes has a distinct VolShell bezel treatment; the rectangular LED
continues to indicate actual session readiness. Desktop, 390px and 320px visual
review caught and corrected a narrow Mode selector overflow. No flashing or
animation is used for the decorative failed bulbs.

Final theme checks passed all 31 palettes, Settings/mobile layout and CSP. The
VolShell bezel audit measured minimum text contrast of 5.07:1 and verified distinct
styles, keyboard focus and the ready LED. The existing live-console check also
passed New Vegas with actual output at desktop and 320px widths.

### AI-selected helpers and incremental terminal delivery

The case MCP server exposes the separate `case_volshell` helper transport to both
providers, including resumed Codex conversations. Fifteen synthetic controller
checks cover the closed helper schema, literal quoting, active job/image binding,
manual-session separation, exact question approvals, automatic report scope,
errors/timeouts, Stop and job cleanup, and saved-observation confinement. A real
MCP transport test returns a synthetic observed PID and feeds it into the next
plugin call. Observations retain their exploratory classification and are never
counted as validated core runs. A separate official Volatility 3 2.28.2 smoke used
only a newly created 64 KiB zero fixture and verified the bounded `db` helper and
its saved observation.

Nineteen session/HTTP tests include a gated no-newline write and split UTF-8
sequence visible before command completion, through both the pipe reader and
authenticated SSE. Case filtering, reconnect snapshots, terminal status, stream
capacity and immediate closed-connection reuse are covered. Bridge checks cover
case-specific capabilities, Origin, redirects, exact-request cancellation and
cancellation/start races. No credentials or case content are sent to a remote
service by these tests.

The browser stream check disables normal polling and verifies partial fragments,
stale-case/source rejection, stale-poll protection, reconnect fallback, scroll
retention, AI readiness LED, same-case expanded-only activity switching and
approval access without a manual session. New Vegas at 320px and Fallout 2 at
desktop/390px were visually reviewed again. The existing live-console and all-theme
checks passed with explicit offline stream substitutes.

The final installed-wheel smoke passed all **222 tests**, dependency checks and
packaged routes. Four MCP bridge tests include redirect rejection, exact-request
cancellation and pre-cancel/replay rejection. Closed streams release slots within
the focused one-second bound; permanently closed EventSource connections retry at
1/2/4/8/15-second capped intervals while polling remains available. The seven
HTTP/SSE tests also passed with ResourceWarning promoted to an error.

## Shared appearance preferences and automatic PasswordManager policy — 18 October 2026

Theme choices now live in the application preferences directory, outside cases and
installed assets. Ten backend tests cover validation, atomic persistence, migration,
invalid/symlink paths and shared-preference locking. Three independent processes
with different state roots produced 24 unique consecutive revisions under forced
save overlap. The synthetic UI fixture covers changing server ports, fresh browser
storage, main/Settings synchronization, late responses, rapid choices, stale storage
events and a real Retry save button click after a failed write.

The combined 31-theme fixture passed text/control contrast, theme isolation,
320px/390px layouts and Settings checks, including the full-app New Vegas marquee
and cream/rust housing. Its requests were intercepted synthetic local reads; no
analysis, external requests or private evidence were used.

Core 88f06e2 permits relevant automatic PasswordManager collection with an explicit
browser PID and existing offline limits. Workbench's exact-name exemption requires
explicit manual_only=false metadata; unknown/older metadata and SSHKeys remain
gated. Focused tests passed through both supported MCP protocol modes. The staged
analyzer retained the exact 237-command set with zero import failures and all 46
addon files matching inventory hashes. These checks establish policy and packaging
behavior, not real-image accuracy across OS/builds.

The VolShell bezel is now a direct connection toggle for the selected case's
manual session, including when returning from Output. Its synthetic UI regression
passed delayed and failed shutdown, busy commands, duplicate clicks, stale ready
and empty stream frames, terminal confirmation and cross-case fallback checks.
Commands and disconnecting retain the green connection light; only a confirmed
terminal state turns it off. Input stays disabled during shutdown, and stale
poll/stream updates cannot resurrect a confirmed closed session. AI investigation
guards remain in place. No live interpreter or evidence was used by this check.

## Fallout 3 terminal variants and history order — 2026-10-20

Added Fallout 3 (RobCo Night) and Fallout 3 (Vault 112) using the supplied terminal
references. Both use CSS chassis, screen recesses, vents and control plates across
Workbench, Settings and Output/VolShell. The catalog has 33 themes and 14 Fallout
choices. Original Fallout 3, Fallout 2, New Vegas and classic styles passed isolation
checks. Screenshot review covered both terminals at desktop and 320px widths;
the theme fixture also passed 390px, 200% text and contrast checks.

The title dot and main/console text-size control strips were removed. Gesture
scaling remains functional and Settings retains its text-size controls. The Report
console disclosure arrow now uses the heading's font size. Conversation and activity
have independent per-case oldest/newest preferences saved in case metadata; sorting
never rewrites their recorded entries.

Thirteen focused Python tests passed, including durable theme and history choices
and save-failure rollback. Nine browser scripts passed: themes, VolShell, case
header, history order, live console, running reports, report plugins, theme
persistence, and Settings. These checks use intercepted synthetic requests and no
private evidence, live interpreter or real investigation. Native installation and
physical trackpad gestures were not exercised for this batch.


## Malicious AI Executive summary presentation — 2026-10-31

Exact author-selected supporting excerpts are rendered red only when the AI
verdict is Malicious. Validation rejects invented, out-of-summary and label
quotes, invalid types and supporting excerpts for other verdicts. Unannotated
legacy prose remains normal rather than receiving a keyword-based classification.
Mixed-paragraph browser checks cover red rationale beside ordinary timestamps
and filenames (including a filename containing “Malicious”), overlapping excerpts,
formatted text and working finding/evidence links, report switching and independent
human opinions. This is presentation metadata, not a new evidentiary conclusion.

The final isolated fresh-wheel smoke passed **273 application tests**, dependency
checks, installed assets/HTTP routes, and ten-tool MCP discovery in both modes.
All six PR checks passed on application source `4120e7097d0d3421c5bfe15707a546929fd70d3f`:
Python 3.12/3.13 compatibility, the complete synthetic browser job, quality,
security/SAST and native Adventure gameplay. Native bundle validation passed:
four starter symbol packs, zero first-run symbol downloads, 203 discovered
plugins with no import failures, MCP/catalog and synthetic analyzer checks,
strict signing and system-or-bundle-relative native linkage. No private image
was opened by these checks. Build-size measurements identify this same revision.

## Benign AI Executive summary presentation — 2026-10-31

Benign uses the same exact-excerpt validation and text-node highlighting path as
Malicious, with independent green presentation metadata. The synthetic browser
check passed for green supporting prose, formatting and finding/evidence links
within a paragraph whose timestamp and unrelated Benign.exe filename keep their
normal text color. It also covers overlapping excerpts, excluded limitations,
out-of-summary quotes, opposite-verdict metadata, finding navigation, reload and
no highlight leakage into Undetermined. Existing maliciousness and human-choice
regressions passed. A Chromium screenshot was visually reviewed.

The report-author prompt requires affirmative supported Benign rationale; absence
of observed indicators alone does not qualify. No visible saved Benign reports
were present to annotate. Existing private reports and maliciousness annotations
are preserved. Risk review found no change to verdict calculation, evidence,
collection authorization, permissions or publication.
