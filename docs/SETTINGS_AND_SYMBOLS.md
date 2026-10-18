# Settings, analyzer overlays, and symbols

Settings uses the same authenticated loopback server as the case UI. The desktop
Settings menu opens `/settings.html`; browser mode can use the same page when a
settings manager is configured. Host, Origin, capability-cookie and CSP checks
still apply. No JS/native bridge is exposed by the settings controls.

Opening settings reads configuration and small settings metadata only. It does
not hash images, discover OSes, run analysis, or contact an AI provider. Provider
checks are explicit. Missing credentials never prevent settings or saved-case
browsing. The compatible-provider capability check uses synthetic tool content;
actual case content requires the explicit endpoint-specific checkbox. Settings
reports Blocked when the configured analyzer Python or Volatility entrypoint is
missing or nonexecutable; otherwise it reports Ready with limitations until exact
image/symbol and provider checks are requested.

The provider form defaults to **Default for new cases only**. Selecting a named
existing case explicitly switches that idle case to the chosen connection; earlier
provider sessions and evidence remain saved. **Start a new conversation** applies
only to the explicitly selected case and allows recovery from an interrupted
compatible-provider turn. Default-only saves do not switch existing cases.

## Locations and maintenance

The configured evidence folder is the default for relative paths and folder
browsing by default; Browse folder can switch among registered image folders.
It is not the only physical location an explicitly selected image may
use. Add evidence in Workbench by absolute path or the native picker, including
images on other mounted disks. **Registered image folders** in Settings lists
each unique image parent folder, unique image count and case count, alongside the
default folder. It refreshes from saved case metadata and survives reopening;
unmounted locations remain listed. Opening Settings does not hash or open images.

Each new case records its own evidence scope and exact selected-file allowlist.
Unrelated selections still create separate cases. Explicitly related images from
different folders can share one case; their common parent provides stable relative
identities internally, while the scoped MCP rejects every unregistered sibling.
Adding an image does not add or scan its entire folder, change the default MCP
configuration, copy evidence, or widen an existing case. Symlinks, traversal,
unsupported files and files in application outputs/state remain rejected.

Existing case roots cannot be changed from this screen. Empty setups can select physical evidence/output directories through
the desktop native picker or path entry. State remains in the configured private
state directory; this is not a migration tool. Symlinks are refused.

Changes require idle jobs. Settings maintenance also blocks new jobs. Runtime or
symbol configuration changes back up the original config and case MCP configs
under the private settings `backups/` directory, disconnect idle agent processes,
and update scoped runtime/symbol paths without changing case IDs, evidence paths,
report bundles, or state roots. Failure before activation preserves the previous
runtime. Keep the application open until maintenance finishes. Interrupted
operations are marked interrupted on next launch and never automatically retried.

The optional community installer creates a **fresh** venv at its final private
`runtimes/analyzer-<id>` location using the packaged standalone analyzer Python.
It installs the package's analyzer lock from its offline wheelhouse, preserves
pinned bundled pypykatz bytes, and invokes core's existing `plugins-install`
command for the explicit upstream downloads. It does not copy or rename a venv.
All subprocesses receive a restricted environment without provider credentials.
The candidate must discover every previously available plugin with no import
failures before config activation. Missing/unknown local additions therefore
prevent silently switching to a reduced inventory. Original analyzer files remain
unchanged. Failed candidates are removed; previous selected runtime remains.

