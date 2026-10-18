# Optional local Workbench — experimental

This repository owns the optional Workbench application, available in browser mode
and the native macOS shell. The standalone MCP server and authoritative report
contract remain in the separate volatility-mcp project. Desktop dependencies do
not become core MCP dependencies. Codex is the default AI adapter and uses an
existing local CLI/login; the optional compatible chat API adapter is configured
explicitly in Settings. Saved cases, Settings and plugin discovery work without
an AI connection. See [AI connections](AI_PROVIDERS.md) for endpoint checks,
credential handling and tested limits.

## Appearance

The header's Theme selector and Settings → Appearance offer the same 31 local
skins, including 12 separate Fallout choices. New profiles start with the
original Matrix green appearance; the three original preference values remain
supported. Selection persists in browser/WebView local storage, and open
same-origin tabs synchronize.
Artwork stays in a decorative band outside opaque evidence/report surfaces.
Theme changes do not submit jobs or modify cases, conversations or saved reports.
The displayed report retains its selection stripe. See [the catalog and verified
references](THEMES.md), including the Punisher #53 artist correction.

## Launch

From the repository, using the existing configured environment:

```sh
.venv/bin/volatility-workbench --config /absolute/path/to/config.json
```

This binds an available port on `127.0.0.1` and opens the local browser. Keep the
Terminal process running. Ctrl-C stops work and exits. `--no-open` prints the
private launch URL without opening a browser; `--port 8765` requests a fixed port.
Treat the launch URL as a local access credential; do not share it or put it in
issues. Repeating the launch command for the same state directory opens the
existing application instead of starting another queue.

Default private storage is `<configured output_root>/workbench`. To use another
private output directory outside the repository, add:

```sh
--state-dir /absolute/path/to/private/workbench
```

The chosen directory is the UI's configured case output root. Keep the same
argument on later launches to reopen those cases. Do not put UI state under Git.
Source images remain at their selected physical locations. The configured evidence
root is the default for relative paths and browsing. Each case scopes MCP to its
explicitly registered files; output roots must never contain selected source evidence.
No migration or rewrite of previous reports is performed.
Use the physical location in both `--config` and `--state-dir`. Moving a case
root requires an offline, backed-up rebase of mutable saved paths; changing only
the launcher path does not repair old absolute references inside run manifests.
The launcher never creates a symlink or other filesystem alias.

A fresh clone follows the existing MCP setup first. Install the project normally
or with the optional separate Workbench distribution. The
`volatility-workbench` console command is available after package installation;
the module command above also works with an existing editable installation.

## Workflow

The Cases list displays newest first by case creation time. A fresh page selects
the first displayed case unless a valid `?case=<case-id>` URL requests another.
Background refreshes preserve the selected case, including a manual selection.
If the selected/requested case no longer exists, selection falls back to the
first displayed case; an empty list shows the start screen.
The **Add evidence** panel starts collapsed; click its heading to expand it.
The **Theme** button sits directly below Plugins. Click it to show the theme
dropdown, and click it again or press Escape to hide it. Settings, with its silver
gear, sits at the upper-right corner. The themes include Matrix green (default),
Soft black and white, and Light blue. The selection is stored in this browser's local
storage and restored on reload. It changes presentation only; case state,
saved evidence, and reports are unaffected.

1. Add existing `.raw`, `.mem`, `.vmem`, `.dmp`, `.lime`, or `.dd` files through
   path entry, evidence-folder browsing, or **Choose in Finder** on macOS. The
   native helper returns filesystem paths; the browser does not upload files.
   Absolute selections can use different physical folders. Relative paths use the
   default evidence root. Folder browsing starts there; its folder selector can
   switch to any registered image folder. Selected files cannot be symlinks
   or application outputs. Their parent folders appear automatically under
   Settings → Evidence locations. Finder Cancel is a quiet no-op that preserves
   typed paths; actual chooser failures offer path entry/folder browsing. No automatic
   copying or folder scan occurs.
2. Unrelated images become separate cases. Check **related captures** only when
   intentionally grouping them. Each capture keeps its own evidence ID, hash,
   discovery result, run associations, and report provenance. New cases get a
   dedicated conversation; the UI never controls an unrelated open Codex session.
