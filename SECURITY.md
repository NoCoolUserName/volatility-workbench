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
