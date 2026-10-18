# macOS packaging validation

The following checks were performed on an ARM64 Mac with macOS 26.4.1. They
exercise the packaged runtime; native-window interaction is recorded separately
in the Workbench UI validation documentation.

- Nine deterministic offline packaging tests pass: lock/inventory references,
  corrupt cached download rejection and atomic activation, archive traversal
  rejection, dirty-build installation refusal, active bundled-process refusal,
  simulated installation rollback after activation failure, real launcher layout/target/icon and deferred old-launcher removal, launcher activation rollback, and symlink refusal. A compiled Cocoa helper also resolved its temporary app target successfully without opening it.
- A complete application and ZIP were built from fresh, hash-pinned standalone
  CPython 3.12.15 runtimes, independent app/analyzer package environments and exact
  dependency locks. No development virtualenv was copied. The candidate carried
  an explicit uncommitted-source label; release installation requires a clean
  commit and records its exact revision.
- The embedded native executable's fixed runtime self-check passed with no LANG
  variable, a minimal PATH, and a temporary HOME/cwd. UTF-8 source labels survive
  a real subprocess round trip. Bundled Python import paths remain within the
  application, with runtime bytecode writes disabled.
- The actual bundled core revision matches the immutable pin, including VCS
  provenance. Native imports for Capstone, YARA, cryptography support, Pillow,
  EVTX and pypykatz passed. The bundled catalog discovers **200 plugins** and no
  import failures: 197 official plus XP compatibility, pypykatz and EVTX. Source
  attribution remains native/community/local. These numbers describe this build.
- The official MCP SDK initialized a real bundled stdio server and called its
  catalog tool. A synthetic byte file exercised one real `banners.Banners`
  subprocess per validator run and recovered its expected test string. No private
  memory image, recovered executable, real investigation or model service was
  used by this validator.
- The `.app` path includes spaces. Native libraries require system paths or
  bundle-relative dependencies; a dylib's own identifier is checked separately
  from a dependency load path. Strict/deep signature verification passes **after**
  runtime imports, catalog discovery, MCP and fixture execution, confirming that
  these operations did not alter sealed bundle resources.

Concrete defects found and repaired: Python's isolated mode ignores the
`PYTHONDONTWRITEBYTECODE` environment variable, so prebuilt bootstrap caches and
an installed site hook now prevent bytecode mutations. Finder's missing shell
locale initially caused ASCII decoding of Unicode catalog labels; the native
launcher now initializes UTF-8 before CPython starts and has a direct regression
check. The validator initially mistook universal Mach-O architecture headers and
YARA's own dylib identifier for loaded external libraries; it now inspects those
separately while continuing to reject external build-library dependencies.

Installed distribution RECORD entries are recomputed after relocatable entrypoint
normalization and native signing. Only existing RECORD members are updated, so
additional plugins are not falsely promoted to official Volatility files.
Original wheel hashes and upstream notices remain available for provenance.

Local signing is ad-hoc. No Developer ID signing or notarization was performed.
Synthetic import/contract checks do not establish forensic accuracy, correctness
on real memory images, or support for every OS/kernel. Windows/container builds
and a public notarized release remain untested. The optional community profile
retains explicit upstream download because selected upstream license/source
obligations are unresolved for public bundling.
