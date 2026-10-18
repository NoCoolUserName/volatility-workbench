# Workbench scope

The current application supports saved-case navigation, newest-first initial
selection, report/evidence/citation/coverage views, sequential jobs, cancellation,
resumable case conversations, coins and three display themes. See LOCAL_UI.md.

The optional native macOS application, managed plugin/symbol settings and one
compatible tool-API adapter are now implemented; see MACOS_APP.md and
AI_PROVIDERS.md for actual validation and limits. Advanced exports, additional
provider protocols, parallel analysis, Intel/Windows distributions and broader
accessibility testing remain future work. Shared forensic evaluation and contracts are maintained
in volatility-mcp; do not fork them here.

## Proposed investigation modes — not implemented

| Mode | Intended scope |
| --- | --- |
| Quick triage | Identify OS/symbol readiness; collect a bounded process/command-line/network/module baseline; follow high-value anomalies within a declared time/output budget. Save leads, evidence and gaps, not a clean verdict. |
| Targeted investigation | Pursue an explicit question or selected process/address, reusing saved results first and collecting only justified missing evidence. |
| Compatibility sweep ("Run all applicable plugins") | A diagnostic mode: sequentially attempt OS-appropriate plugins with satisfiable arguments/prerequisites; record success, empty, skipped, unsupported, failure, duration, hashing overhead, reuse and output size separately. Extraction/credential/expensive operations require explicit inclusion and bounded settings. |

These buttons are a design proposal, not permission to start a sweep. Installed
plugin count is not a coverage denominator: some plugins need PID/address/rules or
particular symbols and artifacts. One XP image cannot establish support elsewhere.
Use measured cost and human-reviewed lead yield from multiple representative
malicious and benign fixtures to version OS-specific triage profiles/templates.
Distinguish cache hits from physical execution; total duration alone includes
integrity checks and is not a plugin-only benchmark. Never tune a template solely
to a known malware filename or present a heuristic as a validated detector.

## Biggest remaining gaps before wider use

This is the prioritized work list. [UI validation](UI_VALIDATION.md) and
[packaging validation](../packaging/VALIDATION.md) record what was actually tested;
completing a task here requires recording the new evidence there. These are
release readiness gaps, not claims that the listed feature is absent.

| Priority | Gap supported by current validation | Acceptance check |
| --- | --- | --- |
| 1 | A real Codex/MCP report, follow-up, and revision were exercised on this developer Mac. They have not been repeated as one acceptance run of the current distributable app on a clean user account or second Mac. | From a clean install, use a harmless fixture to select a file, complete readiness, generate a report, ask a follow-up, revise it, quit, and reopen without lost case state or duplicate analysis. Record the app revision, OS, and results. |
| 2 | Cancellation/restart work is tested, but forced process death cannot guarantee child cleanup; long hashing/conversion can delay Stop, and output storage has no quota. | Exercise interruption and restart with bounded large fixtures; verify child cleanup, incomplete state, preserved artifacts, predictable Stop latency, and a documented storage limit or warning. |
| 3 | Saved-output/citation contracts and synthetic checks exist, but there is no independent demonstration of broad forensic or model-answer accuracy. | Use a small human-reviewed, multi-OS saved-evidence set to check supported observations, abstentions, citation values, and report conclusions. Record false leads and unknowns separately from contract-test pass rates; keep private images out of Git. |
| 4 | Plugin discovery works, but real-image support across OS/build/symbol combinations is not established; the starter symbol profile is deliberately narrow, and selected community sources cannot yet be redistributed in the public bundle. | Record a supported OS/build/plugin matrix with real compatibility results and actionable failures; resolve upstream redistribution terms or retain explicit operator downloads for each excluded source. |
| 5 | The macOS release pipeline is implemented and tested with simulated Apple responses; no Developer ID signed, notarized, downloaded-app Gatekeeper acceptance has been recorded. | Sign with an authorized Developer ID, notarize and staple, then test the downloaded archive on a second Mac with quarantine intact and document the outcome. |

If a container distribution is added, keep the analyzer dependency profile explicit:
install and pin the official Volatility 3 `full` extra in its analyzer environment;
package any selected third-party plugin file and its own dependencies with pinned
source provenance and license review. Treat cloud/Arrow extras and browser-test
Playwright as separate opt-in profiles. At build time, check package requirements,
`vol -h`, the core plugin inventory and Workbench's import-failure display. Use
harmless fixtures for runtime plugin checks; import success alone does not prove
image compatibility. The UI must not silently install plugin dependencies.

The native app and future container plugin baseline is core's versioned
`community-2026-10` profile: PteMalfind/Ptenum, ImgMalfind, Prefetch, AnyDesk,
EVTXLog, Browser History Extractor and KeePass (plus ApiSearch support). Extend
that single core inventory for later additions; do not create a Workbench copy
of its installer or plugin implementations. The profile is locally installable
now. Selected upstream redistribution licenses/source obligations remain unresolved;
the native public bundle includes eligible plugins and provides explicit operator
upstream download for the remainder. Future containers must preserve that policy. See [the core profile](https://github.com/NoCoolUserName/volatility-mcp/blob/main/docs/COMMUNITY_PLUGINS.md).
