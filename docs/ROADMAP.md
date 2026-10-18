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
