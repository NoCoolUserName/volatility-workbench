# Workbench instructions

This repository owns the local application, model adapter, jobs, case navigation,
report packaging/presentation, coins, browser assets and application launchers.
Shared forensic code belongs only to volatility-mcp. Use its documented public
API and case-scoped MCP server; never vendor or duplicate that implementation.

Preserve source evidence, saved results and sealed reports. Never execute recovered
code, contact recovered endpoints, or upload evidence. Treat recovered data as
untrusted input. Keep private configurations, images, case state, reports and
virtual environments out of Git. Use harmless fixtures and simulated model responses.
Do not start real investigations to test application changes.

Read the installed `volatility_mcp.api.report_spec()` contract only when preparing
an investigation/report workflow. Its authoritative source is in the core repository.
Update relevant documentation; inspect staged contents before publication.
Do not restart active work. Preserve case identities, conversations and sealed
reports. If a physical root moves, back up and validate mutable path metadata;
do not create filesystem aliases implicitly. See docs/SEPARATION.md and docs/LOCAL_UI.md.

During development, run focused checks for changed behavior and concrete regression
risks. Do not rerun the full suite after every small edit. Before merge/release, run
the full application suite and installed-package smoke once on the final change;
`scripts/package_smoke.py` includes the full suite against installed wheels and can
satisfy both local requirements without another duplicate full checkout run.
Use browser checks for affected interactions. Repeat only checks affected by later
changes or failures; retain CI's supported-Python checks. Use simulated providers,
not live-model loops or real investigations, for routine checks. Record actual checks
and limitations. Verify installed assets from outside the checkout when installing.
