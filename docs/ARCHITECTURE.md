# Architecture

Browser static assets → loopback HTTP controller → private durable case/jobs state.
The controller uses `volatility_mcp.api` for local saved-data access, confinement,
coverage and report validation. Readiness and Codex case turns use the official
MCP SDK and `python -m volatility_workbench.guarded_scoped` (a consent middleware wrapper around the public core server) for the same ten case-confined tools.
Codex is an adapter; core imports no model provider or application package.

`app.py` owns sequential jobs, cancellation and case conversations. `storage.py`
packages explicit new report revisions using the core contract/validator. `coins.py`
creates decorative assets from saved identities. `http.py` serves packaged static
assets with loopback Host/Origin/capability checks. The runtime fingerprint covers
both installed packages, so a core update requires an idle process restart.

`generation.py` formats optional report-turn provenance. Thread responses provide
effective Codex model/effort; usage notifications provide cumulative counters,
with a persisted pre-turn baseline for report-only deltas. Report revisions snapshot
that metadata, never the case's latest settings retroactively. New portable Markdown,
manifest and final checksums contain the final snapshot. Live presentation of older
reports labels missing metadata instead of altering their bundles. No model requests
are made merely to display or calculate these counters.

Explicit incomplete/sealed-report hide/delete actions use the same authenticated,
Origin-checked HTTP transport. Hidden/deleted timestamps and history remain in
the existing case state. Only a registered incomplete or sealed revision can be targeted;
file cleanup is confined to its bundle with symlink, source-overlap and completed
manifest checks. A completed manifest is removable only for an explicitly selected
sealed case record; incomplete metadata cannot authorize deleting a completed bundle.
Shared analysis is never deleted. Cleanup runs in a background
thread, blocks new work for that case, and finishes before graceful shutdown.
The native shell treats cleanup as maintenance. An interrupted cleanup remains
retryable; startup never automatically deletes or regenerates reports. This is
a UI action, not a new investigator/MCP tool or generic filesystem delete API.

Case data roots, sealed bundles and conversations are independent of source paths.
The optional legacy `--project` only keeps state outside a named source tree.
Read the detailed boundaries in [LOCAL_UI.md](LOCAL_UI.md), the
[ownership map](SEPARATION.md), and the authoritative
[core API](https://github.com/NoCoolUserName/volatility-mcp/blob/main/docs/PUBLIC_API.md).

## Optional macOS desktop

`desktop.py` hosts the existing authenticated `http.Server` and `Workbench` on a
background asyncio loop. A pywebview Cocoa window displays that server; it has no
application JavaScript/native bridge. Its small pinned Cocoa adapter handles
same-origin navigation, external links, close-to-hide, Dock reopen and explicit
Quit. Backend locks and runtime fingerprints remain authoritative. Native settings
use the same guarded HTTP routes, with a private per-launch cookie.

`packaging/distribution.json` selects runtime/dependency/addon/symbol profiles.
The native executable embeds a bundled CPython interpreter but explicitly sets
`sys.executable` to the real bundled Python executable for scoped MCP subprocesses.
The analyzer is separate. Runtime code/resources/RECORD data remain in the
immutable app; configuration, overlays, symbols and caches remain outside it.

`providers.py` is the bounded compatible API connector. Codex remains in `codex.py`.
Case sessions record their provider identity. Both execute the same case-confined
MCP tools and existing report functions; no provider adds shell access. See
[providers](AI_PROVIDERS.md) and [native lifecycle](MACOS_APP.md).
