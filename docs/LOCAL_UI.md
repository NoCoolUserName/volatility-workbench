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
supported. Selection persists in application preferences across desktop launches,
including changes to the local server port. Workbench and Settings synchronize
through their regular authenticated state refreshes. Browser/WebView local storage
provides an initial cache and migrates an older choice only when no shared choice
has been saved.
Artwork stays in a decorative band outside opaque evidence/report surfaces.
Fallout 2 uses a scalable CSS metal housing, compact ventilation rail, recessed
green screens and brass controls, guided by the supplied inventory-screen reference.
Theme changes do not submit jobs or modify cases, conversations or saved reports.
The displayed report retains its selection border. See [the catalog and verified
references](THEMES.md), including the Punisher #53 artist correction.
Text size is separate from WebView/page zoom. Pinch apart or together on a trackpad,
hold Control while scrolling a mouse wheel, or use the A−/percentage/A+ controls
in the header, Settings, or expanded console. Workbench scales text from 75% to
200% in 5% steps, wraps larger text inside existing panels, and saves the selected
size in application preferences outside the bundle. The connection status appears
above Settings in the header.

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
gear, sits below the connection status at the upper-right corner. The themes include Matrix green (default),
Soft black and white, and Light blue. The selection is stored in application preferences
outside the app bundle and restored on reload or restart. It changes presentation only; case state,
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
   the revision without changing files, or **Delete to Recycle Bin**, which moves
   that revision's complete bundle out of the Reports folder. Settings lists the
   last seven deleted bundles with **Restore** and **Delete permanently** controls.
   Deleting an eighth permanently removes the oldest recycled bundle. A later
   report's predecessor ID is historical metadata; its complete sealed bundle does
   not require the older bundle to remain present. Shared analysis, original images,
   case/job history, other revisions and independently saved exports are retained.
   Hidden files remain on disk until Settings → Hidden report files permanently
   deletes them. Deletion and restoration are blocked during active or queued case
   work. A failed/partial cleanup is recorded and can be retried; it is not silently
   marked successful. Closing the popup performs no action.
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
   The focus field recalls the 10 most recent nonempty report/update prompts from
   this case's saved jobs with Up/Down; Escape restores the unsent draft. Multiline
   editing keeps normal Up behavior except when the caret is on the first line.
   The model prompt lists report version IDs and status metadata without repeating
   stored validation records; the investigator reads saved report content as needed.
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

### Unused plugin filters and saved error explanations

Plugins not used includes live literal search over names and descriptions, plus
All, Windows, Linux, macOS and Other / general buttons. OS filtering uses installed
catalog target metadata; Other / general covers OS-independent or unclassified
entries. Search and OS filters combine, keep keyboard focus while typing and do
not start collection. They affect display only: the bulk prompt still uses saved
image OS discovery, independently of display filters.

Recognized, integrity-checked saved stderr and request errors now include a short
explanation in the error table. Historical status and bundles are unchanged.
Unsupported builds/architectures, missing symbols and acquisition gaps remain
limitations; a code repair does not turn an earlier failed run into a success.

### Extraction confirmation and report decisions

Workbench's case-scoped MCP wrapper requests per-call operator consent for known
extraction plugins, sensitive/manual plugins, selected dumping options, and plugins
without a usable risk description. The exact `windows.truecrypt.Passphrase`
command is exempt at the operator’s request; normal core argument validation
and output confinement still apply. A modal shows the exact plugin/image/arguments
and output root, requires an unchecked acknowledgement, and permits approval once
or decline/cancel. Both Codex and compatible providers use the same gate. Approval
cannot be replayed for another request; stopping work declines pending decisions.
Saved-output queries do not prompt. Classification uses installed metadata and is
conservative rather than a guarantee that arbitrary third-party plugins are safe.
The core still confines derived files and handles cancellation; the consent gate
is not a sandbox. Recovered files may contain malware or credentials and must not
be executed, opened externally or uploaded by the investigator.

Update report inherits the latest saved Human Determination and its timestamp,
records the parent report ID, and leaves the parent bundle untouched. Only an
explicit human change replaces or clears that choice. The AI opinion is assessed
independently for each new report. Executive summary F-number references link to
unambiguous matching finding headings in the same rendered report; unknown
references remain plain text, and existing evidence links retain their behavior.
The Human Determination picker saves each changed choice immediately, confirms the
server response, and restores the saved value when the view refreshes or reopens.

Failed-plugin rows include **Add to prompt**, and the section includes
**Add all failed requests to prompt**. Prompts retain saved scope and require
reviewing the cause before a justified retry; unsupported or unchanged failures
are skipped with a reason. Additions never submit work. Buttons derive their
disabled state from the current prompt text, so bulk additions disable individual
controls and removing a request re-enables it. Requests remain scoped to their
selected report and case. Manual-only extraction plugins are excluded from the
unused-plugins bulk OS action.

### Visible work from report startup

