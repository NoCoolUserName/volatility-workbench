"""Read-only, bounded views of actual tool events for the active report job."""
from __future__ import annotations

import json
import re

MAX_ENTRY = 8000
MAX_CHARS = 128000
MAX_ENTRIES = 100


def excerpt(value, limit=MAX_ENTRY):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
    text = re.sub(r'\x1b\][^\x07]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]', '', text)
    text = ''.join(c for c in text if c in '\n\t' or ord(c) >= 32).replace('\x7f', '')
    return text if len(text) <= limit else text[:limit] + '\n[Console excerpt; full plugin results remain saved separately.]'


def tool_output(result):
    if not isinstance(result, dict):
        return result
    content = result.get('content')
    if isinstance(content, list):
        texts = [item['text'] for item in content if isinstance(item, dict) and isinstance(item.get('text'), str)]
        if texts:
            return '\n'.join(texts)
        return result.get('structuredContent') or '[No text output returned.]'
    return result


def event_text(event):
    kind, detail = event.get('kind'), event.get('detail', {})
    if not isinstance(detail, dict):
        return None
    if kind == 'job_started':
        return str(detail.get('kind', 'Report')) + ' started'
    if kind in ('local_tool_started', 'provider_tool_started'):
        return '> ' + str(detail.get('tool', 'tool')) + '\n' + excerpt(detail.get('arguments', {}), 2000)
    if kind in ('local_tool_completed', 'provider_tool_completed'):
        return '< ' + str(detail.get('tool', 'tool')) + '\n' + excerpt(detail.get('output', '[No text output returned.]'))
    if kind == 'tool_progress':
        return '... ' + str(detail.get('message', ''))
    if kind == 'provider_request':
        return 'Waiting for provider response · request ' + str(detail.get('round', ''))
    if kind in ('item/started', 'item/completed') and detail.get('type') == 'mcpToolCall':
        name = str(detail.get('server', 'MCP')) + '.' + str(detail.get('tool', 'tool'))
        if kind == 'item/started':
            return '> ' + name + '\n' + excerpt(detail.get('arguments', {}), 2000)
        output = detail.get('error') or tool_output(detail.get('result'))
        return '< ' + name + ' [' + str(detail.get('status', 'completed')) + ']\n' + excerpt(output)
    if kind == 'agent_error':
        return 'Error: ' + excerpt(detail.get('message') or detail.get('error') or detail)
    return None


def snapshot(job, activity):
    if not job or job.get('kind') not in ('report', 'update'):
        return None
    entries = []
    for event in activity:
        if event.get('job_id') != job['id']:
            continue
        detail = event.get('detail', {})
        turn = detail.get('turn_id') if isinstance(detail, dict) else None
        if turn and turn != job.get('turn_id'):
            continue
        text = event_text(event)
        if text:
            entries.append({'id':event['id'], 'time':event['time'], 'text':excerpt(text)})
    dropped = max(0, len(entries) - MAX_ENTRIES)
    entries = entries[-MAX_ENTRIES:]
    size = sum(len(item['text']) for item in entries)
    while size > MAX_CHARS and entries:
        size -= len(entries.pop(0)['text'])
        dropped += 1
    return {'job_id':job['id'], 'case_id':job['case_id'], 'entries':entries, 'earlier_entries':dropped}
