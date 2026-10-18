# Community3 candidate plugin review

Review date: 18 October 2026. Workbench main: `75ee7770691548ce6a3f5e05e3bcd219617944e1`. Analyzer: Volatility 3 `2.28.2` on arm64. Refreshed installed catalog: **208 commands, zero import failures**.

All **14 community3 projects** are accounted for. Their checked sources and linked author repositories yield **39 source-defined command entries** after removing alternate copies and Volatility 2 code. Of these, **14 are potentially new analysis commands** and **one is an alternative EVTX analyzer**. The remainder are existing commands, overlapping support/detection, GUI entry points, or orchestration. Acquisition layers, the symbol generator/server, and the Syslog renderer are recorded separately because they are not analyzer commands.

The best first adaptation batch is **CobaltStrike, RichHeader, ZoneID3, and PteResolve**. This is a proposal based on static review, not a compatibility result. Keep the current 208 intact. Integration belongs in the core community inventory, with Workbench consuming discovery through its existing public API.

## Baseline and source scope

Local main and GitHub main both resolve to `75ee777`. The checkout was clean before review. The selected-report highlight is therefore part of the baseline. Quick triage and compatibility sweep remain proposals; this review does not implement buttons or authorize a sweep.

The current catalog contains:

| Source | Commands |
| --- | ---: |
| Official Volatility 3 | 197 |
| f-block/volatility-plugins | 4 |
| forensicxlab/volatility3_plugins | 3 |
| skelsec/pypykatz-volatility3 | 1 |
| aynaitlamine/volatility3-browser-history | 1 |
| spitfirerxf/vol3-plugins | 1 |
| Local volatility-mcp XP network addon | 1 |
| Total | 208 |

Catalog refresh completed at `2026-10-18 09:11:30Z`. These counts describe discovery, including deprecated aliases; they do not measure distinct forensic coverage or real-image support. The separate public app bundle's documented 200-command catalog is not the baseline for this comparison.