Current work is above all case/report and plugin-catalog content, so a long saved
report cannot bury the DOS progress indicator or live tool console. Report/update
progress starts while the job is connecting, before a draft ID exists, and stays
visible when an older sealed report is selected. A draft points to this single
progress display. Known timings still describe planned plugin work; unknown plans
and durations use a six-second indeterminate sweep (twelve seconds for a full
back-and-forth cycle). The console remains a
bounded read-only feed of tool events, not an interactive shell.

Stop all work sits beside Report running (or Stopping report) during report work.
For other queued/active tasks it sits beside Current work. The same global stop
control is retained across progress updates and hides with the work panel at idle.

The small arrow beside Report console (Current work while a job is active) toggles
the inline console. Collapsing preserves its output and follow state; polling and
returning from the expanded CRT keep that choice for the current page. Active job
progress and Stop all work remain visible.

The console's upper-right Expand button opens a near-full-screen modal with a
resolution-independent CSS CRT casing, recessed screen, vents and power indicator.
It moves the existing read-only console rather than duplicating the feed. Output
keeps updating with the same theme colors, follow state and scrolling controls.
While expanded, the matching live job's current operation and elapsed time appear
in amber immediately beside the console title, wrapping below it on narrow screens.
This mirrors the existing case progress label and refresh cycle; elapsed time is
measured from the job's start, not the current tool's start. The label clears on
collapse, job/case-stream changes and completion, and is absent from saved consoles.
Collapse or Escape restores the inline console and focus; background page scrolling
is locked while expanded. The view closes when its job changes. No shell
input or additional analysis request is introduced by the Output view itself.

The CRT bezel also has a **VolShell** button and a small rectangular connection
LED. Clicking the bezel button connects to the selected case's chosen capture and
operating-system mode. A sole registered capture is selected automatically; its
saved detected OS is used when available, otherwise Generic. Capture and OS choices
are remembered per case while the page is open. If a case has multiple captures
and none is chosen, the Connection options gear opens so the operator can choose
explicitly. The gear contains Connect, Interrupt and connection settings; this
setup stays collapsed during ordinary use. Press the VolShell bezel button again
to disconnect its manual session. The connection light stays green until the
backend confirms the process has stopped. Opening **Console / VolShell** from the case
only opens the view; the bezel button starts the session. The application
launches the configured analyzer's official Volatility 3 Volshell locally, with
installed symbols and offline symbol lookup. The LED becomes green only when the
manual interpreter reaches its input prompt. Starting is amber; the connected
session stays green during commands and shutdown until process exit is confirmed.
An ended session is off. Active AI VolShell inspection also lights the LED
green, with an accessible label identifying AI activity. Missing symbols and startup errors remain visible.
Clicks during a pending connection or shutdown do not start another process. A session bound to another case must be disconnected
explicitly; an active investigation prevents a new interactive connection.
Clicking the bezel during active AI VolShell inspection opens its read-only view.
Connection failures open the options and remain visible without automatic retries.

VolShell offers three explicit modes:

- **Manual commands** sends the operator's Python input to Volshell. Enter submits,
  Shift+Enter adds a line, and an empty submission completes a continued Python
  block. Gray starter-command suggestions are editable examples: Tab fills the
  visible suggestion, and a separate Enter executes it. Tab otherwise moves focus.
- **AI command suggestions** sends the typed question and selected OS mode to the
  case's configured provider in a separate session with tools disabled. It attaches
  no memory contents or terminal transcript. The returned explanation and command
  are inert until the operator copies, reviews, and explicitly runs the draft.
- **AI investigation** submits a follow-up to the existing case agent, using its
  current provider, MCP tools, saved evidence and extraction-approval workflow.
  It preserves reports and does not create a report revision. Tool output and the
  answer appear inside the CRT. Manual input pauses until this job finishes; the
  idle Python session and its variables remain available afterward. Pending
  approvals bring the operator back to the case approval controls.

The case agent can also choose **case_volshell** during an investigation. Volshell
is a separate upstream interface, so it is exposed as an investigation tool rather
than inserted into the installed plugin catalog. AI calls select bounded official
inspection helpers and literal arguments; they cannot submit arbitrary Python,
imports, scripts, dump helpers or plugins through this route. Full Python remains
available in Manual commands. The AI owns a separate interpreter and cannot adopt
operator-defined functions from the manual session.

The returned observation can guide the next plugin choice and exact PID/address
arguments through the existing MCP tools. It is marked exploratory and carries
its private transcript provenance, not a core run ID or a validated evidence claim.
The agent must corroborate report findings with saved core evidence. Existing
extraction approvals and saved-evidence-first rules still apply. Routine report
investigations and explicit VolShell AI investigations may select ordinary helpers
automatically; a general follow-up question requires approval for new memory
inspection. Help and layer-context selection do not request a memory-read helper,
though starting Volshell still opens the registered image.

