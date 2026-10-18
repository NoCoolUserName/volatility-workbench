"""Bounded upstream Volshell helper transport for the active investigating job.

This is an exploratory application tool, not a core plugin or evidence adapter.
It never accepts Python from the model and never adopts a user's Python session.
"""
from __future__ import annotations

import asyncio
import copy
import re
import uuid

from volatility_mcp.api import check_components, file_fingerprint, private_dir
from .storage import atomic_json, now
from .volshell import VolshellManager


HELPERS = ('hh', 'ps', 'db', 'dw', 'dd', 'dq', 'dis', 'dt', 'cl', 'cp')
MAX_OUTPUT = 32000
MAX_CALLS = 50
NOTE = ('Exploratory Volshell observation, not validated core evidence. Completion only means the '
        'helper returned; inspect its output for errors or limitations. Use exact observed values to '
        'choose subsequent guarded core tools. Report claims require saved, validated core evidence; '
        'do not invent a core run ID, citation, successful collection or clean result from this output.')


def _integer(value, name, maximum, minimum=0):
    if isinstance(value, str) and re.fullmatch(r'(?:0[xX][0-9a-fA-F]+|[0-9]+)', value) and len(value) <= 24:
        value = int(value, 16 if value.lower().startswith('0x') else 10)
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f'{name} must be an integer from {minimum} to {maximum}')
    return value


def _name(value, label):
    if not isinstance(value, str) or not 1 <= len(value) <= 256 or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in value):
        raise ValueError('Invalid ' + label)
    return value


def validate_call(data):
    """Translate a closed, typed helper schema to fixed upstream function calls."""
    if not isinstance(data, dict) or set(data) - {'image_id', 'helper', 'arguments', 'mode', 'reason'}:
        raise ValueError('Use image_id, helper, arguments, mode and reason only')
    image_id = _name(data.get('image_id'), 'registered image identity')
    helper = data.get('helper')
    if not isinstance(helper, str) or helper not in HELPERS:
        raise ValueError('Choose one supported inspection helper: ' + ', '.join(HELPERS))
    mode = data.get('mode', 'generic')
    if mode not in ('generic', 'windows', 'linux', 'mac'):
        raise ValueError('Choose generic, windows, linux or mac mode')
    arguments = data.get('arguments')
    arguments = {} if arguments is None else arguments
    if not isinstance(arguments, dict):
        raise ValueError('Helper arguments must be a named object')
    reason = data.get('reason', '')
    if not isinstance(reason, str) or len(reason) > 2000:
        raise ValueError('Reason must be text under 2,000 characters')
    allowed = {'hh': set(), 'ps': {'start', 'limit'}, 'dt': {'type_name', 'offset'},
               'cl': {'layer_name'}, 'cp': {'pid'}}.get(helper, {'offset', 'count', 'layer_name'})
    if helper == 'dis':
        allowed = allowed | {'architecture'}
    if set(arguments) - allowed:
        raise ValueError('Unknown arguments for ' + helper)
    normalized = {}
    if helper == 'hh':
        command = 'hh()'
    elif helper == 'ps':
        if mode == 'generic':
            raise ValueError('ps requires a Windows, Linux or macOS session')
        start = _integer(arguments.get('start', 0), 'start', 10000)
        limit = _integer(arguments.get('limit', 50), 'limit', 200, 1)
        normalized = {'start': start, 'limit': limit}
        command = f'ps()[{start}:{start + limit}]'
    elif helper == 'cp':
        if mode == 'generic':
            raise ValueError('cp requires a Windows, Linux or macOS session')
        normalized = {'pid': _integer(arguments.get('pid'), 'pid', 2**32 - 1)}
        command = 'cp(pid=' + str(normalized['pid']) + ')'
    elif helper == 'cl':
        normalized = {'layer_name': _name(arguments.get('layer_name'), 'layer name')}
        command = 'cl(layer_name=' + repr(normalized['layer_name']) + ')'
    elif helper == 'dt':
        normalized = {'type_name': _name(arguments.get('type_name'), 'symbol type name')}
        command = 'dt(' + repr(normalized['type_name'])
        if 'offset' in arguments:
            normalized['offset'] = _integer(arguments['offset'], 'offset', 2**64 - 1)
            command += ', offset=' + str(normalized['offset'])
        command += ')'
    else:
        normalized = {'offset': _integer(arguments.get('offset'), 'offset', 2**64 - 1),
                      'count': _integer(arguments.get('count', 128), 'count', 4096, 1)}
        if 'layer_name' in arguments:
            normalized['layer_name'] = _name(arguments['layer_name'], 'layer name')
        if 'architecture' in arguments:
            architecture = arguments['architecture']
            if architecture not in ('intel', 'intel64', 'arm', 'arm64'):
                raise ValueError('Unsupported disassembly architecture')
            normalized['architecture'] = architecture
        command = helper + '(' + ', '.join(key + '=' + repr(value) for key, value in normalized.items()) + ')'
    return {'image_id': image_id, 'helper': helper, 'mode': mode, 'arguments': normalized,
            'reason': reason, 'command': command}