This is same-user process separation, not a sandbox against malicious plugin code.
Community compatibility/licensing constraints remain in the authoritative core
[community profile](https://github.com/NoCoolUserName/volatility-mcp/blob/main/docs/COMMUNITY_PLUGINS.md).
The app bundle is never a mutable plugin destination.

## Small explicit symbol profile

`resources/symbols.json` is profile `starter-2026-10`, selected by the distribution
manifest. No symbol pack is downloaded by default. **Download all** means only
these two bounded, versioned packs:

| Pack | Source release | Download size | Actual scope |
| --- | --- | ---: | --- |
| Legacy Linux | Volatility Foundation test-data v0.0.1 | 2,980,184 bytes | Four exact CentOS/Debian historical kernel banners |
| Windows 10 | Same release | 789,065 bytes | One `ntkrnlmp.pdb` GUID/age, not every 19041 image |

The manifest records source URLs, release version, SHA-256, size, exact matching
identifiers and limitations. Sources:
[official release](https://github.com/volatilityfoundation/volatility3-test-data/releases/tag/v0.0.1)
and [published checksums](https://raw.githubusercontent.com/volatilityfoundation/volatility3-test-data/refs/tags/v0.0.1/symbols/SHA256SUMS).
The archives were downloaded, their identities inspected, and all five ISFs passed
Volatility 3's own schema validator. No memory image compatibility was tested.
They are optional upstream downloads, not redistributed symbol bytes in the app.

No macOS collection is presented as recommended. The upstream reports
[incomplete historical kernels](https://github.com/volatilityfoundation/volatility3/issues/155)
and [kernel type incompatibilities](https://github.com/volatilityfoundation/volatility3/issues/848)
remain reasons to require separately verified exact symbols. This does not claim
all current macOS symbol files are invalid. Local appropriate ISF imports remain
available.

Windows matching-symbol retrieval remains Volatility's normal exact PDB GUID/age
retrieval during an explicitly requested collection. Linux/macOS require exact
constant banners; a similarly named kernel is never accepted as a substitute.
Installed pack presence alone is not image readiness. Existing symbols and lookup
cache stay in their configured writable directories. No machine-specific lookup
cache is distributed, and Volatility rebuilds cache entries during normal use.
Offline analysis uses already available matching symbols; missing ones remain an
explicit readiness/collection failure.

Imports accept local `.json`, `.json.xz`, `.json.gz` or symbol-only ZIP files.
The original is unchanged. Decompression and member counts are bounded, absolute
paths/traversal/symlinks and non-ISF members are rejected, exact identifiers are
required, and OS-specific data is staged before atomic directory activation.
Mixed-OS archives must be split by OS. No unrelated symbol file is overwritten.
An immutable private receipt records source hash/size and derived file hashes and
identifiers. A repeated import reuses verified installed data; changed managed
bytes are rejected. Maximum input is 268.44 MB, each decoded ISF 268.44 MB, total
expanded archive 1.07 GB and 2,000 entries. These are operational limits, not a
claim that arbitrary compressed data is safe to trust.

HTTPS downloads use fixed profile URLs and verify final size and SHA-256. Partial
files are retained for explicit retry; HTTP Range is used when supported, and a
server that ignores Range restarts the download safely. Hash failures discard the
partial. Redirects may not downgrade to HTTP. Nothing crawls symbol servers.

## Focused validation

```sh
python -m unittest discover -s tests -p test_desktop_settings.py -v
node --check src/volatility_workbench/static/settings.js
```

Offline fixtures cover exact PDB/banner preservation, repeat imports, unchanged
sources, traversal/symlink/hash/size/decompression failures, altered managed files,
idle guards, roots with existing cases, private backups, interrupted maintenance,
secret-free subprocess environments, fresh-venv overlay paths, and install failure
rollback. These checks exercise setup contracts, not forensic detector accuracy.

A real ARM64 packaged-runtime check also created a fresh temporary managed overlay
from the application wheelhouse, ran the existing core pinned community installer,
and discovered 208 plugins with zero import failures (the redistributable bundled
baseline had 200). `pip check` reported no broken requirements. Bundled analyzer
source/data hashes were unchanged and deep/strict application signature verification
still passed afterwards. This exercised installation/discovery only: no memory
image was opened and no analysis tool was invoked. A real HTTPS retry from a
partial Windows symbol download passed the pinned byte-size/hash checks and
imported its exact PDB identifier into temporary storage.
