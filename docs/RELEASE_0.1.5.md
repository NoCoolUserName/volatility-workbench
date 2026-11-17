# Workbench 0.1.5 — Linux Keyring integration

Experimental macOS ARM64 prerelease, ad-hoc signed.

- Includes the attributed MIT Linux Keyring addon from mischw/volatility3_plugins, adapted for bounded traversal and payload reads, explicit incomplete-scan failures, UTC timestamps and layer/address provenance.
- Keyring is eligible for authorized automatic Linux investigations and report suggestions, with normal analyzer symbol/network behavior and no separate extraction prompt.
- Includes the current core-updater authentication fix and the existing report, concurrency and interface improvements merged since 0.1.4.

The bundled MCP remains version 0.1.4, pinned to source revision 128625bc2ee8850f76ba257e0ffe80dccbbef95d. Its full symbol wheel was built locally from that published source; the distribution profile records its exact hash. To reproduce this build, pass that matching full wheel with --core-wheel as described in packaging/README.md.

Keyring supports Linux Intel64 and selected user/logon/asymmetric payloads with matching kernel symbols. It does not guarantee volume decryption or recovery of every key type. Real Linux-image recovery remains unvalidated; checks use synthetic fixtures.

The app is ad-hoc signed and is not Apple notarized. Broader clean-Mac acceptance remains outstanding. The ARM64 host app does not imply support for Apple-silicon memory captures.
