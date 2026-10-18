# Workbench roadmap

This is the remaining-work list, reviewed against current main on 18 October 2026.
Completed features and rollouts are recorded in [LOCAL_UI.md](LOCAL_UI.md),
[UI_VALIDATION.md](UI_VALIDATION.md) and [packaging validation](../packaging/VALIDATION.md).
Remove completed items here when acceptance evidence is recorded there; keep
unverified platform, forensic and release claims explicit.

Workbench owns application controls, model adapters, jobs, case navigation,
report presentation and distribution. Core owns forensic adapters, the single
addon inventory, execution policy, symbols, provenance and accuracy evaluation.
Use the public core API and existing catalog; do not duplicate upstream plugin
implementations or inventory policy in this repository.

## Release and usability priorities

| Priority | Remaining Workbench work | Acceptance check |
| --- | --- | --- |
| 1 | Complete one end-to-end acceptance run of the current distributable on a clean user account or second Mac. Existing developer-Mac and synthetic checks do not establish that environment. | From a fresh install, register an authorized harmless fixture, check readiness, generate a report, ask a follow-up, revise it, quit and reopen. Verify preserved case/session identity, saved consoles, citations and report selection, with no duplicate analysis. Record exact app/core revisions, OS and results. |
| 2 | Improve and measure interruption/resource behavior where forced process death, long hashing/conversion and unbounded stored output still limit reliability. Coordinate analyzer changes with core. | Bounded large fixtures for Stop latency, forced termination/restart and descendant cleanup; preserve completed evidence and mark unfinished work. Add a documented storage quota or warning/cleanup design that never silently removes evidence or sealed reports. |
| 3 | Validate accessibility and interaction beyond the existing browser/theme fixtures. | Keyboard-only and assistive-technology review of case/report navigation, error review, Settings and VolShell; selected browser/WebView and narrow-screen checks. Preserve readable evidence surfaces, focus, reduced-motion behavior and status semantics across themes. |
| 4 | Complete credentialed macOS release acceptance. Build, auditing and signing/notarization machinery already exist. | Authorized Developer ID signing, notarization/stapling, and downloaded-app Gatekeeper testing on a second Mac with quarantine intact; record exact artifact hashes and outcomes. Ad-hoc signing and simulated Apple responses do not close this item. |
| 5 | Establish a distribution licensing decision before expanding the portable plugin baseline. Dependency inventories and bundled license notices already exist. | Resolve the questions in [LICENSING.md](../LICENSING.md) with core; align covered paths, metadata, notices and source obligations. Retain the current allowlist until each added source is eligible. Local installation and public redistribution are different decisions. |

No existing private case or saved investigation is authorized as a fixture by this
roadmap. Routine UI tests use synthetic state and simulated providers; any acceptance
run involving an image or live provider needs a specifically authorized fixture and
bounded scope. Preserve original evidence, existing cases and sealed revisions.

## Forensic validation dependencies — core owns the work

The [core roadmap](https://github.com/NoCoolUserName/volatility-mcp/blob/main/docs/ROADMAP.md)
tracks the following acceptance work. Workbench consumes the resulting catalog,
limitations and evidence; importable command counts are not a support matrix.

| Dependency | Gate before broader application claims or collection defaults |
| --- | --- |
| OS/build accuracy campaign | Explicitly authorized representative Windows/Linux images with matching symbols, known positive/negative artifacts, expected source offsets and measured byte/time/output costs. Preserve unsupported, incomplete and error outcomes separately from valid empty results. |
| BitLocker | Establish Windows pool-layout coverage and independently known key roles/cipher modes. AES schedule candidates currently do not establish FVEK/tweak identity, BitLocker use or decryptability; raw-key/decryption-schedule variants need separate fixtures. |
| Go | Validate selected Windows/Linux AMD64 builds and Go versions: current 1.16–1.25 gates, with heap/string modes starting at 1.18, are candidate layouts. Measure typed-heap, strings, functions and goroutine/frame coverage before widening claims. |
| Python | Validate the exact pinned CPython 3.8 research layout with known runtime/object/frame addresses. Other builds/versions, frozen/permanent-generation and untracked-object coverage remain separate work; raw target bytecode must remain inert. |
| Sensitive recovery | Validate fabricated known credentials/keys, false matches and output handling. PasswordManager is eligible for relevant authorized automatic investigation with an explicit browser PID; SSHKeys remains manual with a PID/address. Honor the core catalog policy for other sensitive/runtime commands. |
| Deferred candidates | Separate core changes for SwapEnumerator (bounded PTE/PFN work), parent-spoof checks (independent heuristic accuracy), Docker (namespace/cgroup/symbol adapters and rights), and alternate EVTX (correct parsing, offsets, dependencies and comparative recovery). Keep PFNInfo/P2V/RamMap and WinObj deferred pending justification; CryptoScan needs an offline redesign first. |

When the core publishes measured compatibility results, assess a concise UI view
of the selected build/runtime prerequisites and known gaps. Reuse the existing
catalog and coverage contracts instead of inventing a Workbench-only compatibility
database. Updating a core pin or refreshing the catalog does not authorize a sweep.

## Proposed investigation modes — not implemented

| Mode | Remaining design and acceptance work |
| --- | --- |
| Quick triage | Define versioned OS-specific profiles using measured cost and human-reviewed lead yield on authorized benign/malicious fixtures. Start with OS/symbol readiness and bounded process/command-line/network/module observations; follow justified anomalies within a declared time/output budget. Preserve leads, citations and gaps without presenting a clean verdict. |
| Compatibility sweep ("Run all applicable plugins") | Define an explicit diagnostic job that sequentially attempts suitable commands with satisfiable arguments/prerequisites. Record success, valid empty, skipped, unsupported, failure, duration, integrity-hashing cost, reuse and output volume separately. Require explicit inclusion for commands whose core policy is manual-only; apply bounded extraction/expensive-operation settings. |

These are proposed controls, not permission to execute them. Installation alone
does not establish applicability: PID/address/rules, runtime layouts and matching
symbols may be required. A future profile must respect the authorized case scope
and core's current per-command policy, including PasswordManager's permitted
automatic use and SSHKeys' manual restriction. Do not tune profiles only to known
malware names or use installed-plugin count as a coverage denominator.

## Later, with an identified use case

- Evaluate polished report exports against authorized representative reports while
  preserving citation links, limitations, revision provenance and sealed originals.
- Add provider protocols or model/effort controls only after defining their actual
  capability, provenance, secret-storage and interruption contracts. The existing
  compatible tool API and provider usage display do not imply support for every API.
- Evaluate parallel analysis only after measuring evidence/output locking, resource
  contention, cancellation and result-reuse behavior; sequential jobs remain the
  baseline.
- Scope Intel macOS, Windows and container distributions separately. A container
  must pin the official analyzer dependency profile, use core's inventory and
  license policy, and validate imports plus harmless runtime fixtures. Keep optional
  cloud/Arrow and browser-test dependencies separate. Do not silently install
  dependencies through the UI.
- Coordinate independent model-answer/report accuracy evaluation with core using
  authorized saved-evidence sets. Check citation values, unsupported conclusions,
  uncertainty and abstentions separately from UI/contract test pass rates.
