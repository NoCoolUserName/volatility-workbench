# Third-party notices

The existing MIT license applies to original project material, subject to the
unresolved integration scope described in [LICENSING.md](LICENSING.md). It does not
relicense separately installed dependencies, upstream Volatility material,
symbols, acquired evidence, reference publications, or other third-party works.

- **Official MCP Python SDK:** installed as a dependency, not vendored here.
  Preserve its [upstream license](https://github.com/modelcontextprotocol/python-sdk/blob/main/LICENSE)
  and those of its transitive dependencies in redistributed environments.
- **Volatility 3:** source is not vendored in this repository. The macOS app
  distribution bundles Volatility in a separate analyzer runtime.
  Its [Volatility Software License](https://github.com/volatilityfoundation/volatility3/blob/develop/LICENSE.txt)
  and notices remain applicable to upstream code and symbol material.
- **pefile:** pinned dependency for static inspection of saved PE artifacts,
  not vendored or used to execute recovered code. Preserve its
  [upstream MIT license](https://github.com/erocarrera/pefile/blob/master/LICENSE).
- **Historical XP structure references:** the local `xpnet.XpNetScan` addon retains
  its source links to official Volatility 2
  [TCP/IP layouts](https://github.com/volatilityfoundation/volatility/blob/master/volatility/plugins/overlays/windows/tcpip_vtypes.py),
  [connection pool checks](https://github.com/volatilityfoundation/volatility/blob/master/volatility/plugins/connscan.py),
  and [socket pool checks](https://github.com/volatilityfoundation/volatility/blob/master/volatility/plugins/sockscan.py).
  The upstream project has its own
  [license](https://github.com/volatilityfoundation/volatility/blob/master/LICENSE.txt).
  This addon is an independent local compatibility implementation and is not an
  upstream plugin or an endorsement by the Volatility Foundation.

No memory images, malware samples, symbol archives, commercial reference books,
or real investigation reports are distributed here. The example is original,
synthetic text. Product and organization names identify compatibility and context;
they do not imply sponsorship or endorsement.

Workbench was extracted from volatility-mcp commit `3ecc22e1275467879005556f5340fbc863bc3281`.
The original MIT copyright notice is retained. Core is an installed dependency, not vendored source.

## Application distribution

The macOS build also redistributes CPython, pywebview/Cocoa dependencies and selected
plugins. Preserve their exact-version licenses/notices alongside the application
and analyzer inventories. Packaging already copies Python and selected plugin
notices; verify the final artifact against all installed dependencies before release.

Theme artwork provenance is documented in docs/THEMES.md. The two Fallout 76
bezel PNGs were edited from supplied game references; their redistribution rights
are unverified and they must not be represented as cleared original art. Franchise
names, characters and recognizable motifs require a separate rights assessment.
For public distribution, clear the exact images for the intended use or use
independently created, non-derivative artwork or a build excluding those assets
and affected theme options. See LICENSING.md for the release checkpoint.

## Dependency evidence — 2026-10-18

[Dependency inventory](licenses/DEPENDENCIES.json) records exact versions, source commits, archive URLs/hashes, dependency context and review items. [Collected license texts](licenses/DEPENDENCY_LICENSES.txt) preserve upstream notices, including recovered omissions. This snapshot includes build/test and optional packages; it is not a claim that all listed components ship together or that a finished release has been cleared. Unlocked requirements are labeled audit-time resolutions, not new project pins. Refresh the inventory and verify actual release contents when dependencies change.

Unresolved upstream notice/conflict items: `proxy_tools@0.1.0` (license-conflict). These entries are not represented as cleared. Obtain matching upstream terms or exclude/replace the affected dependency before redistribution that requires them.

`proxy_tools==0.1.0` declares MIT in PyPI metadata but identifies BSD/Werkzeug in its source. The source attribution is preserved; the missing referenced BSD license and conflicting metadata remain an upstream clarification item. The macOS builder now copies the inventory and collected notices alongside the existing Python and plugin notices. This does not resolve the VSL integration review.
