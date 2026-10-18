# Workbench scope

The current application supports saved-case navigation, newest-first initial
selection, report/evidence/citation/coverage views, sequential jobs, cancellation,
resumable case conversations, coins and three display themes. See LOCAL_UI.md.

Desktop wrapping, additional model providers, advanced exports, parallel analysis,
and broader platform/accessibility support remain future work. Repository separation
adds none of those features. Shared forensic evaluation and contracts are maintained
in volatility-mcp; do not fork them here.

If a container distribution is added, keep the analyzer dependency profile explicit:
install and pin the official Volatility 3 `full` extra in its analyzer environment;
package any selected third-party plugin file and its own dependencies with pinned
source provenance and license review. Treat cloud/Arrow extras and browser-test
Playwright as separate opt-in profiles. At build time, check package requirements,
`vol -h`, the core plugin inventory and Workbench's import-failure display. Use
harmless fixtures for runtime plugin checks; import success alone does not prove
image compatibility. The UI must not silently install plugin dependencies.