3. **Check Readiness**, below the case title, checks the case's selected provider (existing Codex account
   or a previously checked compatible endpoint), initializes the ten actual scoped MCP tools, discovers plugins, hashes each image with byte progress,
   and runs OS/symbol discovery through MCP. **Ready** means ready to attempt
   analysis. **Ready with limitations** records discovery/import/compatibility
   gaps. **Blocked** records authentication, tool, file, or integrity errors that
   prevent readiness. This single control displays queued/checking status and
   live progress to its right, then the **saved result of the last check**, with
   its check time to the right of the Ready control. Successful Ready states have
   green text and outline in every theme; limitations retain their label and
   reasons. Clicking it again explicitly starts a new check. It is disabled
   while a check is pending and does not continuously monitor whether a drive
   is still connected. Blocked checks show **Check Readiness** again with their
   failure reasons. None is a
   malware verdict or guarantee every plugin works.
4. **Generate report** starts an adaptive investigation, optionally narrowed by
   your focus. The report must follow `the installed core report contract`. The agent records
   important runs and saves Markdown/findings/IOCs; the application packages actual
   execution metadata and exact artifacts, validates provenance, rehashes source
   evidence, and seals a new version. A failed or incomplete draft stays visibly
   incomplete. Structural validation does not validate the analyst's conclusions.
5. View reports with their section navigation and evidence links. Raw outputs,
   readable text views, JSON/JSONL, activity, failures, current operation and elapsed
   time are accessible in the other tabs. Large files are read in bounded chunks;
   complete originals remain on disk. Recovered HTML is never executed.
   The report viewer loads the complete saved report in bounded chunks. Pipe-formatted
   Markdown tables in Scope and evidence and Technical findings
   display as grouped **Label:** value lines. Dense run/call lists display as
   actual tables without visible pipe syntax. This presentation does not
   rewrite a sealed report or its checksums.
   The report's actual assessment wording moves from its metadata preamble directly
   beneath its title in the viewer; it is not a fixed readiness/verdict label.
   Report preparation metadata shows the recorded model, reasoning effort and
   generation-turn token usage where reported. Historical unknowns and case-total
   versus report-only counts are labeled explicitly. The canonical new Markdown
   and manifest retain portable generation provenance; old bundles are not rewritten.
   See [AI connections](AI_PROVIDERS.md) for counter scope and limitations.
   Duplicate managed coin links copied from an older narrative are suppressed by
   the viewer; the packager normalizes managed badges on new saves, retaining
   distinct image coins and leaving other report images intact.
   Incomplete and sealed report cards reveal **×** on hover or keyboard focus (always visible
   on touch devices). Its popup offers **Hide from UI**, which persistently hides
   the revision without changing files, or **Delete**, which permanently removes
   only that revision's `reports/<revision>/` bundle, including its copied
   artifacts and decorative assets. Shared analysis, original images, case/job
   history, other revisions and independently saved exports are retained. Hidden
   files remain accessible in Evidence; there is currently no unhide control.
   Deleting a selected sealed revision also removes that revision's sealed bundle.
   Delete is blocked while
   the case has active/queued work or another revision names it as its predecessor.
   A failed/partial deletion is recorded and can be retried; it is not rolled
   back or silently marked successful. Closing the popup performs no action.
   The report revision currently displayed has a persistent accent outline and
   `aria-current` marker. This selection survives background refresh; after a
   selected revision is hidden or deleted, the remaining latest revision is shown.
6. **Ask / investigate further** resumes the same case conversation. It may run
   more MCP queries, but does not rewrite reports. **Update report** explicitly
   creates a new revision with a link to the previous version and preserved stable
   evidence IDs. Each update explicitly instructs the investigator to read the
   previous sealed report, reassess its Executive summary and AI Determination,
   and incorporate pertinent new findings, confidence changes, contradictions and
   material limitations. If the new results leave the assessment unchanged, the
   summary should say why. This is an investigative instruction; mechanical
   report validation does not independently judge the relevance of a finding.
   Sealed content is not edited in place; explicit Hide/Delete is
   separate from report generation and retains the case's audit metadata.
