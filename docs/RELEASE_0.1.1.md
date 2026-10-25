# Workbench 0.1.1

Adopts core 0.1.2 and its pinned CryptoMem 0.3.0 release. Linux x86-64
memory-image analysis is available through the existing MCP discovery and
execution tools. Windows command/output behavior is preserved. Both CryptoMem
commands remain available when the legacy Windows XP add-on is disabled.

The backend contains a pinned catalog and explicit installer for 10,255 community
Linux x86-64 symbol tables. Installed tables use the existing configured symbol
store and offline index; the 19.53 GiB collection is not copied into the app
bundle or redownloaded during app upgrades. The existing four official starter
packs remain bundled. Exact captured-kernel symbols are required, and other
Linux architectures remain unsupported until tested.

Validation uses synthetic fixtures and real installed analyzer/MCP invocations,
including a clearly failed Linux scan with unsatisfied kernel/symbol requirements.
A successful empty result is not substituted for missing symbols. No private
images are opened or uploaded. Real-memory Linux CryptoMem validation remains
outstanding. This release does not add a Linux desktop build or redesign the UI.

Local macOS arm64 packaging is ad-hoc signed unless built separately with a valid
Developer ID identity and notarized. Ad-hoc validation is not notarization.

The local macOS arm64 build passed native runtime/dependency checks, first-run
provisioning of all four packs with network access blocked, discovery of both
CryptoMem 0.3.0 commands with XP enabled/disabled, actual ten-tool MCP discovery
and a synthetic Linux missing-kernel failure, input-integrity checks, signature
verification and native library linkage checks. The app catalog contains 202
commands with zero import failures. The installed Python package suite passed
272 tests. No real memory image was used.

Artifact source: `8015921c801dd80036321dc61c28062ad4969026` (the subsequent README
size stamp is documentation only). Backend release source:
`5e3affb9c9fcf1be2e6b463194cef488518c7ff6`. The native artifact uses CPython 3.12.15,
Volatility 2.28.2, CryptoMem 0.3.0 and MCP 2.3.0. It is ad-hoc signed and has not
been Apple-notarized.
