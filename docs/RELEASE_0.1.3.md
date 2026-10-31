# Workbench 0.1.3 backend adoption

Workbench 0.1.3 aligns the MCP source pin and release wheel at MCP 0.1.4
(`2887c77283da4a45860d8ac2f3042027401257a0`), including CryptoMem 0.5.0
(`69f8d1f0c94b51b19da6de810e2b57a33df3d9c9`). The core wheel SHA-256 is
`339dd2bb671893c9a3c5606486c4b9e7cbb824b86fd125d9980a4c86ae329975`.
Existing UI assets, address defaults, OS adapters and ten MCP tools remain.

Opt-in detectors cover English BIP-39 (12/15/18/21/24 words with normalization
and checksum), Bitcoin WIF and BIP-32 xprv/tprv. A checksum-valid phrase or key
in memory does not establish wallet ownership or control. A 64-hex transaction-ID
candidate has explicit confidence and ambiguity; it does not establish a chain,
confirmation, payment, balance or history. Ordinary results mask secrets; complete
values require explicit local extraction in private case outputs. No online
enrichment, wallet import or transaction operations are added.

## Validation and provenance

- Isolated installed-package smoke and all 272 application tests passed using
  Python 3.12.13; 29 focused macOS and 11 security tests also passed after updating
  native validator expectations to CryptoMem 0.5.0.
- Native ARM64 Python 3.12.15, Volatility 2.28.2 and MCP SDK 2.3.0: clean imports,
  203 catalog plugins, three CryptoMem commands, ten-tool MCP discovery,
  synthetic invalid-image invocations and explicit missing-symbol failures.
- Actual installed CryptoMem detector through MCP transport: synthetic
  process buffers for Windows/Linux/macOS, XP on/off, secret masking, local-only
  extraction/read guards, timeout and cancellation. No private evidence was used.
- Native launcher, bundled assets, both Adventure editions, source/wheel/notice
  hashes, signature and system-or-bundle-relative linkage passed. Fresh-home
  provisioning verified four bundled symbol packs with downloads blocked.
- The additional 10,255-table Linux collection finished indexing separately.
  Successful exit, ready receipt, pinned catalog metadata and all 10,255 verified
  table entries were checked. The collection is outside the native application;
  exact captured-kernel symbols are always required.

Measured 2026-10-25 from clean source `acdf84a6c4e482a3bbdac3392f11a574545db15c`:
`Volatility Workbench.app` has 1,352,402,393 regular-file bytes (1289.751428 MiB),
excluding symlink aliases. `Volatility-Workbench-macos-arm64.zip` has 1,126,118,069
bytes (1073.949880 MiB), SHA-256 `16d5a6def6762522d720c87c3f1f9ef0ec6b600a916bb2bd34236a274d2206dd`.
The later README measurement commit does not require a recursive rebuild.

## Remaining limits

The native package remains an ad-hoc signed prerelease, without Developer ID
signing or Apple notarization. Real-memory Linux and macOS validation remains
outstanding; only synthetic/public fixtures were used. macOS nested submaps,
Intel32, Apple-silicon captures and modern macOS remain unsupported; the ARM64
application host does not imply ARM64 capture support. Other mnemonic languages,
non-BIP-39 schemes, encrypted or unrelated private-key formats, arbitrary raw
32-byte keys, transaction parsing and online services are outside this increment.
