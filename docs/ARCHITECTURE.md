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
