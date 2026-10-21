# Clean-install acceptance on macOS

Run this once for the exact candidate distributable on a **new macOS user account
or second Apple silicon Mac** (macOS 13 or later). This is a manual release gate,
not a replacement for `scripts/validate_macos.py`. Do not run the installer over
an existing Workbench application to obtain a fresh-state result. Do not copy a
developer's preferences, cases, credentials, Python environment or analyzer into
the test account. Use only an explicitly authorized harmless test image; never
use an existing private investigation as the fixture. Retain the downloaded
archive's quarantine attribute for a downloaded-app Gatekeeper check.

Before starting, record the candidate ZIP SHA-256, `build-info.json` Workbench
and core commits, signing/notarization status, Mac model/architecture, macOS
version and whether the account is new or the Mac is separate. Keep the original
ZIP. If testing an ad-hoc signed development candidate, record that Gatekeeper
acceptance of a notarized download is **not tested**; do not disable Gatekeeper
to produce a passing result.

1. In the fresh account, extract the candidate with Finder and copy the app into
   that account's `~/Applications`. Open it from Finder. Confirm a native window
   appears without Terminal, Homebrew, a checkout, a Python setup prompt, or a
   browser tab. Note any Gatekeeper dialog or failure verbatim. Inspect About
   for app/core versions. Leave the original installation in the other account
   untouched.
2. Confirm first-run Settings uses the bundled analyzer and offers the default
   Evidence/Outputs folders under `~/Documents/Volatility Workbench`. Check
   readiness before registering an image; missing AI sign-in must leave saved-case
   browsing and Settings usable. Configure a **test-only** provider credential if
   the remaining scenario requires AI. Do not copy a real credential or saved
   provider state from the developer account.
3. Place the authorized benign fixture in the fresh account's Evidence folder;
   record its path and SHA-256. Register it once. Run readiness and record the
   exact status and reasons. If the fixture cannot reach report readiness, mark
   subsequent report steps **blocked by fixture/prerequisite**, not passed. Do not
   change the readiness result by editing case state.
4. If ready, generate a report, ask a follow-up in the same case, and explicitly
   update the report. Record case ID, model session/thread ID if available,
   job IDs, report revision IDs, saved console presence, citations and the
   selected report revision. Check the original sealed report's checksum and
   the fixture hash before and after the update. Observe whether work is reused
   or repeated from the job history; do not infer this from the plugin count.
5. Quit normally while idle, reopen from Finder, and verify the same case,
   conversation, saved consoles, citations, reports and intended report selection.
   Record any selection that changes to the newest revision. Verify no job ran
   just because the app reopened. Close the window and reopen from the Dock to
   check window lifecycle separately from Quit.
6. For recovery, create an **additional disposable test case** and start a
   bounded test-only operation. Use the normal Stop/Quit controls first. If a
   forced-termination experiment is approved for the disposable fixture, record
   the exact interruption and restart: incomplete work must remain explicit,
   completed evidence intact, and nothing must resume automatically. Do not kill
   a process that is handling private evidence or maintenance. A simulated
   interrupted job in `tests/test_clean_install.py` checks state semantics but
   does not prove real process/descendant cleanup.

Record each step as **pass / fail / blocked / not run**, with a short observation,
app/core commits, fixture hash and test date. Capture screenshots or logs only
after checking they contain no token, private path, case evidence or secret.
Keep the original sealed revisions. File a focused defect for any failure, then
repeat only affected steps on a new disposable test account or clean state.

## Automated companion

`python3 -m unittest discover -s tests -p 'test_clean_install.py' -v` uses
temporary directories, a fake Volatility command and a simulated AI provider.
It exercises fresh preferences/config paths, bundled-analyzer selection and
readiness, case registration, report/follow-up/update, saved console/citation
lookup, Quit/reopen state, immutable first revision and interrupted-job recovery.
No private image or live provider is involved. The existing macOS validator
independently checks actual bundled interpreters, MCP, catalog and a synthetic
banner invocation; neither test opens a Cocoa window, verifies Finder/Launch
Services, Gatekeeper, Keychain prompts, WebKit storage, or a real forced exit.