7. Multiple cases/jobs run sequentially. Refreshing/reopening the browser reads
   existing state and cannot start a scan. **Stop all work** interrupts the active
   turn/readiness operation and cancels all queued follow-on work. It sits below
   the connection status and is disabled when no work is queued or running.
   The **Current work** panel appears only while jobs are queued, running, or
   stopping; completed and failed job history remains in the case's Activity tab.
   During report generation/update, a **Live investigation console** shows actual
   tool starts, progress notifications and returned text as they arrive through
   the provider connection. This read-only terminal-style panel uses the theme's
   background and accent color. It has no shell or input forwarding. Tool output
   arrives only when emitted; a long-running plugin may be quiet until completion.
   Scroll up to pause following, or enable **Follow output** to return to the
   bottom. The recent window is bounded; full plugin results remain in Evidence.
   Entries are isolated to the active job/turn and render as plain text. The
   console does not expose model reasoning or raw protocol/credential traffic.
   Completed artifacts remain, and interrupted jobs/drafts are marked incomplete. An app
   restart marks unfinished jobs incomplete; it never automatically restarts them.
   Explicitly queue a new question/report operation to continue a saved completed
   conversation. An interrupted compatible-API turn requires an explicit new
   session in Settings; its transcript and completed evidence remain saved.

