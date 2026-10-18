# Security and evidence handling

Workbench is a local application bound to loopback. Its HTTP interface checks Host,
Origin, and a private per-launch capability; its session cookie is HttpOnly and
SameSite=Strict. Recovered content is rendered inertly, and raw source-image
upload/download endpoints are not exposed. Do not expose this service to a network.

Private case state contains paths, report content, saved excerpts and conversation
associations. Store it outside Git. Preserve sealed report bundles and originals;
never execute recovered files, contact recovered endpoints, or publish case data.
The explicitly selected AI service may receive questions and selected tool output.
Codex remains the default and retains its own supported authentication. Optional
compatible-API secrets stay in the connector's memory or macOS Keychain, bound to
the configured endpoint; they are never copied into case/report data or browser
storage. Volatility may fetch symbols; setup downloads packages.
The separately installed core owns forensic confinement, integrity checks, execution
and artifact inspection. Read its [security contract](https://github.com/NoCoolUserName/volatility-mcp/blob/main/SECURITY.md).

The Codex adapter requests a read-only agent sandbox, routes supported approvals
explicitly, and disables unrelated tools. The compatible adapter exposes only the
case-scoped MCP tools and validated case/report operations, with no generic shell
or filesystem tool. This is not protection against a compromised local
account, analyzer, dependency, or model client. Keep those components trusted.
Updates are explicit dependency changes and idle process restarts, never startup
pulls or automatic installations during an investigation.

Report a vulnerability privately to the maintainer through an available GitHub
private security advisory channel. If unavailable, open a minimal issue requesting
a private contact method. Never attach credentials, memory images, recovered malware,
or private case material to a public issue.


The optional macOS app keeps the same loopback authentication, Origin/Host checks
and CSP. Remote navigation never replaces the trusted app UI. Native dialogs are
called by the authenticated backend; there is no exposed application JavaScript
bridge. The decorated system window supplies normal macOS clipping and controls.
The application bundle is immutable in normal operation. Optional downloads are
pinned, verified and staged outside it, with activation only while idle.

New compatible-API credentials are endpoint-bound and held in memory or macOS
Keychain; no plaintext fallback exists. Remote endpoints require TLS, redirects
are refused, and secrets are not returned to the UI or passed to analyzer/MCP
subprocess environments. Explicit provider selection and a capability check do
not establish forensic accuracy. Same-user processes and trusted plugins are not
an OS sandbox against malicious code. Local case content can reach the configured
AI service. See [provider limits](docs/AI_PROVIDERS.md).

## Private-repository security CI

The `Security / SAST` check runs Semgrep Community Edition locally on every Python,
JavaScript and TypeScript source file under `src/` and `scripts/`. It does not install
the application or an analyzer, open evidence, use a model, log in to Semgrep, or
upload source/findings to a scanning service. Usage metrics and version checks are
disabled. Findings and the coverage inventory remain private GitHub Actions artifacts
for 14 days. The separate code-quality workflow still runs its existing secret checks.

GitHub's hosted CodeQL scanning requires a public repository or an eligible organization
with [GitHub Code Security enabled](https://docs.github.com/en/code-security/concepts/code-scanning/codeql/codeql-code-scanning).
The [CodeQL CLI terms](https://github.com/github/codeql-cli-binaries/blob/main/LICENSE.md)
also restrict private non-open-source use without the applicable commercial license.
Disabling SARIF upload does not remove that licensing requirement. This repository
stays private; the workflow does not change its visibility, account plan or billing.

The [Semgrep CE engine is LGPL 2.1](https://github.com/semgrep/semgrep/blob/develop/LICENSE).
The [upstream rule license](https://semgrep.dev/legal/rules-license/) permits internal
use but restricts redistribution and service use. The workflow downloads the immutable
rule archive to its temporary workspace, verifies its SHA-256, retains its notices,
and selects 458 security-category rules from the Python/JavaScript/TypeScript folders.
Downloaded rules are not committed, included in scan artifacts, or bundled with Workbench.
The engine version, rule commit, archive digest and expected count are reviewed pins in
[security-rules.json](.github/security-rules.json); updates must review licensing and
rule changes as well as test the resulting scan.

The gate blocks every finding whose pinned rule declares `HIGH` or `CRITICAL` impact,
regardless of its confidence or INFO/WARNING/ERROR display level. Lower-impact findings
remain visible in the retained report. This replaces the previous CodeQL high/critical
CVSS gate; Semgrep impact labels are not CVSS scores, and CE's primarily local analysis
does not provide CodeQL's query set or cross-file data-flow coverage. A clean result is
not a security certification. See [CE's documented limitations](https://github.com/semgrep/semgrep/blob/develop/README.md).

Scanner failures, missing/malformed reports, parser errors, omitted source files, an
unexpected engine/rule inventory, and stale/unused review exceptions all fail the job.
Inline `nosemgrep` comments are disabled. The ten existing dynamic-argv audit findings
were individually reviewed as fixed maintenance/tool invocations without a shell;
[security-exceptions.json](.github/security-exceptions.json) records each exact rule,
path, line, full-file SHA-256 and rationale. Any change to one of those files requires
reviewing its invocation paths again. New findings do not inherit an exception.

To reproduce in a separate development environment:

```sh
python3 -m venv /tmp/workbench-security-venv
/tmp/workbench-security-venv/bin/python -m pip install semgrep==1.181.0
python3 -m unittest discover -s tests -p test_security_scan.py -v
/tmp/workbench-security-venv/bin/python scripts/security_scan.py --work-dir /tmp/workbench-security-results
```

The source only scan writes JSON findings, rule/target inventory and the gate result
under the specified directory. Do not install scanning dependencies into the configured
memory analyzer or an application environment.
