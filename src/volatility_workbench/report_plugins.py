"""Bounded report-presentation inventory from bundled metadata, never live analysis."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat

from volatility_mcp.api import safe_file

SCHEMA = 'report-plugin-inventory/1'
MAX_RECORDS = 2000
MAX_METADATA_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024
MAX_SNAPSHOT_BYTES = 32 * 1024 * 1024
START = '<!-- report-plugin-inventory -->'
END = '<!-- /report-plugin-inventory -->'
SCOPE_WARNING = ('Saved plugin-run records bundled with this report; runs can predate this revision. '
                 'Packaging or reuse does not establish new execution during report generation. '
                 'Empty output, failures and missing metadata are not clean-system conclusions.')


def _path(value):
    if (not isinstance(value, str) or not value or len(value) > 4096 or '\\' in value or '\x00' in value
            or any(ord(c) < 32 for c in value)):
        raise ValueError('Invalid bundled metadata path')
    p = PurePosixPath(value)
    if p.is_absolute() or any(part in ('.', '..') for part in value.split('/')) or str(p) != value:
        raise ValueError('Bundled metadata path escapes the report')
    return value


def identifier(value):
    if (not isinstance(value, str) or not value or len(value) > 256 or value in ('.', '..')
            or '/' in value or '\\' in value or any(ord(c) < 32 for c in value)):
        raise ValueError('Invalid report revision identifier')
    return value


class Reader:
    def __init__(self, root):
        self.root = Path(root)
        self.remaining = MAX_TOTAL_BYTES
        self.warnings = []
        self.partial = False

    def warn(self, message):
        self.partial = True
        if message not in self.warnings and len(self.warnings) < 100:
            self.warnings.append(message)

    def read(self, relative, registered=None, maximum=MAX_METADATA_BYTES):
        relative = _path(relative)
        target = safe_file(self.root, relative)
        try:
            info = target.lstat()
        except FileNotFoundError:
            self.warn('Bundled metadata is missing: ' + relative)
            return None
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('Bundled metadata must be a regular file')
        if info.st_size > maximum or info.st_size > self.remaining:
            self.warn('Bundled metadata exceeds the bounded read limit: ' + relative)
            return None
        with target.open('rb') as stream:
            raw = stream.read(min(maximum, self.remaining) + 1)
        self.remaining -= len(raw)
        if len(raw) != info.st_size or len(raw) > maximum or self.remaining < 0:
            self.warn('Bundled metadata changed or exceeded its read bound: ' + relative)
            return None
        if registered is not None and (registered.get('size_bytes') != len(raw)
                or registered.get('sha256') != hashlib.sha256(raw).hexdigest()):
            self.warn('Bundled metadata hash/size disagrees with its report manifest: ' + relative)
            return None
        return raw

    def json(self, relative, registered=None, maximum=MAX_METADATA_BYTES):
        raw = self.read(relative, registered, maximum)
        if raw is None:
            return None
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeError):
            self.warn('Malformed bundled JSON metadata: ' + relative)
            return None
        if not isinstance(value, dict):
            self.warn('Bundled JSON metadata must be an object: ' + relative)
            return None
        return value


def _text(value):
    return value if isinstance(value, str) and len(value) <= 4096 else None


def _records(value, reader, label, maximum=MAX_RECORDS):
    if not isinstance(value, list):
        reader.warn('Malformed ' + label + ' metadata')
        return []
    if len(value) > maximum:
        reader.warn(label + ' metadata exceeds the bounded record limit')
    return value[:maximum]


def _array(value):
    # Preserve exact values; do not silently truncate commands/arguments.
    if not isinstance(value, list) or len(value) > 256:
        return None
    if all(isinstance(v, str) and len(v) <= 16384 for v in value):
        return value if len(json.dumps(value)) <= 65536 else None
    return None


def _argv(commands):
    if not isinstance(commands, list) or len(commands) > 32 or not commands:
        return None
    result = [_array(c.get('argv')) if isinstance(c, dict) else None for c in commands]
    return result if all(value is not None for value in result) else None


def _empty(case_id, report_id):
    return {'schema': SCHEMA, 'case_id': case_id, 'report_id': report_id,
            'scope': 'bundled_saved_runs', 'source_status': 'unavailable',
            'summary': {'executions': 0, 'plugins': 0, 'failures': 0, 'reuse_receipts': 0,
                        'request_failures': 0, 'unknown_execution_records': 0,
                        'simulated_runs': 0, 'run_records': 0},
            'entries': [], 'warnings': [SCOPE_WARNING]}


def _summary(entries):
    runs = [e for e in entries if e['kind'] == 'plugin_run']
    executed = [e for e in runs if e['execution_recorded'] is True]
    return {'executions': len(executed),
            'plugins': len({e['plugin'] for e in executed if e['plugin'] is not None}),
            'failures': sum(e['status'] not in ('success', 'unknown', 'running') for e in executed),
            'reuse_receipts': sum(e['kind'] == 'reuse_receipt' for e in entries),
            'request_failures': sum(e['kind'] == 'request_failure' for e in entries),
            'unknown_execution_records': sum(e['execution_recorded'] is None for e in runs),
            'simulated_runs': sum(e.get('synthetic') is True for e in runs), 'run_records': len(runs)}


def _entry(run, step, original, source_path, reader, synthetic=False):
    rid = _text(run.get('run_id'))
    parameters = step.get('arguments') if isinstance(step.get('arguments'), dict) else {}
    plugin = _text(original.get('plugin')) or _text(parameters.get('plugin')) or _text(step.get('tool'))
    if plugin in ('run_plugin', 'get_image_info', 'unknown'):
        plugin = None
    args = _array(original.get('arguments'))
    if args is None:
        args = _array(parameters.get('arguments')) if parameters else _array(step.get('arguments'))
    argv = _argv(original.get('commands'))
    if argv is None and isinstance(step.get('argv'), list):
        candidate = step['argv']
        if all(_array(v) is not None for v in candidate) and candidate:
            argv = candidate
    commands = original.get('commands')
    # Core can save a command entry even when Popen fails. An integer return
    # code positively establishes process execution, including nonzero/negative
    # exits, without requiring argv in older records. Booleans are not exit codes.
    synthetic = synthetic or any(value.get('synthetic') is True or value.get('execution_kind') == 'simulated'
                                 for value in (run, step, original))
    executed = False if synthetic else (True if isinstance(commands, list) and any(
        isinstance(c, dict) and type(c.get('returncode')) is int for c in commands) else None)
    if any(value is None for value in (plugin, args, argv)) or executed is None:
        reader.warn('Some plugin/argument/argv/execution metadata is unknown for bundled run ' + str(rid))
    if not (_text(original.get('status')) or _text(run.get('status'))) or (original.get('status') or run.get('status')) == 'unknown':
        reader.warn('Execution outcome is unknown for bundled run ' + str(rid))
    return {'kind': 'plugin_run', 'run_id': rid, 'call_id': _text(run.get('call_id')),
            'image_id': _text(run.get('image_id')), 'plugin': plugin,
            'status': _text(original.get('status')) or _text(run.get('status')) or 'unknown',
            'arguments': args, 'argv': argv,
            'started_at': _text(original.get('started_at')) or _text(run.get('started_at')) or _text(step.get('timestamp')),
            'finished_at': _text(original.get('completed_at')) or _text(run.get('finished_at')),
            'reuse_count': 0, 'source_path': source_path or ('investigation.jsonl' if step else None), 'execution_recorded': executed,
            'synthetic': bool(synthetic), 'execution_kind': 'simulated' if synthetic else ('physical' if executed else 'unknown'),
            'provenance': 'core_manifest' if original else ('investigation_log' if step else 'bundle_run')}


def derive(root, case_id, report_id):
    """Historical fallback; read selected bundle metadata only and never write it."""
    reader = Reader(root)
    result = _empty(case_id, report_id)
    manifest = reader.json('case-manifest.json', maximum=4 * 1024 * 1024)
    if manifest is None:
        result['warnings'] += reader.warnings
        return result
    if manifest.get('case_id') != case_id:
        raise ValueError('Report belongs to another case')
    runs, artifacts = manifest.get('runs'), manifest.get('artifacts')
    if not isinstance(runs, list) or not isinstance(artifacts, list):
        reader.warn('Report run/artifact inventory is unavailable or malformed')
        result['warnings'] += reader.warnings
        return result
    if len(runs) > MAX_RECORDS or len(artifacts) > MAX_RECORDS * 16:
        reader.warn('Report metadata inventory is partial because its record limit was reached')
    registered = {}
    for item in artifacts[:MAX_RECORDS * 16]:
        if not isinstance(item, dict):
            reader.warn('Malformed report artifact entry')
            continue
        path = _path(item.get('path'))
        if path in registered:
            raise ValueError('Duplicate bundled artifact metadata path')
        registered[path] = item
    images = {e.get('id'): e for e in _records(manifest.get('evidence'), reader, 'evidence') if isinstance(e, dict) and isinstance(e.get('id'), str)}
    steps, steps_by_call, calls = {}, {}, []
    raw = reader.read('investigation.jsonl', maximum=4 * 1024 * 1024)
    if raw is not None:
        for index, line in enumerate(raw.splitlines()):
            if index >= MAX_RECORDS:
                reader.warn('Investigation log exceeds the bounded record limit')
                break
            if not line.strip():
                continue
            try:
                step = json.loads(line)
            except (ValueError, UnicodeError):
                reader.warn('Malformed investigation log entry')
                continue
            if not isinstance(step, dict):
                reader.warn('Malformed investigation log entry')
                continue
            calls.append(step)
            if isinstance(step.get('call_id'), str):
                if step['call_id'] in steps_by_call:
                    reader.warn('Duplicate investigation call metadata: ' + step['call_id'])
                else:
                    steps_by_call[step['call_id']] = step
            if isinstance(step.get('run_id'), str):
                if step['run_id'] in steps:
                    reader.warn('Duplicate investigation run metadata: ' + step['run_id'])
                else:
                    steps[step['run_id']] = step
    entries, known = [], {}
    for run in runs[:MAX_RECORDS]:
        if not isinstance(run, dict) or not _text(run.get('run_id')):
            reader.warn('Malformed bundled run record')
            continue
        rid = run['run_id']
        if rid in known:
            raise ValueError('Duplicate report run ID')
        step = steps.get(rid) or steps_by_call.get(_text(run.get('call_id')), {})
        if step and step.get('call_id') != run.get('call_id'):
            raise ValueError('Investigation call identity disagrees with its bundled run')
        if rid.startswith('inspection-') or step.get('tool') == 'inspect_artifact':
            continue
        if _text(run.get('image_id')) not in images:
            raise ValueError('Bundled run belongs to an unknown report image')
        candidates = [a for a in registered.values() if a.get('run_id') == rid
                      and a['path'].startswith('artifacts/') and a['path'].endswith('/manifest.json')]
        original, source_path = {}, None
        if len(candidates) > 1:
            reader.warn('Ambiguous original execution manifest for bundled run ' + rid)
        elif candidates:
            item = candidates[0]
            value = reader.json(item['path'], item)
            if value is not None:
                if value.get('source_ref') or value.get('inspection_id'):
                    continue  # Static inspections are not Volatility plugin runs.
                if value.get('run_id') != rid:
                    raise ValueError('Original execution manifest belongs to another run')
                if value.get('image_relative_path') != run.get('image_relative_path'):
                    raise ValueError('Original execution manifest image disagrees with report run')
                expected_hash = images[run['image_id']].get('sha256')
                if value.get('image_sha256_before') not in (None, expected_hash):
                    raise ValueError('Original execution manifest belongs to another image')
                if value.get('image_sha256_after') not in (None, expected_hash):
                    raise ValueError('Original execution manifest final image hash disagrees with report')
                if not expected_hash or value.get('image_sha256_before') is None:
                    reader.warn('Original execution image identity is unverified for bundled run ' + rid)
                if value.get('image_relative_path') is None:
                    reader.warn('Original execution image path identity is unknown for bundled run ' + rid)
                if (value.get('image') is not None and images[run['image_id']].get('path') is not None
                        and value['image'] != images[run['image_id']]['path']):
                    raise ValueError('Original execution manifest source image disagrees with report')
                if run.get('source_case_id') is not None and value.get('case_id') not in (None, run['source_case_id']):
                    raise ValueError('Original execution manifest belongs to another source case')
                original, source_path = value, item['path']
        if not original:
            reader.warn('Original execution manifest is unavailable for bundled run ' + rid)
        entry = _entry(run, step, original, source_path, reader, manifest.get('synthetic') is True)
        if step and step.get('tool') not in (None, entry['plugin']):
            reader.warn('Investigation plugin label disagrees with original execution record for ' + rid)
        if entry['started_at'] is None or entry['finished_at'] is None:
            reader.warn('Execution timestamps are incomplete for bundled run ' + rid)
        known[rid] = entry
        entries.append(entry)
    # Preserve denied/pre-execution requests without counting them as runs.
    for step in calls:
        tool = step.get('tool', '')
        if _text(step.get('call_id')) in {e['call_id'] for e in entries} or not isinstance(tool, str) or tool == 'inspect_artifact':
            continue
        if step.get('run_id') or re.fullmatch(r'(windows|linux|mac)\.[\w.]+', tool):
            if _text(step.get('run_id')) in known:
                continue
            if not re.fullmatch(r'(windows|linux|mac)\.[\w.]+', tool):
                reader.warn('Unmatched investigation run has no identifiable plugin')
                continue
            if step.get('image_id') is not None and _text(step['image_id']) not in images:
                raise ValueError('Investigation call belongs to an unknown report image')
            fallback = {k:step.get(k) for k in ('run_id', 'call_id', 'image_id', 'status')}
            entries.append(_entry(fallback, step, {}, 'investigation.jsonl', reader,
                                  manifest.get('synthetic') is True))
            reader.warn('Investigation call lacks a matching bundled run record; execution is unknown')
            continue
        if step.get('status') not in ('error', 'failed', 'cancelled', 'timeout'):
            continue
        args = step.get('arguments')
        if isinstance(args, str):
            try: args = json.loads(args)
            except ValueError: args = None
        plugin = args.get('plugin') if isinstance(args, dict) else None
        if tool.rsplit('.', 1)[-1] not in ('run_plugin', 'get_image_info') and not re.fullmatch(r'(windows|linux|mac)\.[\w.]+', tool):
            continue
        if plugin is None and tool.startswith(('windows.', 'linux.', 'mac.')):
            plugin = tool
        entries.append({'kind': 'request_failure', 'run_id': None, 'call_id': _text(step.get('call_id')),
            'image_id': _text(step.get('image_id')), 'plugin': _text(plugin), 'status': 'request_failed',
            'arguments': _array(args.get('arguments')) if isinstance(args, dict) else _array(args),
            'requested_image': _text(args.get('image')) if isinstance(args, dict) else None,
            'argv': None, 'started_at': _text(step.get('timestamp')), 'finished_at': None,
            'reuse_count': 0, 'source_path': 'investigation.jsonl', 'execution_recorded': False,
            'synthetic': step.get('synthetic') is True or step.get('execution_kind') == 'simulated',
            'execution_kind': 'request',
            'provenance': 'investigation_log', 'reason': 'Failed request; no physical plugin execution established.'})
    coverage_info = manifest.get('coverage')
    if isinstance(coverage_info, dict) and coverage_info.get('path'):
        path = _path(coverage_info['path'])
        if path not in registered:
            reader.warn('Coverage metadata is not registered with a report artifact hash')
        coverage = reader.json(path, registered.get(path))
        if coverage:
            if coverage.get('case_id') != case_id:
                raise ValueError('Coverage snapshot belongs to another case')
            receipt_paths = set()
            for image in _records(coverage.get('images'), reader, 'coverage images'):
                if not isinstance(image, dict) or _text(image.get('image_id')) not in images:
                    raise ValueError('Coverage snapshot belongs to an unknown report image')
                for scope in _records(image.get('entries'), reader, 'coverage scopes'):
                    if not isinstance(scope, dict):
                        reader.warn('Malformed coverage scope metadata');continue
                    for attempt in _records(scope.get('attempts'), reader, 'coverage attempts'):
                        if not isinstance(attempt, dict):
                            reader.warn('Malformed coverage attempt metadata');continue
                        rid = _text(attempt.get('run_id'))
                        for receipt in _records(attempt.get('reuse_receipts', []), reader, 'reuse receipts'):
                            if len(entries) >= MAX_RECORDS:
                                reader.warn('Plugin inventory reached its bounded record limit; counts cover retained metadata only')
                                break
                            if not isinstance(receipt, dict) or not receipt.get('bundle_path'):
                                reader.warn('A reuse receipt lacks bundled source metadata');continue
                            path = _path(receipt['bundle_path'])
                            if path in receipt_paths:continue
                            receipt_paths.add(path)
                            if rid not in known or path not in registered or not path.startswith('artifacts/'):
                                reader.warn('A reuse receipt is not linked to a bundled plugin run');continue
                            value = reader.json(path, registered[path])
                            if value is None:continue
                            parent = known[rid]
                            if (value.get('run_id') != rid or value.get('plugin') != parent['plugin']
                                    or value.get('reused') is not True or value.get('integrity_verified') is not True
                                    or parent['image_id'] != image['image_id']
                                    or value.get('arguments') != parent['arguments']):
                                reader.warn('Reuse receipt identity/verification disagrees with its bundled run');continue
                            expected_hash = images[image['image_id']].get('sha256')
                            if (not isinstance(value.get('image_before'), dict)
                                    or value['image_before'].get('sha256') != expected_hash
                                    or not isinstance(value.get('image_after'), dict)
                                    or value['image_after'].get('sha256') != expected_hash):
                                reader.warn('Reuse receipt image hash disagrees with its bundled image');continue
                            parent['reuse_count'] += 1
                            entries.append({**parent, 'kind': 'reuse_receipt', 'status': 'reused', 'argv': None,
                                'started_at': _text(value.get('requested_at')), 'finished_at': None,
                                'reuse_count': 0, 'source_path': path, 'execution_recorded': False,
                                'execution_kind': 'reuse',
                                'provenance': 'reuse_receipt', 'reason': 'Saved-result reuse; no new plugin execution.'})
    if len(entries) > MAX_RECORDS:
        entries = entries[:MAX_RECORDS]
        reader.warn('Plugin inventory reached its bounded record limit; counts cover retained metadata only')
    result.update(entries=entries, summary=_summary(entries),
                  source_status='partial' if reader.partial else ('available' if entries else 'unavailable'))
    if not entries:
        reader.warn('No plugin execution metadata is available in this report; execution count is unknown')
    if result['summary']['simulated_runs']:
        reader.warnings.append('Explicitly synthetic/simulated records are excluded from physical execution counts.')
    result['warnings'] += reader.warnings
    return result


def error_explanation(text):
    """Explain recognized saved diagnostics without treating failure as a finding."""
    if 'file_offset' in text and 'NameError' in text:
        return 'Plugin implementation defect: reconstruction referenced an unassigned file offset. The updated compatibility adapter repairs it; this historical run still failed.'
    if 'forbidden shell metacharacters' in text:
        return 'Request rejected before execution by argument validation. Installed regex-aware schemas support the VadRegExScan pattern and DumpFiles filter; use those exact options with valid regex syntax.'
    if 'This version of Windows is not supported' in text:
        return 'The installed plugin does not support this Windows version. For XP x86 network pool recovery, xpnet.XpNetScan is a separate limited alternative; it does not prove active connections or traffic.'
    if 'only supports x64 versions of Windows' in text:
        return 'The installed GUI plugin requires Windows x64. It cannot analyze an x86 image; rerunning unchanged will not resolve it.'
    if 'Template guessing is not applicable for NT5' in text or 'LSA signature' in text:
        return 'The credential parser could not resolve the NT5 LSA layout or required pages. This is a parser/acquisition limitation, not evidence that credentials are absent.'
    if 'Page error' in text or 'InvalidAddressException' in text:
        return 'A required memory page was unreadable. Acquisition gaps, an invalid pointer or a plugin defect can cause this; recovered rows may be incomplete and unchanged retries are not a repair.'
    if 'Unable to validate the plugin requirements' in text:
        return 'Required kernel layer or symbols could not be validated for this plugin. Check its guest OS, architecture and exact symbol requirements; installation alone does not establish compatibility.'
    if '_MI_SYSTEM_VA_TYPE' in text and 'Enumeration not found' in text:
        return 'The plugin requires a kernel enumeration missing from this symbol table. Its expected layout is unavailable for this image; do not substitute symbols from another build.'
    return None


def _error_sources(root, manifest, entries):
    """Link only registered, same-run diagnostics; read small request metadata only."""
    reader = Reader(root)
    artifacts = manifest.get('artifacts', []) if isinstance(manifest, dict) else []
    registered = {a['path']: a for a in artifacts[:MAX_RECORDS * 16]
                  if isinstance(a, dict) and isinstance(a.get('path'), str)}
    for entry in entries:
        entry['error_sources'] = []
        rid, cid = entry.get('run_id'), entry.get('call_id')
        if entry['kind'] == 'plugin_run' and rid:
            candidates = [a for a in registered.values() if a.get('run_id') == rid
                          and a['path'].startswith('artifacts/') and
                          (a['path'].endswith('/stderr.txt') or a['path'].endswith('/manifest.json'))]
            for item in candidates[:8]:
                path = _path(item['path'])
                safe_file(root, path)
                entry['error_sources'].append({'path': path, 'label': 'Saved stderr' if path.endswith('/stderr.txt') else 'Run manifest'})
                if path.endswith('/stderr.txt'):
                    raw=reader.read(path,item,maximum=256*1024)
                    if raw is not None:
                        entry['diagnosis']=error_explanation(raw.decode('utf-8',errors='replace'))

        elif entry['kind'] == 'request_failure' and isinstance(cid, str) and re.fullmatch(r'UI-[\w-]+', cid):
            path = 'artifacts/' + cid + '.json'
            if path not in registered:
                continue
            event = reader.json(path, registered[path])
            detail = event.get('detail') if isinstance(event, dict) else None
            if not isinstance(detail, dict) or 'UI-' + str(event.get('id')) != cid:
                continue
            args = detail.get('arguments')
            if isinstance(args, str):
                try: args = json.loads(args)
                except ValueError: args = None
            if not isinstance(args, dict) or args.get('plugin') != entry.get('plugin'):
                continue
            entry['requested_image'] = _text(args.get('image'))
            if entry.get('arguments') is None:
                entry['arguments'] = _array(args.get('arguments'))
            entry['error_sources'].append({'path':path, 'label':'Saved request error'})
            result = detail.get('result')
            content = result.get('content') if isinstance(result, dict) else None
            messages = [_text(c.get('text')) for c in content[:8] if isinstance(c, dict) and c.get('type') == 'text'] if isinstance(content, list) else []
            message = _text(detail.get('error')) or _text('\n'.join(m for m in messages if m))
            if message:
                entry['reason'] = message
                entry['diagnosis'] = error_explanation(message)
    return reader.warnings


def read(root, case_id, report_id, offset=0, limit=20):
    if type(offset) is not int or not 0 <= offset <= 100000 or type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('Invalid report-plugin inventory page bounds')
    identifier(report_id)
    reader = Reader(root)
    manifest = reader.json('case-manifest.json', maximum=4 * 1024 * 1024)
    if manifest is not None and manifest.get('case_id') != case_id:
        raise ValueError('Report belongs to another case')
    snapshot = None
    info = manifest.get('plugin_inventory') if manifest else None
    if isinstance(info, dict) and info.get('schema') == SCHEMA and info.get('path') == 'plugin-inventory.json':
        item = next((a for a in _records(manifest.get('artifacts'), reader, 'report artifacts', MAX_RECORDS * 16)
                     if isinstance(a, dict) and a.get('path') == info['path']), None)
        if item is not None:
            reader.remaining = MAX_SNAPSHOT_BYTES
            snapshot = reader.json(info['path'], item, maximum=MAX_SNAPSHOT_BYTES)
            if snapshot is not None:
                if (snapshot.get('schema') != SCHEMA or snapshot.get('case_id') != case_id
                        or snapshot.get('report_id') != report_id or snapshot.get('scope') != 'bundled_saved_runs'):
                    raise ValueError('Plugin inventory snapshot identity disagrees with selected report')
                entries = snapshot.get('entries')
                if (not isinstance(entries, list) or len(entries) > MAX_RECORDS
                        or not all(isinstance(e, dict) and e.get('kind') in ('plugin_run', 'reuse_receipt', 'request_failure') for e in entries)
                        or snapshot.get('source_status') not in ('available', 'partial', 'unavailable')
                        or not isinstance(snapshot.get('warnings'), list)):
                    raise ValueError('Malformed report-plugin inventory snapshot')
                # Validate every exposed source path before a frontend can link it.
                run_rows = _records(manifest.get('runs'), reader, 'report runs')
                image_rows = _records(manifest.get('evidence'), reader, 'report evidence')
                artifact_rows = _records(manifest.get('artifacts'), reader, 'report artifacts', MAX_RECORDS * 16)
                for rows, field in ((run_rows, 'run_id'), (image_rows, 'id'), (artifact_rows, 'path')):
                    if any(not isinstance(row, dict) or _text(row.get(field)) is None for row in rows):
                        raise ValueError('Malformed report inventory ownership metadata')
                run_images = {r['run_id']:r.get('image_id') for r in run_rows}
                image_ids = {e['id'] for e in image_rows}
                registered = {_path(a['path']):a for a in artifact_rows}
                checked_paths = set()
                reader.remaining = min(reader.remaining, MAX_TOTAL_BYTES)
                for entry in entries:
                    if (not {'run_id', 'call_id', 'image_id', 'plugin', 'arguments', 'argv', 'started_at',
                             'finished_at', 'execution_recorded', 'synthetic', 'reuse_count', 'status', 'source_path'} <= entry.keys()
                            or not all(entry.get(k) is None or _text(entry[k]) is not None for k in
                                ('run_id', 'call_id', 'image_id', 'plugin', 'started_at', 'finished_at'))
                            or _text(entry.get('status')) is None
                            or type(entry.get('synthetic')) is not bool
                            or (entry.get('execution_recorded') is not None and type(entry['execution_recorded']) is not bool)
                            or type(entry.get('reuse_count')) is not int or not 0 <= entry['reuse_count'] <= MAX_RECORDS
                            or (entry.get('arguments') is not None and _array(entry['arguments']) is None)
                            or (entry.get('argv') is not None and (not isinstance(entry['argv'], list)
                                or len(entry['argv']) > 32 or any(_array(c) is None for c in entry['argv'])))):
                        raise ValueError('Malformed report-plugin inventory entry')
                    if entry['synthetic'] and entry['execution_recorded'] is True:
                        raise ValueError('Simulated inventory record cannot claim physical execution')
                    if entry['kind'] != 'plugin_run' and entry['execution_recorded'] is not False:
                        raise ValueError('Reuse/failed-request inventory record cannot claim physical execution')
                    if entry['image_id'] is not None and entry['image_id'] not in image_ids:
                        raise ValueError('Plugin inventory entry belongs to another report image')
                    if entry['run_id'] in run_images and entry['image_id'] != run_images[entry['run_id']]:
                        raise ValueError('Plugin inventory run/image ownership disagrees with selected report')
                    if entry['execution_recorded'] is True and entry['run_id'] not in run_images:
                        raise ValueError('Plugin inventory claims execution without a bundled run')
                    if entry.get('source_path') is not None:
                        _path(entry['source_path'])
                        if entry['source_path'] not in registered.keys() | {'investigation.jsonl'}:
                            raise ValueError('Plugin inventory source is not registered in the selected bundle')
                        safe_file(root, entry['source_path'])
                        source = entry['source_path']
                        if (source != 'investigation.jsonl' and not source.endswith('/manifest.json')
                                and not (source.startswith('artifacts/coverage/') and source.endswith('.json'))):
                            raise ValueError('Plugin inventory source is not small bundled execution metadata')
                        if source not in checked_paths and source != 'investigation.jsonl':
                            # Check small metadata hashes, never source images or raw output.
                            reader.json(source, registered[source])
                            checked_paths.add(source)
                snapshot['summary'] = _summary(entries)
                if reader.warnings:
                    snapshot['warnings'] = list(dict.fromkeys(snapshot['warnings'] + reader.warnings))
                    if snapshot['source_status'] == 'available':snapshot['source_status'] = 'partial'
        else:
            reader.warn('Plugin inventory snapshot is not registered in this report manifest')
    elif info is not None:
        reader.warn('Plugin inventory snapshot metadata is unsupported or malformed')
    if snapshot is None:
        snapshot = derive(root, case_id, report_id)
        if reader.warnings:
            snapshot['warnings'] += reader.warnings
            if snapshot['source_status'] == 'available':snapshot['source_status'] = 'partial'
    entries = snapshot['entries']
    executed_names = sorted({e['plugin'] for e in entries
                             if e.get('kind') == 'plugin_run' and e.get('execution_recorded') is True
                             and e.get('synthetic') is not True and e.get('execution_kind') != 'simulated'
                             and isinstance(e.get('plugin'), str)})
    errored = [{key: e.get(key) for key in ('plugin', 'image_id', 'requested_image', 'arguments', 'status', 'kind', 'run_id', 'call_id', 'reason')}
               for e in entries if e.get('kind') == 'request_failure' or
               (e.get('kind') == 'plugin_run' and isinstance(e.get('status'), str) and
                re.search(r'fail|error|denied|cancel|timeout', e['status'], re.I))]
    diagnostic_warnings = _error_sources(root, manifest, errored)
    return {**snapshot, 'warnings': list(dict.fromkeys(snapshot['warnings'] + diagnostic_warnings)),
            'entries': entries[offset:offset + limit],
            'next_offset': offset + limit if offset + limit < len(entries) else None,
            'executed_plugin_names': executed_names, 'errored_entries': errored}


def markdown(text, inventory):
    """Replace our own block inside workflow; preserve required report order."""
    text = re.sub(r'\n*' + re.escape(START) + r'.*?' + re.escape(END) + r'\n*', '\n\n', text, flags=re.S)
    heading = re.search(r'^## Investigative workflow[^\n]*$', text, re.M | re.I)
    if heading is None:
        return text
    def cell(value):
        if value is None:return 'Not recorded'
        raw = value if isinstance(value, str) else json.dumps(value, ensure_ascii=True)
        if len(raw) > 768:
            raw = raw[:768] + ' … [display abbreviated; exact value in plugin-inventory.json]'
        raw = raw.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        for char in '\\|`[]()!*_':
            raw = raw.replace(char, '&#' + str(ord(char)) + ';')
        return raw.replace('\r', ' ').replace('\n', '<br>')
    summary = inventory['summary']
    counts = {key:('Unknown' if inventory['source_status'] == 'unavailable' else str(value)) for key,value in summary.items()}
    lines = [START, '### Saved plugin inventory', '', SCOPE_WARNING, '',
             f"Source metadata: **{inventory['source_status']}**. Recorded plugin runs: **{counts['executions']}**; "
             f"distinct plugins: **{counts['plugins']}**; failed runs: **{counts['failures']}**; "
             f"reuse receipts: **{counts['reuse_receipts']}**; failed requests: **{counts['request_failures']}**; "
             f"runs with unknown execution metadata: **{counts['unknown_execution_records']}**; "
             f"explicitly simulated runs: **{counts['simulated_runs']}**.", '',
             '[Complete saved inventory](plugin-inventory.json). Counts are metadata records, not a completeness or clean-system verdict.', '']
    labels = ('Record', 'Plugin', 'Arguments (bounded display)', 'Recorded argv (bounded display)',
              'Result', 'Image', 'Run / call', 'Start / finish', 'Reuse receipts')
    for number, entry in enumerate(inventory['entries'][:100], 1):
        values = [entry['kind'] + (' (simulated)' if entry.get('synthetic') else ''), entry['plugin'], entry['arguments'], entry['argv'], entry['status'], entry['image_id'],
                  (entry.get('run_id') or 'Unknown') + ' / ' + (entry.get('call_id') or 'Unknown'),
                  (entry.get('started_at') or 'Unknown') + ' / ' + (entry.get('finished_at') or 'Unknown'), entry['reuse_count']]
        lines += [f'#### Saved record {number}', *(f'**{label}:** {cell(value)}' for label, value in zip(labels, values)), '']
    if len(inventory['entries']) > 100:
        lines += ['', 'Entries above show the first 100 metadata records; consult the complete saved inventory for all retained records.']
    lines += ['', *('Metadata limitation: ' + cell(w) for w in inventory['warnings'] if w != SCOPE_WARNING), END, '']
    return text[:heading.end()] + '\n\n' + '\n'.join(lines).rstrip() + '\n\n' + text[heading.end():].lstrip('\n')
