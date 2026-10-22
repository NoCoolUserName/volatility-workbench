# Preparing a signed macOS release

Daily development remains ad-hoc signed. This is an explicit, optional release
pipeline for the ARM64 Mac application, not an App Store submission or automatic
publication workflow. No Apple credentials are required to develop or run its
offline checks. Actual Developer ID runtime behavior and Apple acceptance remain
unverified until a credentialed release is exercised.

## Prepare without Apple credentials

From the Workbench checkout:

```sh
python3 scripts/release_macos.py --help
python3 scripts/release_macos.py audit '/path/to/Volatility Workbench.app'
python3 scripts/release_macos.py notarize '/path/to/Volatility Workbench.app' \
  --output dist/releases/preview --dry-run
python3 -m unittest discover -s tests -p 'test_macos_*.py' -v
```

Audit reads an existing build and its file hashes, not memory evidence. It checks
bundle layout against this checkout's distribution profile, source provenance,
selected private filenames/extensions, symlink boundaries, addon receipts and
required notices. It rejects excluded community plugins. Dry run performs that
audit and prints the proposed stages, without creating the output directory,
signing, running the app, accessing Keychain, or contacting Apple. An ad-hoc build
can be inspected in dry run; that does not make it eligible for submission.

This is a focused packaging guard, **not an exhaustive secret scanner or a legal
license determination**. Review the actual inventory, new bundled dependencies,
upstream notices and licenses for each release. Dependencies can contain public
certificate/test-key fixtures; a `.pem` suffix alone does not identify a secret.
Never package cases, images, recovered binaries, reports, credentials, provider
settings or personal configuration. Only the reusable app bundle is submitted.

## One-time account preparation

1. Join an Apple Developer Program team and install a **Developer ID Application**
   identity, including its private key, in your login Keychain. An Apple Development
   identity, ad-hoc signature, or certificate without a private key is insufficient.
2. Install Apple's command-line signing/notarization tools; confirm `xcrun
   notarytool --help` and `xcrun stapler --help` work.
3. Store notarization credentials in Keychain using Apple's interactive prompt:

```sh
xcrun notarytool store-credentials WorkbenchNotary
security find-identity -v -p codesigning
```

Follow the credential prompts (for example, Apple ID, app-specific password and
team). An App Store Connect API key is another supported Apple authentication
option. This project's release command accepts only the stored profile name,
never a password or private-key argument. Do not commit signing private keys,
notarization credentials or exported certificates. CI credential provisioning is
deferred; this workflow runs locally and existing CI needs no Apple secrets.

## Build and release when ready

Commit source and use a clean checkout of the intended release revision. Keep the
version in `packaging/distribution.json` and Python package metadata consistent.
Every changed release binary must go through signing and notarization again.

```sh
python3 scripts/build_macos.py --output dist/macos \
  --sign-identity 'Developer ID Application: YOUR NAME (TEAMID)'
python3 scripts/release_macos.py audit 'dist/macos/Volatility Workbench.app'
python3 scripts/release_macos.py notarize 'dist/macos/Volatility Workbench.app' \
  --keychain-profile WorkbenchNotary \
  --output dist/releases/RELEASE-VERSION-COMMIT
```

A valid matching identity name or certificate SHA-1 is accepted. Identity lookup
happens before build downloads. `--allow-dirty` cannot be combined with a Developer
ID build. Ad-hoc signing remains the default when no identity is supplied.

The builder signs each actual Mach-O component explicitly, skipping interpreter
symlinks. Developer ID executables receive hardened runtime and a secure timestamp;
libraries receive a timestamp without executable entitlements. It updates package
RECORD hashes after native signing, then seals the outer app. It does not use
`codesign --deep` for signing; deep verification remains appropriate. No broad
runtime exceptions are enabled. Credentialed testing may reveal a need for narrow
entitlements for Python/Cocoa callbacks or optional native plugin dependencies;
those must be justified and tested before advertising a signed release as usable.

The notarization command:

- Audits the build, rejects ad-hoc provenance and verifies every native signature's
  Developer ID authority, timestamp and common team. Executables require hardened
  runtime and must not enable debugger attachment.
- Copies the app to a **new** output directory; it never changes the source or
  installed app and refuses to overwrite a previous release directory.
- Repeats the audit and signature/team checks on that staged copy before upload.
- Creates `submission.zip` and explicitly uploads that app archive to Apple using
  `notarytool --wait` (30-minute service wait, bounded subprocess timeout).
- Requires Apple's `Accepted` status, saves the submission/log, staples and
  validates the ticket on the staged `.app`, verifies signatures and assesses
  Gatekeeper, then creates the final archive **after stapling**.
- Saves relative file paths/hashes in `bundle-inventory.json` and a
  `release-status.json` receipt with build identity, submission ID, timestamps,
  status, signing team and final archive SHA-256. Failures/interruption remain
  `incomplete`, with the current step and diagnostic logs. An interrupted upload
  may still be processing at Apple; inspect its saved submission output or
  `notarytool history --keychain-profile WorkbenchNotary` before resubmitting.

Share only `Volatility-Workbench-macos-arm64-notarized.zip` from a release whose
receipt is `complete`, plus its checksum and release notes. Keep submission
archives and detailed local logs private. Build metadata inside the signed bundle
retains `notarized: false`: it records the pre-submission build state and is never
rewritten after signing. The external release receipt and stapled ticket establish
notarization; no flag in a JSON file substitutes for ticket validation.

## Final release checks and scope

Publish the matching Workbench and pinned MCP source under VSL when distributing
the application. Include the source links/revisions from `notices/SOURCE_CODE.json`
in the release notes and verify public access without a GitHub login. If the
development repository is private, publish a reviewed source archive or a public
source repository for that exact revision. The bundle carries both project license
texts and core notices; the audit checks their presence and matching revisions,
but does not certify public source availability or third-party artwork rights.
The project license grants are in [LICENSING.md](../LICENSING.md); no advance
Foundation approval is required for distribution under the existing VSL.

Before publishing a GitHub release, download the final archive on another Mac,
extract it normally and verify Gatekeeper launch with quarantine retained. Test
first-run setup, native window, plugin catalog, harmless analysis, and idle quit/
reopen with private settings outside the bundle. Test offline ticket availability
where practical. Record host macOS/architecture and results; do not infer Intel,
Windows or container support from this ARM64 release. Do not disable Gatekeeper.
The script's automated assessment does not replace this downloaded-app test.

The archive contains the main app and a signed nested helper executable. The
optional installer still constructs a **local ad-hoc** Desktop shortcut containing
the user's installation path; it is not a separately notarized downloadable app.
No installer or `.pkg` is distributed by this pipeline. Opening or moving the main
app does not require that shortcut. Existing installed apps, case storage and
active work are never replaced or restarted by the release command.

Offline fixtures exercise command ordering, credential rejection, component types,
privacy/layout guards, rejection/interruption handling and final success gating.
They simulate Apple services; they do not establish successful notarization or
hardened-runtime compatibility. See [actual validation](../packaging/VALIDATION.md).

References: [Apple distribution signing](https://developer.apple.com/documentation/xcode/creating-distribution-signed-code-for-the-mac/),
[notarization workflow](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow),
and [packaging for distribution](https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution).