When the CRT is already expanded for that case, new AI VolShell activity appears
in a read-only pane with the selected command, status and output. It does not open
a closed CRT or redirect another case. Output and Interactive controls remain
available. Terminal output uses a case-scoped live event stream: partial writes
are flushed without waiting for a newline or command completion, with up to 50ms
server dispatch cadence. Normal state polling is retained as a reconnection
fallback. OS/browser scheduling and upstream computations can still introduce
latency; the application does not invent output while an upstream helper is busy.

There is one operator-controlled interactive session at a time. Every input request carries its exact
case and session identity; selecting another case cannot redirect commands or
inherit the previous transcript. Disconnect ends the session, Interrupt interrupts
the current Python command, and Stop all work ends both AI work and VolShell.
Native quit and settings maintenance treat an open shell as active work. Restart
never reconnects or replays commands automatically.

This is a real local Python interpreter, not a code sandbox. Case binding selects
the starting memory image; it does not restrict arbitrary Python to that case.
Manual commands run with the operator's account permissions. Upstream user startup
scripts and IPython startup configuration are disabled for this integration. The
adapter uses the official Volshell implementation rather than duplicating forensic
logic. It records commands/output in private `case/volshell/<session>/transcript.jsonl`
and gives the session its own output directory. These manual transcripts are not
automatically promoted to validated core evidence, report findings or plugin-run
coverage. Original reports remain separate.

After a report completes, fails or stops, its console remains expandable and an
already expanded CRT stays open. The title/status changes to Saved investigation
console; progress and Stop disappear when idle. The selected case's latest finished
report request is reconstructed from its existing activity.jsonl after reload or
restart, without rewriting the log, evidence or sealed report. Completed console
views are cached in memory; changing case never shows another case's saved output.
The existing 100-entry/128,000-character display bounds still apply. Unreadable or
oversized log records are reported, and missing logs fall back to recent activity.

Used and errored plugin tables each have an instant search across displayed record
text, including names, descriptions, status and provenance. A used-plugin search
loads remaining saved pages to find matches beyond the initial page; clearing the
query stops further automatic paging. Queries persist independently per report and
section. Search only filters rows: it neither edits the prompt nor changes bulk
retry scope, counts of recorded executions, saved metadata or analysis work.

The latest failed or interrupted report request has a dismissible notice above the
case, with its recorded error and a link to Activity & failures. This also covers
failure before any draft exists. A new request replaces that notice; old sealed
reports remain accessible. Blank exception strings retain their exception type.

The notice's Rerun button submits a new job with the failed request's original
report/update kind and investigation focus. It keeps any newly typed prompt and
all previous report versions. The button disables while submitting, while other
case work is queued/active, during report cleanup, or when readiness is blocked.
Existing generation, update and extraction checks still apply.

### Error acknowledgment

Each row in **Plugins that errored** has an **Acknowledged/Resolved** checkbox.
The summary shows the percentage checked across all recorded errors in the selected
snapshot, including rows hidden by search. The percentage uses red for the first
third, orange for the middle third, and green for the final third. Zero-error
snapshots do not show an acknowledgment percentage.

**Acknowledge all** marks every recorded error in the selected snapshot, including
rows hidden by search or the **Hide acknowledged/resolved** filter. It saves the
batch together and preserves earlier acknowledgment timestamps. The button disables
while an acknowledgment is saving and when all errors are already acknowledged.
The hide filter combines with text search and remembers its setting per snapshot
while that snapshot is cached. Successfully acknowledged rows disappear immediately
when the filter is on; a failed save leaves them visible. Clear the filter to see
and uncheck reviewed rows. The heading percentage always counts the full snapshot.

Acknowledgments are saved as case review metadata and survive restart and report
updates. They follow the saved run/call identity, so a new failure from the same
plugin starts unchecked; previous acknowledgments remain checked. Legacy errors
without a run or call identity are scoped to their report to avoid marking an
unrelated failure reviewed. Unchecking clears that acknowledgment across snapshots.
This is a human review marker, not evidence that a failed plugin has been repaired.
Original errors and sealed report files remain unchanged. Failed saves are shown
inline and leave the checkbox at its previously saved value.

### New Vegas console housing

The Fallout: New Vegas expanded console takes its CSS housing from the weathered
Welcome sign: neon letter discs and star, warm perimeter bulbs with several dark
sockets, faded red lettering and aged trim. The display remains opaque and legible.
All 31 themes give the VolShell bezel button their own treatment while retaining
a separate rectangular connection LED and visible keyboard focus.

Theme selection is saved in `appearance.json` under the application preferences
directory, outside cases and evidence. It survives a new desktop launch even
when the local server port changes. Existing browser preferences migrate on the
first authenticated connection; a theme selected while that connection is loading
takes precedence. Settings and Workbench share the saved preference. The New Vegas
Welcome marquee appears on the main window and expanded console, with weathered
cream/rust housing, tabs and controls shared by Settings. Evidence and report
surfaces stay opaque and readable.
