# Architecture

Browser static assets → loopback HTTP controller → private durable case/jobs state.
The controller uses `volatility_mcp.api` for local saved-data access, confinement,
coverage and report validation. Readiness and Codex case turns use the official
MCP SDK and `python -m volatility_mcp.scoped` for the same ten case-confined tools.
Codex is an adapter; core imports no model provider or application package.

`app.py` owns sequential jobs, cancellation and case conversations. `storage.py`
packages explicit new report revisions using the core contract/validator. `coins.py`
creates decorative assets from saved identities. `http.py` serves packaged static
assets with loopback Host/Origin/capability checks. The runtime fingerprint covers
both installed packages, so a core update requires an idle process restart.

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
