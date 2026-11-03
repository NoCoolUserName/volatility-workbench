# Workbench 0.1.4 — Summary clarity and curated themes

Experimental macOS ARM64 prerelease, continuing the ad-hoc signing profile.

## Changes since 0.1.3

- Executive summary clauses supporting an AI Malicious verdict appear red;
  clauses supporting a Benign verdict appear green. Unrelated objective facts,
  chronology, limitations and contrary evidence keep their normal text color.
  Exact author-selected excerpts preserve formatting and clickable citations.
- The 16 screenshot-listed extras and three seasonal themes are deferred to the
  roadmap. The local catalog has 18 remaining choices. Old selections resolve
  safely without rewriting their original preference or revision.
- Native Adventure CI now uses complete input comparisons. Both Adventure game
  editions remain available independently of the retired Adventure theme.
- The exact upstream BSD notice for proxy_tools 0.1.0 is included after verifying
  that the upstream, published archive and bundled implementation are identical.

The MCP backend remains 0.1.4 at `2887c77283da4a45860d8ac2f3042027401257a0`,
including CryptoMem 0.5.0. This Workbench release changes presentation and
packaging; it does not add forensic detector capabilities or capture-platform
support. Saved evidence, cases, conversations, sealed reports and independent
human determinations are preserved. No model runs merely to view a report.

## Validation and artifact provenance

- The isolated installed-wheel smoke passed all 299 application tests.
- Native ARM64 validation passed with 203 catalog plugins, no import failures,
  ten-tool MCP discovery, CryptoMem synthetic vectors and three synthetic analyzer
  invocations. First-run provisioning verified four bundled symbol packs with
  downloads blocked. Both Adventure editions passed gameplay and save checks.
- Code signatures and system-or-bundle-relative native linkage passed. The release
  audit checked layout, selected private filenames, contained symlinks, the addon
  allowlist, notices and 14,425 regular-file hashes. The ZIP passed its
  integrity check. These checks do not establish artwork redistribution rights.
- Runtime and analyzer package versions match the preceding local build, except
  for Workbench's own 0.1.4 version. The matched proxy_tools notice is present in
  both the native notices and collected dependency license texts.

Candidate measured 2026-11-03 from clean source
[`7ac98793b3151ad009c983bf397b774ce80275d4`](https://github.com/NoCoolUserName/volatility-workbench/tree/7ac98793b3151ad009c983bf397b774ce80275d4):
`Volatility Workbench.app` has 1,348,421,025 regular-file bytes
(1285.954499 MiB), excluding symlink aliases. The candidate ZIP has
1,122,203,281 bytes (1070.216447 MiB), SHA-256
`fc3bd64fae6bf43485b22b9e9483562e4440202dca10ad295370bef00def6454`.
The matching [MCP source](https://github.com/NoCoolUserName/volatility-mcp/tree/2887c77283da4a45860d8ac2f3042027401257a0)
remains pinned. A later documentation-only measurement stamp does not require
rebuilding this artifact. Final CI and publication status remain pending.

## Distribution checkpoint

Public binary upload is pending the recorded redistribution-clearance decision
for the five reference-derived bezel images, or a verified public build that
omits those images and their affected theme options. This draft does not assert
that those assets are cleared. See LICENSING.md and THEMES.md.

## Remaining limits

Ad-hoc signed; no Developer ID signing or Apple notarization is claimed.
Downloaded-app Gatekeeper/clean-Mac acceptance and broader accessibility testing
remain outstanding. The ARM64 application host does not imply support for
Apple-silicon memory captures. Existing forensic platform and symbol-matching
limits remain unchanged. Validation uses harmless synthetic/public fixtures;
no private evidence or live-model loop is used for release checks.
