"""Small compatible chat/tool adapter. Secrets stay inside this connector.

No model request occurs until an explicit capability check or conversation turn.
The adapter only executes tools supplied by the case controller.
"""
from __future__ import annotations
import asyncio
import hashlib
import ipaddress
import json
import re
import secrets
from urllib.parse import urlsplit, urlunsplit
import httpx2 as httpx
from jsonschema import validate, ValidationError
from .storage import atomic_json
from .models import DEFAULT_MODEL, DEFAULT_EFFORT, model_name, reasoning_effort
from .live_console import excerpt

MAX_RESPONSE = 4 * 1024 * 1024
MAX_TRANSCRIPT = 8 * 1024 * 1024
MAX_TOOL_RESULT = 1024 * 1024
MAX_ROUNDS = 16
MAX_CALLS = 64
CAPABILITY_TIMEOUT = 180


class ProviderError(RuntimeError):
    pass


def normalize_endpoint(value):
    if not isinstance(value, str) or len(value) > 2000 or any(ord(c) < 32 for c in value):
        raise ValueError('A compatible provider requires an endpoint URL')
    parsed = urlsplit(value.strip())
    if parsed.username or parsed.password or parsed.query or parsed.fragment or not parsed.hostname:
        raise ValueError('Endpoint must not contain credentials, a query or a fragment')
    host = parsed.hostname.lower()
    try:
        loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = host == 'localhost'
    if parsed.scheme != 'https' and not (parsed.scheme == 'http' and loopback):
        raise ValueError('Remote providers require HTTPS; HTTP is permitted only for explicit loopback endpoints')
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError('Invalid endpoint port') from exc
    authority = '[' + host + ']' if ':' in host else host
    if port:
        authority += ':' + str(port)
    path = parsed.path.rstrip('/')
    if path.endswith('/chat/completions'):
        raise ValueError('Enter the API base URL, such as https://host.example/v1, without /chat/completions')
    if any(part in ('.', '..') for part in path.split('/')) or '%' in path or '\\' in path:
        raise ValueError('Endpoint path must be a literal API base path without traversal or encoded characters')
    return urlunsplit((parsed.scheme, authority, path, '', ''))


def provider_config(data, *, resolve_executable=True):
    if not isinstance(data, dict):
        raise ValueError('Provider configuration must be an object')
    kind = data.get('provider', 'codex')
    if kind == 'codex':
        result = {'provider': 'codex', 'id': 'codex', 'model': model_name(data.get('model', DEFAULT_MODEL)),
                  'reasoning_effort': reasoning_effort(data.get('reasoning_effort', DEFAULT_EFFORT))}
        if data.get('codex_executable'):
            from .codex import discover_codex
            if not isinstance(data['codex_executable'], str):
                raise ValueError('Codex executable must be a path')
            result['codex_executable'] = discover_codex(data['codex_executable']) if resolve_executable else data['codex_executable']
        return result
    if kind != 'compatible':
        raise ValueError('Choose Codex or compatible API explicitly')
    endpoint = normalize_endpoint(data.get('endpoint', ''))
    model = model_name(data.get('model', ''))
    identity = hashlib.sha256((endpoint + '\n' + model).encode()).hexdigest()[:24]
    storage = data.get('credential_storage', 'none')
    if storage not in ('none', 'session', 'keychain'):
        raise ValueError('Unknown credential storage mode')
    return {'provider': kind, 'id': 'compatible-' + identity, 'endpoint': endpoint, 'model': model,
            'reasoning_effort': reasoning_effort(data.get('reasoning_effort')),
            'credential_storage': storage, 'allow_case_content': data.get('allow_case_content') is True}


