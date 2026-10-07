# Security and evidence handling

Workbench is a local application bound to loopback. Its HTTP interface checks Host,
Origin, and a private per-launch capability; its session cookie is HttpOnly and
SameSite=Strict. Recovered content is rendered inertly, and raw source-image
upload/download endpoints are not exposed. Do not expose this service to a network.

Private case state contains paths, report content, saved excerpts and conversation
associations. Store it outside Git. Preserve sealed report bundles and originals;
never execute recovered files, contact recovered endpoints, or publish case data.
The configured Codex service may receive questions and selected tool output. Model
credentials remain with Codex. Volatility may fetch symbols; setup downloads packages.
The separately installed core owns forensic confinement, integrity checks, execution
and artifact inspection. Read its [security contract](https://github.com/NoCoolUserName/volatility-mcp/blob/main/SECURITY.md).

The adapter requests a read-only agent sandbox, routes supported approvals explicitly,
and disables unrelated tools. This is not protection against a compromised local
account, analyzer, dependency, or model client. Keep those components trusted.
Updates are explicit dependency changes and idle process restarts, never startup
pulls or automatic installations during an investigation.

Report a vulnerability privately to the maintainer through an available GitHub
private security advisory channel. If unavailable, open a minimal issue requesting
a private contact method. Never attach credentials, memory images, recovered malware,
or private case material to a public issue.