[Community3](https://github.com/volatilityfoundation/community3/tree/5ae4e232e14667277a0cc74848b87b634b4d8ad1) resolves to `5ae4e232e14667277a0cc74848b87b634b4d8ad1`, last committed on 18 February 2022. It is an old contest collection, not a current compatibility manifest. Its README directs readers to author repositories and expressly leaves currency, compatibility, and accuracy unverified. This review follows those links and pins the public source fetched on the review date. ZoneID3, PteResolve, and SwapEnumerator were found in the linked author repositories beyond the obvious contest descriptions.

## Every community3 project

| Project directory | Difference from the installed catalog | Disposition |
| --- | --- | --- |
| Block_PTE_Malfind | PteMalfind, SimplePteEnumerator, ImageMalfind and ApiSearch are installed. PteResolve and SwapEnumerator are absent. | Retain the four installed commands; evaluate the two additions from the same pinned upstream revision. |
| Breen_LastPass_ISF_Rich_CS | CobaltStrike, RichHeader and PasswordManager are absent. The linked author repository also has ZoneID3. Symbol generation/server infrastructure is separate. | Collect all four Volatility 3 candidates; keep credentials opt-in and symbol infrastructure outside plugin counts. |
| Chechik_Weber_CheckSpoof | Check_parent_spoof is absent. Check_peb_spoof overlaps native PebMasquerade. | Evaluate parent checks; compare PEB edge cases before adding a second implementation. |
| Gerhart_Hyper_V | Live Hyper-V layer, hvlib wrapper and stacker changes; not a new analysis command. | Exclude from the current macOS/offline profile. |
| Guyard_VolWeb | Separate web platform; current upstream includes four Linux/Windows VolWebMain/VolWebMisc command wrappers. | Record for architectural reference; do not import its database/application workflow. |
| Moreira_Mountinfo | Native linux.mountinfo.MountInfo is installed. | Retain modern native support; do not copy old symbol extension replacements. |
| Moreira_Netfilter | Native linux.malware.netfilter.Netfilter and deprecated linux.netfilter.Netfilter are installed. | Retain native support; the embedded ZIP is historical source. |
| Sheffer_Shaked_Docker | Docker container interpretation is absent; five supporting plugins overlap or replace existing facilities. | Port the container-specific logic only after dependency and namespace review. |
| Silva_Multi_Yara | Multiple rule-repository management and CSV output around existing YARA scanning. | Retain the idea for a separate rule-management design; reject the current drop-in implementation. |
| Stelte_Evtx | EvtxLogs uses EVTXtract raw-image carving; installed windows.evtxlog.evtxlog reconstructs/parses cached EVTX files. | Compare as complementary recovery strategies; do not replace the installed EVTXLog command. |
| Stelte_Syslog | Output renderer/CLI wrappers transmit result data over UDP. | Exclude from the analyzer profile; evidence export would be a separate explicit feature. |
| Team_BTC_Cryptoscan | CryptoScan is absent; bundled PsList/Memmap variants overlap native commands. | Consider an offline extraction port only after separating network enrichment and PDF production. |
| Vergeer_OpenSSH | Linux SSHKeys session-key extraction is absent. | Evaluate as explicit sensitive extraction, including the supplied OpenSSH symbol schemas. |
| Zohar_VolExp | P2V, PFNInfo, RamMap and WinObj are absent; five other entries open or support a GUI. | Evaluate headless analysis separately; exclude GUI wrappers. Vol3xp means Explorer, not a promise of Windows XP support. |

Directory names above correspond to the [pinned community3 tree](https://github.com/volatilityfoundation/community3/tree/5ae4e232e14667277a0cc74848b87b634b4d8ad1). Exact source paths, class definitions, requirements, imports and hashes are in `candidate-inventory.json` and `upstream-manifests.json` in the review bundle.

## Potentially new analysis commands

Names in this table are **source class names**, not newly discovered installed commands or finalized installation namespaces.

| Source class | Potential additional value | Main adaptation and evaluation work | Suggested order |
| --- | --- | --- | --- |
| CobaltStrike | Decode selected Beacon configuration fields from process memory. | Update old Windows PsList arguments; bound scans and malformed configuration parsing; test supported encodings/versions and benign lookalikes. YARA matching alone is not a confirmed finding. | First |
| RichHeader | Recover Rich Header XOR keys and hashes for executable comparison and clustering. | Update PsList calls; bound PE reconstruction; validate header/hash results against known synthetic headers. Hash differences alone do not establish maliciousness. | First |
| ZoneID3 | Recover Zone.Identifier host/referrer URL fragments as download provenance leads. | Preserve hit offsets in output; handle malformed encodings and truncated reads; validate YARA pattern semantics. A memory fragment does not establish an intact ADS or its owning file. | First |
| PteResolve | Targeted virtual-address/PTE interpretation, complementing installed PTE scanning. | Reuse the installed Ptenum adaptation; enforce a meaningful address/PTE input; retain Intel64 support limits and test returned page states. | First |
| SwapEnumerator | Summaries and filtering of software PTEs and pagefile references. | Remove/reconcile legacy nt_symbols requirement; bound PID/address scope and counting cost; reuse adapted Ptenum. It does not itself supply missing pagefile contents. | Second |
| Check_parent_spoof | Compare inherited parent IDs with OwnerProcessId-based leads. | Port legacy imports/kernel APIs. Source restricts itself to Windows 8+ and relies on hard-coded minus-two/minus-one PID adjustments plus AppInfo/conhost exclusions; validate these assumptions across supported builds. | Second |
| Docker | Interpret containers, privilege/capabilities, mounts and networks from Linux namespace data. | Replace dependencies on old framework extensions with compatible helpers. Validate cgroup/kernel/container combinations and negative cases; daemon/container heuristics are not a general container inventory guarantee. | Second |
| PasswordManager | Recover LastPass-style browser fragments, distinct from installed KeePass and pypykatz. | Port PsList, improve decoding and provenance, bound reads, and prevent secrets in debug logs. Source signatures target limited browser names and historical formats. | Explicit sensitive extraction |
| SSHKeys | Recover Linux OpenSSH session cipher/key/IV structures. | Ship both supplied ISFs; adapt the old Linux PsList version requirement; fix the empty PID/name filter, which currently excludes all tasks; constrain the arbitrary --out write. | Explicit sensitive extraction |
| WinObj | Enumerate the Windows object-manager namespace. | Adapt old Handles signatures and redundant symbol requirements; review traversal bounds, malformed pointers and object type decoding. | Later |
| P2V | Relate a physical page to virtual mappings and possible owning processes. | Port legacy process/kernel calls; validate PFN/layout interpretation and address argument parsing with multiple Windows layouts. | Later |
| PFNInfo | Inspect PFN database page use and related metadata. | Same large PFN source and kernel-specific assumptions as P2V; validate incomplete/corrupt states and keep missing metadata explicit. | Later |
| RamMap | Summarize physical-page use, using PFN/P2V logic. | Bound full-memory enumeration; separate heuristic suspicious-page labels from established observations; port shared APIs before considering cost. | Later |
| CryptoScan | Recover cryptocurrency-related memory fragments. | Split offline extraction from external requests and PDF formatting; remove hard-coded paths, scope dumps, and verify pattern false positives. Current code transmits recovered addresses/transaction IDs to external services. | Substantial redesign |

The first four draw from [Kevin Breen's plugins](https://github.com/kevthehermit/volatility_plugins/tree/0f4f2fbbc93b8b59ead45f82e3287859a5ebc469/vol3) and [f-block's source](https://github.com/f-block/volatility-plugins/tree/c4b6ad45ce34f0b7eae9aef80dd6e9594e8c5b84). Other candidate sources are [CheckSpoof](https://github.com/orchechik/check_spoof/tree/0a6ee712006f3cac5af38509345aa4710d256ab5), [Docker](https://github.com/volatilityfoundation/community3/tree/5ae4e232e14667277a0cc74848b87b634b4d8ad1/Sheffer_Shaked_Docker), [OpenSSH](https://github.com/fox-it/OpenSSH-Session-Key-Recovery/tree/78f7955b1e1fccb4b1a7e2382e0ed5a7c8becea3), [Vol3xp](https://github.com/memoryforensics1/Vol3xp/tree/216e936ce560c78704e467ab90d1863e881ea381), and [CryptoScan](https://github.com/BoB10th-BTC/CryptoScan/tree/9588ff800ba625f7ef044ddb98a23013810fbf29).

### Alternative EVTX analysis

`EvtxLogs` is a fifteenth analysis entry to assess, with substantial overlap in purpose rather than an identical implementation. [Stelte's source](https://github.com/volatilityfoundation/community3/blob/5ae4e232e14667277a0cc74848b87b634b4d8ad1/Stelte_Evtx/evtx.py) scans the underlying image file for EVTX chunks/records/templates through EVTXtract. It could recover records that are unavailable through cached-file reconstruction, but that benefit is unmeasured here.

It uses the old `volatility` import namespace, missing `evtxtract` and `requests` dependencies, brittle string manipulation of the input location, raw mmap access rather than normal layer iteration, and broad exception suppression. Template/rescan work is nested inside a chunk loop, so cost needs attention. Provider-column population also needs review: the yielded value is taken from Keywords. Preserve recovered physical offsets, validity status and parsing failures, and keep raw-file assumptions explicit for transformed or layered inputs. Both existing and proposed EVTX support concern EVTX, not XP EVT.

## Overlaps and entries excluded from an additive plugin count

| Category | Source command entries | Reason |
| --- | ---: | --- |
| Already installed source entries | 6 | Four f-block commands, MountInfo and Netfilter. Netfilter has two installed names; these are not two independent new capabilities. |
| Potentially new analysis | 14 | Listed individually above; usability and accuracy remain unevaluated. |
| Overlapping PEB analysis | 1 | Check_peb_spoof versus native windows.malware.pebmasquerade.PebMasquerade. |
| Alternative EVTX analysis | 1 | EvtxLogs versus installed windows.evtxlog.evtxlog. |
| Overlapping support | 3 | Docker's Mount, Ifconfig and ListFiles overlap native mountinfo, ip, pagecache and lsof facilities; namespace details still require comparison. |
| Native command replacements | 4 | Docker PsList/PsTree and CryptoScan PsList/Memmap must not overwrite current native implementations. |
| YARA orchestration | 1 | MultiYara wraps rule collection and existing scanning. |
| VolWeb orchestration | 4 | Linux/Windows VolWebMain and VolWebMisc depend on VolWeb's Django models, configuration and result storage. |
| Explorer GUI entry points | 5 | Vol3xp, HandleXViewGui, StructAnalyzer, WinObjGui and FileScanGui are unsuitable for unattended analyzer jobs. |
| Total | 39 | Source entries after deduplication, not a projected installed count. |

Native PebMasquerade already exposes EPROCESS/PEB information and flags PEB string-length anomalies. The older Check_peb_spoof explicitly compares truncated basenames; these are overlapping approaches, not proven interchangeable detectors. Test useful differences before carrying both.

[MultiYara](https://github.com/volatilityfoundation/community3/blob/5ae4e232e14667277a0cc74848b87b634b4d8ad1/Silva_Multi_Yara/multiyara.py) prints during class definition, uses absolute rule paths, can clone/pull moving rule repositories during execution, and writes CSVs in the working directory. Its `_generator` contains no yield and returns None rather than TreeGrid rows. An acceptable future design would keep pinned rule acquisition outside analysis and use existing YARA support with bounded output.

[Hyper-V](https://github.com/volatilityfoundation/community3/tree/5ae4e232e14667277a0cc74848b87b634b4d8ad1/Gerhart_Hyper_V) requires Windows-specific native components, `msvcrt`, and framework layer/stacker integration. The DLL/driver are not supplied in this collection. [Syslog](https://github.com/volatilityfoundation/community3/tree/5ae4e232e14667277a0cc74848b87b634b4d8ad1/Stelte_Syslog) sends rendered results to a network destination. Neither belongs in an automatic offline analysis profile.

The [symbol generator](https://github.com/kevthehermit/volatility_symbols/tree/f61a60fa8a6e4bc23341ccbe1a69de1e9e5f456f) downloads distribution/kernel packages and invokes build/conversion tools. It is possible future symbol-management infrastructure, not an analysis command. No symbol server, recovered endpoint, rule repository, or enrichment service was contacted for this review; network access was limited to GitHub source retrieval.

## Compatibility and source terms

The installed Windows PsList API accepts `kernel_module_name`; several candidates still pass `layer_name` and `symbol_table`. This is a concrete source-level incompatibility. Modern Linux PsList is version `4.1.1`; SSHKeys requests the old major version `2.2.0` and needs API/requirement review. Source parsing alone cannot establish compatibility.

Installed dependencies include `yara-python 4.5.4`, `capstone 5.0.9`, `pefile 2024.8.26`, `future 1.0.0`, `python-evtx 0.8.1`, and `hexdump 3.3`. Package metadata shows `requests`, `pygit2`, `evtxtract`, `reportlab` and `pyenchant` absent from this analyzer. Do not install those merely to increase discovery counts: separate optional functionality and identify exact packages/versions first.

| Source | Observed notices or repository license metadata | Integration implication |
| --- | --- | --- |
| Immersive Labs / Kevin Breen plugins | MIT license files; original CobaltStrike source retains an inline MIT attribution. | Preserve original notices. RichHeader copies are byte-identical; the inspected CobaltStrike copies differ only by the removed header. Keep one implementation. |
| CheckSpoof | GPL v3 license file plus copied framework notices. | Review source and redistribution obligations before public bundling. |
| OpenSSH | Apache 2.0 license file. | Retain license/notices and review included symbol schemas. The repository's separate live ptrace tool is outside this integration. |
| f-block | Per-file MIT/BSD notices and mixed obligations already documented by core. | Reuse the existing inventory policy; two extra files do not change licensing of their shared dependencies. |
| Stelte EVTX | Apache 2.0 header and incorporated-code attribution. | Review EVTXtract and transitive dependencies separately. |
| MountInfo / Netfilter | Volatility Software License headers in historical source. | Use the installed official implementations. |
| VolWeb | GPL v3 LICENCE file. | Separate platform; not proposed as a new analyzer dependency. |
| Docker, MultiYara, Syslog, CryptoScan, Vol3xp, symbol generator | No clear project-wide license found in the collected trees; some files retain framework notices. | Record source-level terms and unresolved additions before redistribution. A framework header does not settle every contributor's terms. |

These are observations of collected files and metadata, not blanket redistribution clearance. Keep sources with unresolved terms out of a public binary bundle, consistent with the existing core policy.

## Proposed integration sequence

1. Adapt CobaltStrike, RichHeader, ZoneID3 and PteResolve in **volatility-mcp**. Extend its existing versioned addon inventory with original/adapted SHA-256 values, commit pins, dependencies, expected names and limitations. Keep upstream implementations out of Workbench.
2. Verify with harmless fixtures: imports/help, required arguments, current API signatures, valid and malformed records, read/output bounds, clean JSON stdout, no execution-time network, and explicit error versus empty outcomes. Keep the existing 208-name set intact and verify source attribution. ZoneID3 needs source offsets before it can provide useful citations.
3. Evaluate SwapEnumerator, parent-spoof checks, Docker and the alternate EVTX carver as separate changes with their own symbols, costs and representative fixtures. Keep PasswordManager and SSHKeys explicitly opt-in. Defer the PFN family/WinObj until their larger compatibility work is justified; require an offline redesign for CryptoScan.
4. Only after those checks, perform explicitly authorized, bounded compatibility/accuracy evaluation across selected OS/builds. This review supplies no authorization to use existing private cases as test fixtures. Workbench may display newly discovered commands through its current catalog without implementing either proposed investigation mode.

## Collected materials and verification

The review bundle contains the complete pinned community3 working tree, including its original documents and embedded ZIP; selected source/README/license files from nine linked repositories; full upstream file trees and explicit exclusions; original download hashes; the refreshed installed inventory; analyzer dependency metadata; and the 39-entry annotated comparison. The VolWeb snapshot is intentionally limited to review-relevant source/metadata, not a runnable copy of that separate application. GUI source, OpenSSH ISFs and repository license files are retained.

All **144 downloaded upstream files** were verified against both their recorded SHA-256 and Git blob IDs. Static AST parsing of the selected Python source completed without parse failures. Checks verify collection integrity and source structure, not successful plugin imports or runtime behavior. Candidate modules were not imported, installed or run. No memory image, saved case output, conversation or sealed report was opened or modified; application runtimes were not restarted.

Public source pins are retained in `upstream-manifests.json`; class-level paths, requirements and hashes are in `candidate-inventory.json`. The full local catalog snapshot is in `installed-catalog.json`, with dependency metadata in `analyzer-software-baseline.json`. These sidecars and the source archive remain outside the Workbench Git repository. Only this review and a roadmap reference are intended as repository documentation changes.

## Subsequent first-batch integration — 18 October 2026

The source-review statements above describe the pre-integration snapshot. After
explicit authorization, core commit `ba5b14f` on local branch
`codex/community-first-batch` adapted CobaltStrike, RichHeader, ZoneID3 and
PteResolve through inventory revision 3. The installed analyzer increased from
208 to 212 commands without losing any original name; imports, attribution,
pinned original/adapted hashes and notices verified. Twenty first-batch synthetic
fixtures and the existing-addon smoke passed; the installed-core wheel completed
103 tests (102 passed, one expected optional skip) and both MCP protocol checks.
ZoneID3 now provides layer/source offsets with bounded required start/length.
No real image or private case was used, and OS/build accuracy remains unvalidated.

Core documentation records independent symbols, proposed cost budgets and fixture
gates for SwapEnumerator, parent-spoof checks, Docker and alternate EVTX. These
remain separate changes; sensitive extraction remains opt-in, PFN/WinObj deferred,
and CryptoScan requires an offline redesign. The local commit has not been pushed
or merged to main. Workbench source/installed app remain at `75ee777`; its older
bundled core requires a pin update and validated rebuild to inherit the new
attribution/offline policy. No new investigation mode is implemented.


## Publication and revised manual-extraction scope

The initial first batch is merged in core PR #10. At the user's subsequent
request, PasswordManager and SSHKeys are included in the installation as manually
selected commands, excluded from routine triage and automatic investigation/report
flows. Core inventory revision 4 holds their source pins, both SHA-256 values,
limits, offline policy and SSH schemas. Workbench consumes the core catalog; it
contains no copy of those upstream implementations.

The isolated analyzer now has 214 commands with the original 208-name set intact.
Seven synthetic extraction tests supplement the first batch's twenty tests.
A bounded public Windows 10 build 19041 compatibility sample is documented in
core's VALIDATION.md; it includes successful bounded outputs and explicit missing
page failures, not a detection-accuracy claim. No private case was a test fixture.
The earlier review/installation notes above are historical snapshots.