class AgentVolshell:
    def __init__(self, app, manager=None, timeout=120):
        self.app = app
        self.manager = manager or VolshellManager()
        self.timeout = min(120, max(.1, timeout))
        self._lock = asyncio.Lock()
        self._activity = None
        self._owner = None
        self._first_entry = 1
        self._marker = ''
        self._counts = {}

    def _current(self, case, job):
        if (self.app.cancel.is_set() or self.app.active is not job
                or job.get('case_id') != case['id'] or job.get('status') != 'running'):
            raise asyncio.CancelledError('The owning investigation is no longer active')

    def _live_output(self):
        session = self.manager.snapshot()['session']
        if (not session or not self._activity
                or any(session[key] != self._activity.get(key) for key in ('case_id','image_id','mode'))
                or session['id'] != self._activity.get('session_id')):
            return [], '', False
        entries = [entry for entry in session['entries'] if int(entry['id']) >= self._first_entry] if session else []
        output = ''.join(entry['text'] for entry in entries if entry['kind'] == 'output')
        truncated = bool(session and session['earlier_entries'] and
                         (not entries or int(entries[0]['id']) > self._first_entry))
        return entries, output, truncated

    def snapshot(self):
        if self._activity is None:
            return None
        value = copy.deepcopy(self._activity)
        if value['status'] in ('starting', 'running'):
            entries, output, truncated = self._live_output()
            # Hide complete/fragmented internal result markers from the reader.
            marker_at = output.find(self._marker) if self._marker else -1
            if marker_at >= 0:
                output = output[:marker_at]
            elif self._marker:
                for size in range(min(len(self._marker) - 1, len(output)), 0, -1):
                    if output.endswith(self._marker[:size]):
                        output = output[:-size]
                        break
            value['truncated'] = truncated or len(output) > MAX_OUTPUT
            value['entries'] = [{'id': value['id'] + '-command', 'kind': 'input', 'time': value['started_at'],
                                 'text': value['command']},
                                {'id': value['id'] + '-output', 'kind': 'output', 'time': value['started_at'],
                                 'text': output[-MAX_OUTPUT:]}]
            value['last_transcript_entry'] = entries[-1]['id'] if entries else None
        return value

    async def _ready(self, case, job, deadline):
        while True:
            self._current(case, job)
            state = self.manager.snapshot()
            session = state['session']
            if not state['busy']:
                raise ValueError((session or {}).get('error') or 'AI Volshell ended before returning to its prompt')
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError('AI Volshell exceeded its bounded command deadline')
            if session['ready']:
                return session
            await asyncio.sleep(.02)

    async def execute(self, case, job, data):
        call = validate_call(data)
        self._current(case, job)
        image = next((item for item in case['images'] if item['id'] == call['image_id']), None)
        if image is None:
            raise ValueError('Unknown image in the active case')
        if job.get('volshell_image_id') and job['volshell_image_id'] != call['image_id']:
            raise ValueError('This Volshell investigation is bound to another registered image')
        if self._lock.locked():
            raise ValueError('Wait for the current AI Volshell helper to finish')
        async with self._lock:
            self._current(case, job)
            count = self._counts.get(job['id'], 0)
            if count >= MAX_CALLS:
                raise ValueError('AI Volshell helper limit reached for this job; use saved output')
            self._counts[job['id']] = count + 1
            binding = (case['id'], job['id'], call['image_id'], call['mode'])
            if self._owner != binding:
                await self.manager.shutdown()
                self._owner = binding
            self._current(case, job)
            session = self.manager.snapshot()['session']
            reuse = bool(self.manager.busy and session and session['ready'])
            self._first_entry = int(session['entries'][-1]['id']) + 1 if reuse and session['entries'] else 1
            ident = uuid.uuid4().hex
            self._marker = '__WORKBENCH_VOLSHELL_RESULT_' + ident + '__:'
            self._activity = {'id': ident, 'case_id': case['id'], 'job_id': job['id'], **call,
                              'status': 'running' if reuse else 'starting', 'started_at': now(),
                              'finished_at': None, 'error': '', 'entries': [], 'truncated': False,
                              'evidence_status': 'exploratory_unverified', 'note': NOTE}
            if reuse:
                self._activity['session_id'] = session['id']
            self.app.event(case, 'volshell_agent_started', {key: self._activity[key] for key in
                           ('id', 'job_id', 'image_id', 'helper', 'arguments', 'reason', 'evidence_status')})
            deadline = asyncio.get_running_loop().time() + self.timeout
            try:
                if not reuse:
                    path = self.app.case_backend(case).resolve_input(image['path'])
                    directory = self.app.directory(case)
                    check_components(directory)
                    if directory.parent != self.app.root:
                        raise ValueError('AI Volshell case directory escapes state root')
                    await asyncio.wait_for(self.manager.start(case['id'], image['id'], path, call['mode'],
                                           self.app.config, directory),
                                           max(.001, deadline - asyncio.get_running_loop().time()))
                    self._activity['session_id'] = self.manager.snapshot()['session']['id']
                    session = await self._ready(case, job, deadline)
                self._activity['status'] = 'running'
                self._activity['session_id'] = session['id']
                self._activity['transcript_path'] = 'volshell/' + session['id'] + '/transcript.jsonl'
                self._activity['first_transcript_entry'] = str(self._first_entry)
                # Fixed transport wrapper; only validated upstream calls and
                # repr-escaped scalar values enter this program, never AI Python.
                program = ('try:\n    _wb_result = ' + call['command'] + '\n'
                           '    if _wb_result is not None: print(repr(_wb_result))\n'
                           'except Exception as _wb_error:\n'
                           '    print("\\n" + ' + repr(self._marker) + ' + "error:" + type(_wb_error).__name__ + ": " + str(_wb_error))\n'
                           'else:\n    print("\\n" + ' + repr(self._marker) + ' + "ok")')
                await asyncio.wait_for(self.manager.send(case['id'], session['id'], 'exec(' + repr(program) + ')'),
                                       max(.001, deadline - asyncio.get_running_loop().time()))
                await self._ready(case, job, deadline)
                _, raw, _ = self._live_output()
                result = raw.rsplit(self._marker, 1)[-1].split('\n', 1)[0] if self._marker in raw else ''
                if result != 'ok':
                    raise ValueError(('Upstream helper failed: ' + result[6:])[:2000] if result.startswith('error:')
                                     else 'Upstream helper returned without a valid completion record')
                self._activity = {**self.snapshot(), 'status': 'completed', 'finished_at': now()}
            except (Exception, asyncio.CancelledError) as exc:
                self._activity = {**self.snapshot(), 'status': 'cancelled' if isinstance(exc, asyncio.CancelledError) else 'failed',
                                  'finished_at': now(), 'error': (str(exc) or type(exc).__name__)[:2000]}
                await self.manager.shutdown()
                self._owner = None
                self._persist(case)
                if isinstance(exc, asyncio.CancelledError):
                    raise
                return self._result()
            try:
                self._persist(case)
            except Exception:
                await self.manager.shutdown()
                self._owner = None
                raise
            return self._result()

    def _persist(self, case):
        folder = private_dir(self.app.directory(case) / 'volshell-observations')
        path = folder / (self._activity['id'] + '.json')
        self._activity['observation_path'] = str(path.relative_to(self.app.directory(case)))
        atomic_json(path, self._activity)
        self._activity['observation_sha256'] = file_fingerprint(path)['sha256']
        self.app.event(case, 'volshell_agent_completed', {key: self._activity[key] for key in
                       ('id', 'job_id', 'image_id', 'status', 'error', 'observation_path', 'observation_sha256', 'evidence_status')})

    def _result(self):
        value = self.snapshot()
        value['output'] = ''.join(item['text'] for item in value.pop('entries') if item['kind'] == 'output')
        return value

    async def close_job(self, job_id):
        if self._owner and self._owner[1] == job_id:
            await self.manager.shutdown()
            self._owner = None
        self._counts.pop(job_id, None)

    async def shutdown(self):
        await self.manager.shutdown()
        self._owner = None
