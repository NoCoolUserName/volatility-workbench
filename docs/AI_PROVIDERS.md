# AI connections

Workbench opens saved cases and the plugin catalog without a model connection.
Codex remains the default. Settings can explicitly select a compatible chat API
for new cases, or change the provider for a selected idle case. An existing case
without provider metadata is a Codex case. Changes never automatically send an
old conversation to a new provider.

## Codex

The existing official app-server adapter uses the installed Codex CLI and its
supported account configuration. Workbench does not copy account credentials or
change global model, effort, provider or billing settings. GUI launches find the
existing CLI in known installation locations, including the official npm package's
native executable, without running shell startup files. Settings also accepts an
explicit installed CLI executable. Missing Codex leaves saved material and Settings
available.

Readiness calls `initialize` and `account/read`; it does not make a model request.
Case conversations retain their saved thread IDs, supported approval handling and
restricted case MCP configuration. See the [official app-server documentation](https://learn.chatgpt.com/docs/app-server).

## Compatible chat API (experimental)

Enter an API base endpoint and an exact model identifier in Settings. The endpoint
must implement `POST <base>/chat/completions`, assistant `tool_calls`, function
JSON schemas and `tool` result messages. A similar API name alone is insufficient.
Remote endpoints require HTTPS. Explicit numeric loopback/localhost endpoints may
use HTTP. Redirects are refused, including same-origin redirects.

Use **Check provider** before an investigation. This makes two model requests
containing only a synthetic challenge/tool result; it verifies that the selected
model requests a tool and consumes its result. The check can incur provider usage
charges. It does not evaluate forensic accuracy or certify the endpoint. No real
compatible-model endpoint was exercised during the initial implementation: its
HTTP traffic was mocked, while the case-scoped MCP round trip was real.

Sending case content requires the explicit endpoint-specific Settings consent.
Questions, image metadata and selected tool outputs then go to that endpoint.
Images remain local, but this is not an entirely offline AI workflow. There is no
fallback provider, automatic endpoint selection or silent account/billing change.

The compatible adapter has a maximum of 16 tool rounds, 64 tool calls, 16 tool
requests per response, an 8 MiB request/transcript limit, 4 MiB response limit,
1 MiB per tool-result limit, 120-second HTTP timeout, a 180-second overall capability-check deadline and two-hour turn ceiling.
Oversized tool results return an explicit error asking for a bounded query.
Only the ten case-scoped MCP tools and the existing validated case/report tools
are available. There is no generic shell/file/installation tool. Tool schemas are
validated before dispatch. The model loop runs sequentially; network cancellation
closes the request and Stop also clears queued jobs.

Conversation history is saved per case and endpoint/model identity. Switching back
can resume that provider's earlier session. An interrupted/incomplete compatible
API turn is not silently replayed: use an explicit new session to continue, retaining
its transcript and saved evidence. Completed conversations survive restart. Tool
results are untrusted evidence, and report writes use the same provenance,
citation and sealing checks as Codex. A new default affects new cases; explicitly
select a case in Settings to change its provider.

## Secrets and process boundaries

New API secrets can be session-only or saved in macOS Keychain. The service is
`com.nocoolusername.VolatilityWorkbench.api`; accounts are hashes of canonical
endpoint URLs. Secrets never go into provider configuration, frontend responses,
reports, process arguments or environment variables. Changing endpoints cannot
reuse the prior endpoint's secret. Keychain failure has no plaintext fallback.
Session-only secrets must be entered again after app restart.

Keychain uses Security.framework's default trusted-application access controls.
macOS may ask for authorization after replacing an unsigned/ad-hoc build. API
errors omit response bodies, and responses that reflect the credential are
rejected. The provider client does not use environment-configured HTTP proxies.
Codex/analyzer/MCP child environments omit API keys and provider secrets; account
credentials managed by Codex itself stay in its supported login storage.

This is process separation for maintainability and controlled tool access, not a
security sandbox against a malicious plugin running as the same macOS user.

## Verification

`python -m unittest discover -s tests -p test_providers.py -v` runs offline with
synthetic data, HTTP mock transports and harmless fixture executables. It covers
endpoint validation, secret binding/reflection/redirect protection, capability
checks, limits, session persistence, invalid tool rejection, cancellation, explicit
provider switching and a real scoped MCP saved-coverage query with zero physical
memory-analysis invocations. Existing Codex/report tests remain in `test_ui.py`.

On the development Mac, native Codex discovery plus `account/read` succeeded using
the existing ChatGPT login without a model turn. A synthetic Keychain item was
created, read, replaced and deleted successfully. Those checks do not establish
compatibility with every model endpoint or with other host operating systems.
