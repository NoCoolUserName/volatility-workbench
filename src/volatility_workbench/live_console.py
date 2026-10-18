"""Read-only, bounded views of active and saved report tool events."""
from __future__ import annotations

import json
import re
from collections import deque

MAX_ENTRY = 8000
MAX_CHARS = 128000
MAX_ENTRIES = 100
MAX_LOG_RECORD = 16 * 1024 * 1024


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
    if kind in ('job_completed', 'job_failed', 'job_incomplete'):
        label = 'Investigation' if detail.get('kind') == 'question' else 'Report'
        return label + ' ' + kind.removeprefix('job_') + (': ' + excerpt(detail['error']) if detail.get('error') else '')
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


def snapshot(job, activity, *, include_question=False):
    if not job or job.get('kind') not in (('report', 'update', 'question') if include_question else ('report', 'update')):
        return None
    entries, size, dropped = deque(), 0, 0
    for event in activity:
        if not isinstance(event, dict):
            continue
        if event.get('job_id') != job['id']:
            continue
        detail = event.get('detail', {})
        turn = detail.get('turn_id') if isinstance(detail, dict) else None
        if turn and turn != job.get('turn_id'):
            continue
        text = event_text(event)
        if text:
            entry = {'id':event['id'], 'time':event['time'], 'text':excerpt(text)}
            entries.append(entry); size += len(entry['text'])
            while len(entries) > MAX_ENTRIES or size > MAX_CHARS:
                size -= len(entries.popleft()['text']); dropped += 1
    return {'job_id':job['id'], 'case_id':job['case_id'], 'entries':list(entries), 'earlier_entries':dropped,
            'status':job.get('status','running'), 'report_id':job.get('report_id'), 'finished_at':job.get('finished_at')}


def saved_snapshot(job, path, recent=()):
    """Stream the durable log without accumulating its history or rewriting it."""
    skipped = 0

    def events(stream):
        nonlocal skipped
        while line := stream.readline(MAX_LOG_RECORD + 1):
            if len(line) > MAX_LOG_RECORD:
                while not line.endswith(b'\n'):
                    line = stream.readline(65536)
                    if not line:break
                skipped += 1
                continue
            try:
                value = json.loads(line)
                if not isinstance(value, dict) or not isinstance(value.get('id'), str) or not isinstance(value.get('time'), str):
                    raise ValueError('Invalid activity record')
            except (ValueError, UnicodeError, RecursionError):
                skipped += 1
                continue
            yield value

    try:
        with path.open('rb') as stream:
            view = snapshot(job, events(stream))
        view['warnings'] = [f'{skipped} unreadable or oversized activity records were skipped; the original log is unchanged.'] if skipped else []
    except OSError:
        view = snapshot(job, recent)
        view['warnings'] = ['The activity log is unavailable; only recent saved activity is shown.']
    return view