class CompatibleClient:
    """Bounded, cancellable chat-completions tool loop; no shell or file access."""
    def __init__(self, config, credentials, transport=None):
        self.config = provider_config(config)
        self.credentials = credentials
        self.transport = transport  # test injection; not user configurable

    async def request(self, messages, tools):
        payload = {'model': self.config['model'], 'messages': messages, 'stream': False}
        if tools:
            payload.update({'tools': [{'type': 'function', 'function': {'name': t['name'],
                       'description': t.get('description', '')[:8000], 'parameters': t['inputSchema']}} for t in tools],
                            'tool_choice': 'auto'})
        if self.config.get('reasoning_effort'):
            payload['reasoning_effort'] = self.config['reasoning_effort']
        encoded = json.dumps(payload).encode()
        if len(encoded) > MAX_TRANSCRIPT:
            raise ProviderError('Conversation exceeds the 8.39 MB request limit. Start a new explicit provider session; saved evidence is retained.')
        # Read the credential only at the network boundary; never put it in state or env.
        secret = await asyncio.to_thread(self.credentials.get, self.config['endpoint'], self.config.get('credential_storage', 'none'))
        headers = {'Content-Type': 'application/json'}
        if secret:
            headers['Authorization'] = 'Bearer ' + secret
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=15), follow_redirects=False,
                                         trust_env=False, transport=self.transport) as client:
                async with client.stream('POST', self.config['endpoint'] + '/chat/completions', content=encoded, headers=headers) as response:
                    if response.is_redirect:
                        raise ProviderError('Provider redirected the request; redirects are refused to protect endpoint-bound credentials. Configure the intended endpoint explicitly.')
                    if response.status_code != 200:
                        # Error response bodies can echo credentials/prompts; do not persist them.
                        raise ProviderError(f'Compatible provider returned HTTP {response.status_code}; check the endpoint, model, account and credentials.')
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > MAX_RESPONSE:
                            raise ProviderError('Provider response exceeds the 4.19 MB limit')
            if secret and secret.encode() in data:
                raise ProviderError('Provider response contained the configured credential; response was discarded to prevent disclosure')
            result = json.loads(data)
            choice = result['choices'][0]
            message = choice['message']
            if choice.get('finish_reason') in ('length', 'content_filter'):
                raise ProviderError('Provider response was incomplete: ' + choice['finish_reason'])
            if not isinstance(message, dict) or message.get('role') != 'assistant':
                raise ValueError('Expected an assistant message')
            text = message.get('content')
            if text is not None and not isinstance(text, str):
                raise ValueError('Only text assistant messages are supported')
            def reflected(value):
                if isinstance(value,str):return secret in value
                if isinstance(value,list):return any(reflected(v) for v in value)
                if isinstance(value,dict):return any(reflected(v) for v in value.values())
                return False
            if secret and reflected(message):
                raise ProviderError('Provider response contained the configured credential; response was discarded to prevent disclosure')
            calls = message.get('tool_calls') or []
            if not isinstance(calls, list) or len(calls) > 16:
                raise ValueError('At most 16 tool requests per response are supported')
            return {'role': 'assistant', 'content': text, **({'tool_calls': calls} if calls else {})}
        except asyncio.CancelledError:
            raise
        except ProviderError:
            raise
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            raise ProviderError('Compatible provider returned an invalid response or could not be reached. Check connectivity and chat-completions tool support.') from None

    async def list_models(self):
        """Explicit metadata-only discovery; never send case content or follow redirects."""
        secret = await asyncio.to_thread(self.credentials.get, self.config['endpoint'], self.config.get('credential_storage', 'none'))
        headers = {'Authorization': 'Bearer ' + secret} if secret else {}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=15), follow_redirects=False,
                                         trust_env=False, transport=self.transport) as client:
                async with client.stream('GET', self.config['endpoint'] + '/models', headers=headers) as response:
                    if response.is_redirect:
                        raise ProviderError('Model discovery redirected; configure the intended endpoint explicitly. Credentials were not forwarded.')
                    if response.status_code != 200:
                        raise ProviderError(f'Model discovery returned HTTP {response.status_code}. You can enter a custom model identifier if this endpoint does not list models.')
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > MAX_RESPONSE:
                            raise ProviderError('Model catalog exceeds the 4.19 MB limit')
            if secret and secret.encode() in data:
                raise ProviderError('Model catalog contained the configured credential; response discarded')
            entries = json.loads(data)['data']
            if not isinstance(entries, list) or len(entries) > 1000:
                raise ValueError('Invalid model catalog')
            names = list(dict.fromkeys(model_name(item.get('id')) for item in entries if isinstance(item, dict)))
            if secret and any(secret in name for name in names):
                raise ProviderError('Model catalog contained the configured credential; response discarded')
            if not names:
                raise ValueError('Empty model catalog')
            return [{'model': name, 'label': name} for name in names]
        except ProviderError:
            raise
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise ProviderError('No usable model catalog was returned. Enter the endpoint\'s documented model identifier instead.') from None

    async def check(self):
        """Bound the complete capability exchange below the HTTP dispatch deadline."""
        try:
            return await asyncio.wait_for(self._check(), CAPABILITY_TIMEOUT)
        except asyncio.TimeoutError:
            raise ProviderError('Synthetic provider capability check timed out after 180 seconds; no case content was sent') from None

    async def _check(self):
        """Two requests with synthetic data only; validates tool request AND result use."""
        tool = {'name': 'workbench_capability_echo', 'description': 'Call with exactly the supplied challenge.',
                'inputSchema': {'type': 'object', 'properties': {'challenge': {'type': 'string'}},
                                'required': ['challenge'], 'additionalProperties': False}}
        challenge, answer = secrets.token_hex(12), secrets.token_hex(12)
        messages = [{'role': 'user', 'content': 'Compatibility check. Call workbench_capability_echo with challenge ' + challenge + '. After the tool returns, respond with its result exactly.'}]
        first = await self.request(messages, [tool])
        calls = first.get('tool_calls', [])
        if len(calls) != 1:
            raise ProviderError('Capability check failed: model did not request the synthetic tool exactly once')
        call = calls[0]
        name, args = self.tool_call(call, {tool['name']: tool})
        if args != {'challenge': challenge}:
            raise ProviderError('Capability check failed: synthetic tool arguments did not match')
        messages.extend([first, {'role': 'tool', 'tool_call_id': call['id'], 'content': answer}])
        second = await self.request(messages, [tool])
        if second.get('tool_calls') or (second.get('content') or '').strip() != answer:
            raise ProviderError('Capability check failed: model did not consume and return the synthetic tool result')
        return {'connected': True, 'provider': 'compatible', 'model': self.config['model'],
                'requested_reasoning_effort': self.config.get('reasoning_effort'),
                'reasoning_note': 'Effort is a requested override; this check cannot verify that the provider honored it.',
                'tool_round_trip': 'passed', 'scope': 'Synthetic tool request/result only; no case content transmitted or forensic accuracy evaluated.'}

    @staticmethod
    def tool_call(call, allowed):
        try:
            if call.get('type') != 'function' or not isinstance(call['id'], str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,200}', call['id']):
                raise ValueError('Invalid tool call identity')
            function = call['function']
            name = function['name']
            if name not in allowed:
                raise ProviderError('Provider requested a tool outside this case tool allowlist')
            raw = function['arguments']
            if not isinstance(raw, str) or len(raw) > 262144:
                raise ValueError('Invalid or oversized tool arguments')
            args = json.loads(raw)
            validate(args, allowed[name]['inputSchema'])
            return name, args
        except ProviderError:
            raise
        except (ValueError, KeyError, TypeError, ValidationError):
            raise ProviderError('Provider supplied invalid tool arguments; no tool was executed') from None

    async def run(self, path, instructions, prompt, tools, execute, event, cancelled):
        """Persist only this endpoint/model session; supplied executor confines tools."""
        if path.exists():
            if path.is_symlink():
                raise ProviderError('Saved provider conversation must not be a symlink')
            if path.stat().st_size > MAX_TRANSCRIPT:
                raise ProviderError('Saved provider conversation exceeds the 8.39 MB limit')
            saved = json.loads(path.read_text())
            if saved.get('provider_id') != self.config['id']:
                raise ProviderError('Provider conversation belongs to a different endpoint/model')
            if saved.get('status') != 'completed':
                # Incomplete tool result sequences cannot be safely resumed as API messages.
                raise ProviderError('Previous compatible-provider turn is incomplete. Start a new explicit session; saved messages and evidence remain available.')
            messages = saved['messages']
        else:
            messages = [{'role': 'system', 'content': instructions}]
        messages.append({'role': 'user', 'content': prompt})
        state = {'schema_version': 1, 'provider_id': self.config['id'], 'messages': messages, 'status': 'running'}
        def save():
            if len(json.dumps(state).encode()) > MAX_TRANSCRIPT:
                raise ProviderError('Saved provider conversation exceeds the 8.39 MB limit')
            atomic_json(path, state)
        save()
        allowed = {t['name']: t for t in tools}
        calls_used = 0
        seen = set()
        try:
            for round_number in range(MAX_ROUNDS):
                if cancelled.is_set():
                    raise asyncio.CancelledError()
                await event('provider_request', {'round': round_number + 1, 'provider': 'compatible'})
                message = await self.request(messages, tools)
                messages.append(message)
                calls = message.get('tool_calls', [])
                if not calls:
                    if not (message.get('content') or '').strip():
                        raise ProviderError('Provider returned neither a message nor a tool request')
                    state['status'] = 'completed'; save()
                    return message['content']
                for call in calls:
                    if cancelled.is_set():
                        raise asyncio.CancelledError()
                    calls_used += 1
                    if calls_used > MAX_CALLS:
                        raise ProviderError('Tool-call limit reached (64); completed evidence is retained')
                    name, args = self.tool_call(call, allowed)
                    if call['id'] in seen:
                        raise ProviderError('Duplicate provider tool-call ID; no duplicate tool was executed')
                    seen.add(call['id'])
                    await event('provider_tool_started', {'tool': name, 'call_id': call['id'], 'arguments':excerpt(args,2000)})
                    result = await execute(name, args)
                    encoded = json.dumps(result)
                    if len(encoded.encode()) > MAX_TOOL_RESULT:
                        encoded = json.dumps({'error': 'Tool response exceeds the 1.05 MB provider limit. Query a smaller bounded page; saved outputs remain intact.', 'truncated': True})
                    messages.append({'role': 'tool', 'tool_call_id': call['id'], 'content': encoded})
                    await event('provider_tool_completed', {'tool': name, 'call_id': call['id'], 'output':excerpt(encoded)})
                    save()
            raise ProviderError('Tool-round limit reached (16); completed evidence is retained')
        except BaseException:
            state['status'] = 'incomplete'
            save()
            raise