Core [result reuse](https://github.com/NoCoolUserName/volatility-mcp/blob/main/docs/RESULT_REUSE.md) now applies beneath readiness and agent tool
calls. Equivalent requests can reuse verified successful runs after restart, with
their original run IDs and artifact paths. This is independent of the Workbench
queue and leaves sealed report versions unchanged. Old runs without reuse metadata
remain available for saved-output reading but are not automatically certified as
cache hits. Hashing remains mandatory; failed or changed-context runs are not reused.

The investigator can now call `inspect_artifact` through that same scoped MCP
connection. It inspects saved registered files for PE metadata or bounded printable
ASCII/UTF-16LE strings; it does not rerun extraction or memory analysis. Guidance
explicitly separates header flags, readable ranges, string observations and malware
conclusions. New report revisions package inspection outputs as separate derived
runs linked to the original extraction artifact; historical bundles remain intact.
Install updated locked dependencies and restart idle Workbench after upgrading so
both its MCP process and resumed case guidance load the new capability.

## Architecture and boundaries

```text
Browser or native WebView (loopback, escaped views)
  -> local HTTP controller + durable private job/case state
     -> readiness: official MCP client -> scoped core MCP -> existing Volatility
     -> investigation: Codex app-server or opt-in compatible adapter
          -> scoped core MCP -> Volatility
          -> optional case tools: notes, bounded artifact reads, report packaging
```

`volatility_workbench/codex.py` isolates newline-delimited JSON-RPC initialization, thread start/resume,
turns, events, interruption, and server requests. It follows the
[official app-server interface](https://learn.chatgpt.com/docs/app-server), checked
against JSON schemas generated by installed Codex 0.160.0. Dynamic case tools use
its documented experimental API. `volatility_workbench/providers.py` implements
the optional compatible chat/tool adapter with bounded loops and per-case,
endpoint/model-bound transcripts. Both use the same confined MCP tools and
validated report functions; provider switching never resumes another provider's
thread. Compatible model traffic was mocked during verification; a real scoped
MCP saved-evidence call was exercised.

The Codex adapter reuses existing authentication and provider selection without setting
an API key, model provider, or billing mode. It requests read-only shell/filesystem
access, user-reviewed on-request approvals, and disables shell execution, unrelated
MCP servers, apps, plugins, hooks, browser tools, and delegation for case threads.
The explicit scoped MCP process can still write its case analysis outputs, and
case tools can write the current report draft. Effective returned approval and
sandbox settings are checked; incompatible overrides block investigation and are
recorded. This is an application boundary, not isolation from a compromised local
account, trusted analyzer, parser, or Codex installation.

Case-scoped Volatility tools are preauthorized with
`mcp_servers.volatility.default_tools_approval_mode = "approve"` on thread start
and resume. Requested analysis runs without a second approval click. Restart
Workbench after upgrading to apply this to existing case conversations. This does
not change global Codex configuration or authorize generic shell commands.
The launcher checks a fingerprint of the installed application code before
reopening an existing instance. If that instance predates an update (or predates
fingerprint tracking), it tells you to stop the old Terminal process and relaunch
instead of silently reopening outdated code. A browser refresh alone cannot
restart the Python backend. Stopping marks active work incomplete and preserves
completed artifacts; submit a follow-up after relaunch to continue.

Workbench displays timestamps in U.S. Central time with the Zulu clock in
parentheses, e.g. `2026-10-05 22:15:01 CDT (03:15:01Z)`, including legacy
report versions, activity, conversation timestamps, and evidence-path labels.
Conversion uses `America/Chicago` for each timestamp, so CST/CDT and the local
calendar date reflect daylight saving time at that instant. The leading date is
the Central date; the parenthesized Zulu clock can belong to the next UTC day.
Execution/state metadata remains seconds-resolution UTC (`YYYY-MM-DD HH:MM:SSZ`).
Plugin **Speed** is the difference between the original Finished and Started
timestamps, including this saved UTC format and ISO timestamps. Display-time
conversion does not affect the calculation.
New run/report folders and registration backups use portable names such as
`2026-10-06_02-52-39Z-<unique suffix>`; the suffix prevents same-second collisions.
Existing folders, sealed reports, and raw evidence remain unchanged. Evidence
buttons retain their original link targets (hover to see the actual path), and
the raw artifact preview preserves source content and timestamp precision.
Opening a report citation, saved result or plugin manifest shows a sticky
**Back to report** button in Evidence. It restores the clicked link's position
and keyboard focus in the same report; the Reports tab also restores that
position. Switching cases or report versions clears the return location.
When you scroll deep into a report, an up-arrow near the lower right edge
returns to the top. It disappears near the top and outside the Reports tab.
The case header shows evidence image sizes in decimal MB, or GB at 1 GB and
above, rounded to two decimal places.
Below **Executive summary**, a sealed report displays its AI determination as
Benign, Malicious or Undetermined. New reports ask the report-writing AI to
state exactly one of these in the saved summary and explain its basis. Older
reports without that line receive a conservative reading of affirmative
summary language; ambiguous summaries show Undetermined. A separate **Human
Determination** selector can disagree with the AI. It saves per report version
in private Workbench state with an activity timestamp, without editing the
sealed report or starting an investigation. Benign appears bold green,
Malicious bold red, and Undetermined bold white; an unset human choice remains
visibly unset.

Other supported command/file approvals and scoped Volatility MCP form requests are
shown with details and approve-once/decline/cancel choices; user-input requests
accept answers. MCP forms support scalar and single-choice fields, with server-side
schema validation; unsupported fields cannot be approved through this UI. URL and
device-verification elicitations are declined. There is no automatic privileged
approval or persistent rule amendment. Unsupported request kinds fail without a
permission grant. No generic shell endpoint is exposed by the UI.

HTTP actions require an exact local Host and Origin and a per-launch capability
exchanged for an HttpOnly, SameSite=Strict session cookie. No CORS access is granted.
The capability is removed from the URL fragment after connection; no model
credentials enter browser storage. Responses are no-store with restrictive CSP,
no-referrer and nosniff headers. Report rendering uses text DOM nodes and permits
only constrained local artifact navigation; remote links are displayed as text.
These controls do not protect against another process running as the same user.

Private state includes case records, job status, conversation excerpts, activity,
scoped MCP configuration, source paths, and reports. Codex also keeps its own thread
history under its existing user state. Source images are never copied to bundles.
The image stays local, **but questions and selected tool output may reach the
configured AI service**. Volatility may fetch symbols. See `SECURITY.md`.

## Limits and troubleshooting

- macOS ARM64 is the verified host. The Finder helper is macOS-only; other POSIX
  hosts have path entry/browsing but are unverified. Windows hosts remain unsupported.
  The helper's AppleScript was compiled successfully; interactive Finder selection
  was not exercised during automated verification. Path entry and folder browsing
  do not depend on that helper.
- When using Codex, keep it signed in using its supported CLI login. A workspace-restricted agent
  may be unable to start app-server because it cannot open `~/.codex` state. Run the
  documented launch command in ordinary Terminal or grant that specific operation;
  the application does not bypass an enforced policy.
- A connected UI with an unsigned-in account does not establish model access.
  Readiness checks account state; a completed inference turn establishes actual use.
- Agent turns have a two-hour application limit. Per-plugin limits remain configured
  in MCP. Cancellation during existing core hashing/conversion may wait for that
  stage to finish; plugin cancellation retains partial execution records.
- Forced process death cannot guarantee child cleanup. Inspect leftover processes
  before resuming after a crash. No automatic expensive retry is performed.
- Text previews are bounded; the evidence list shows at most 5,000 files, folder
  browsing at most 500 entries. This is not a large-scale evidence management system.
- Reports may fail validation or need factual correction. Continue with a focused
  question and explicitly generate/update a new version; do not edit sealed bundles.
- Parallel analysis, multiple agents per case, additional provider adapters, hosted
  access and polished document exports are deferred. The existing coins and the
  opt-in compatible API adapter are implemented.

See `docs/UI_VALIDATION.md` for actual checks and their limits.

## Image coins

Each image gets a stable, decorative coin once normal readiness has saved its
SHA-256. Original report PNGs can be imported explicitly; otherwise a local SVG
renderer uses the existing display name (or filename), a hash-derived monogram,
and distinct circuit traces. Silver concentric rims, graphite faces, emerald
inlays and curved lettering follow the earlier report coins. The SVG companion
is stylized rather than the originals' photographic metal finish. It assigns no
malware family. No image model, network call, forensic command, or evidence hashing
is involved in artwork creation.

Assets stay in private Workbench storage: `coin-library/<image-sha256>/` stores the
immutable master and provenance; `<case-id>/assets/coins/` stores case copies.
New report versions carry portable copies, Markdown image links, manifest coin
metadata, and checksums. The report viewer also displays coins above old reports
without changing their sealed files. Hover artwork for its decorative label.
Click a coin to enlarge it. Left-click anywhere (including the coin) or press
Escape to dismiss; right-click the enlarged image to use the browser's Save Image
As menu. Keyboard users can focus a coin and press Enter or Space.

Populate existing images from saved metadata only (safe to repeat):

```sh
python -m volatility_workbench.coins --state-dir /path/to/private/workbench
```

To reuse original PNG artwork, import it **before** population for that identity:

```sh
python -m volatility_workbench.coins --state-dir /path/to/private/workbench \
  --sha256 <already-recorded-image-sha256> --png /path/to/original-coin.png \
  --label 'Existing image display name' \
  --provenance 'Original report asset; decorative, not forensic evidence'
```

Then run the population command. Existing coins are never replaced. Restart an
idle Workbench to load populated assets; do not interrupt an active investigation.
An artwork error is recorded without preventing analysis or report generation.
Core MCP tools remain entirely independent of this optional presentation layer.

Saved results can be filtered, counted, grouped and cited with the core
`query_output` and `get_evidence` tools. Workbench follow-ups use saved evidence
first; its report viewer can resolve checked citations to source values. Historical
locators remain readable but are not promoted to value-verified citations. See
[the saved-evidence contract](https://github.com/NoCoolUserName/volatility-mcp/blob/main/docs/SAVED_EVIDENCE.md).


The **Coverage** tab shows each selected image's explicit plan or unspecified
scope, effective collection states, prior attempts and saved evidence/failure links.
Refresh reads saved data only. Orchestration jobs are separate from plugin outcomes.
New reports include a coverage snapshot and limitations summary; old reports are
unchanged. See [COVERAGE_EVALUATION.md](https://github.com/NoCoolUserName/volatility-mcp/blob/main/docs/COVERAGE_EVALUATION.md). Restart only an idle
Workbench to load the new tool inventory, case guidance and view.

## Installed plugins

### Per-report plugin inventory

**Plugins used in this report** appears with the selected report revision. Its
table is derived from that report's saved bundle, rather than the current installed
catalog or later case activity. Exact plugin names, arguments, recorded outcomes,
image identities and run/call IDs remain inspectable, with links to the local
supporting execution metadata. The new Quick Description column comes from the
currently installed plugin catalog. Run provenance shows elapsed execution time
computed from saved start/finish timestamps; Call, Started, and Finished stay
under Details. Missing or invalid timestamps are labelled rather than estimated.
Pages keep large inventories manageable. All three expanded tables end with
**Source provenance**, taken from the current catalog's registered attribution.
Public repository links target their README; official Volatility plugins also link
to their plugin documentation. Links open externally without a referrer. Unknown
attribution stays explicit; a source link does not authenticate historical plugin
bytes. Local run/manifest links remain separate from public project provenance.

Below the used records, **Plugins that errored** lists saved failed runs and failed
or denied requests, distinguishing requests that never executed a plugin. Links
open registered stderr/run metadata or the saved request error in Evidence, with
Back to report preserving the origin. Small request diagnostics are hash checked
and matched by call ID and plugin before display; catalog compatibility notes add
context without changing the saved outcome. **Plugins
not used** compares the current installed catalog with the full snapshot's recorded
physical executions and shows each remaining plugin with an **Add to prompt** button
and quick description. The button appends a request for that plugin to the current
case's investigation focus without starting work. Review the accumulated focus and
choose **Update report** when ready; that action creates the new report version.
After Update report accepts the request, the investigation focus clears. A failed
submission leaves the text in place for correction and retry.

While a report revision is still draft, the report pane shows **Report running…**
and the current job step without requesting a report file that has not been saved.
Its progress bar is indeterminate when the prompt has no explicit plugin list or
one of the listed plugins has no successful saved timing history. For a known list,
the bar weights completed planned plugin runs by their historical average durations.
The segmented, square-edged meter uses the selected theme's accent color and
uses a three-second sweep when indeterminate. It stops animating when reduced
motion is requested.
It estimates *plugin work only*: model reasoning, evidence review, validation and
report writing have no reliable plugin-based ETA. The private `plugin-speeds.json`
table keeps the last ten successful physical execution times for each plugin;
failed requests, errors and reused results do not supply timing samples. Once the
revision seals, the complete saved report replaces the running view.
**Add all OS-relevant to prompt** uses each case image's saved discovery
`detected_os` and the installed catalog's `target_os` to group unused plugins by
image. Windows, Linux and macOS are matched explicitly; the host OS and case title
are never used. Unknown/mixed image OS and unspecified plugin targets are excluded
with an explanation. The draft asks for OS/build/architecture/symbol checks, actual
required arguments, explicit skips/failures, and a new report with coverage limits.
It preserves existing prompt text and starts no work. The button is disabled while
its full request is present; editing/removing that request re-enables it.

Once a case has a sealed report, **Update report** moves before **Generate report**
and receives the primary fill. A case without a sealed report keeps Generate first.
When either job finishes, the UI selects its new revision and reads fresh used,
errored and unused inventories, including when an older revision was selected or
the new revision's draft had been viewed. Historical snapshots stay unchanged.

The focus box keeps at least two readable lines, grows with added plugin requests,
and is vertically resizable. Sizing waits until the selected case is visible. Focus
drafts stay separate when switching cases during the app session.
The comparison uses all bundled records even when the used table displays one page.
Catalog changes or partial historical metadata can affect this comparison; it is
not a statement of image compatibility or forensic coverage. Catalog discovery
and these lists do not run any plugins.

Original saved executions can predate a report revision. Reuse receipts are not
new scans, failed requests without a run are not successful executions, and
artifact inspections are not Volatility plugins. The UI keeps these distinctions
visible. Missing or partial historical metadata is labelled; an absent inventory
is not evidence that no plugin ran. Refreshing this view reads saved metadata
only and never analyzes or hashes a source image.

New bundles retain a machine-readable plugin inventory and generated labeled entries
inside the existing investigative-workflow section of their portable Markdown.
The generated section is synchronized before sealing and included in checksums.
Existing sealed reports remain byte-identical; their UI inventory is derived
read-only from the metadata they already contain. Installed command counts and
recorded run counts are not forensic coverage denominators or clean verdicts.

### Global plugin catalog

The **Plugins** button below the Volatility Workbench title opens a global
catalog in the main pane, even when no case is registered. It lists the
configured analyzer's discovered plugins in two columns: exact plugin name
and source. Search names/descriptions/sources, filter by OS, or open the Source
column dropdown to check any combination of the actual discovered source
labels. **All** selects or clears every source; its mixed state reflects a partial
selection. Native Volatility 3 appears first, followed by the local volatility-mcp
addon, then the remaining sources alphabetically. Expand a name for
description, version, provenance basis, and compatibility notes. Known source labels link to the upstream project. Back to
case restores the selected case and report tab. Background state polling does
not close the catalog, reset filters, or repeat discovery.

`GET /api/plugins` uses the supported core `list_plugins` API behind MCP. Refresh
uses `GET /api/plugins?refresh=1`. Both require the existing local session and never
submit jobs, hash images, analyze memory, or connect to Codex. Import failures are
shown separately; a failed refresh retains and explicitly labels the old inventory.
Discovery success is not proof of image compatibility. Source unknown is explicit;
`installed_volatility` alone does not mean Native. See the authoritative
[core source contract](https://github.com/NoCoolUserName/volatility-mcp/blob/main/docs/PUBLIC_API.md#plugin-catalog).

The optional [community profile](https://github.com/NoCoolUserName/volatility-mcp/blob/main/docs/COMMUNITY_PLUGINS.md)
adds its exact discovered names, upstream-source checkbox labels and compatibility
notes automatically; no case migration or report regeneration is required.
Ptenum's callable entry is `windows.simple_pteenum.SimplePteEnumerator`; the
PTE-family requires 64-bit Windows. EVTXLog does not parse XP EVT. Installation
and synthetic fixture checks do not establish runtime support for a chosen image.
