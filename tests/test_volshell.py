"""VolShell transport and HTTP use a toy Python console, never a memory analyzer."""
import asyncio
import hashlib
import hmac
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
import urllib.error
import urllib.request

from volatility_workbench.app import Workbench
from volatility_workbench.http import Server
from volatility_workbench.volshell import VolshellManager
from support import BackendFixture


FAKE_PYTHON = r'''import code, json, os, pathlib, signal, subprocess, sys, time
root = pathlib.Path(__file__).parent
with (root / "spawn.jsonl").open("a") as stream:
    stream.write(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd(), "env": dict(os.environ), "pid": os.getpid()}) + "\n")
mode = (root / "fixture-mode").read_text() if (root / "fixture-mode").exists() else "normal"
if mode == "failed":
    print("SYNTHETIC startup failure", file=sys.stderr, flush=True)
    sys.exit(7)
if mode == "stall":
    time.sleep(60)
if mode == "eof":
    print("SYNTHETIC early EOF", flush=True)
    sys.exit(0)
if mode == "split":
    os.write(1, b"UTF8: \xc3"); time.sleep(.02); os.write(1, b"\xa9\n")
sys.ps1 = "(fixture) >>> "
sys.ps2 = "... "
token = os.environ.pop("WORKBENCH_VOLSHELL_TOKEN", "fixture-missing-token")
def emit(count):
    sys.stdout.write("X" * count + "\n"); sys.stdout.flush()
def spawn_child():
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    (root / "child.pid").write_text(str(child.pid))
    print("SYNTHETIC child", child.pid, flush=True)
def stream_delayed():
    def wait_for_release(name):
        deadline = time.monotonic() + 15
        while not (root / name).exists():
            if time.monotonic() > deadline:
                raise RuntimeError("Synthetic output gate timed out")
            time.sleep(.005)
    os.write(1, b"PARTIAL \xc3")
    wait_for_release("release-unicode")
    os.write(1, b"\xa9 SECOND")
    wait_for_release("release-completion")
    os.write(1, b" COMPLETE\n")
class FixtureConsole(code.InteractiveConsole):
    def raw_input(self, prompt=""):
        marker = "\x1eWBVS:" + token + ":" + ("1" if prompt == sys.ps2 else "0") + "\x1f"
        if mode == "split":
            midpoint = len(marker) // 2
            sys.stderr.write(marker[:midpoint]); sys.stderr.flush(); time.sleep(.02)
            sys.stderr.write(marker[midpoint:]); sys.stderr.flush()
        else:
            sys.stderr.write(marker); sys.stderr.flush()
        if mode != "split":
            return super().raw_input(prompt)
        midpoint = len(prompt) // 2
        sys.stdout.write(prompt[:midpoint]); sys.stdout.flush(); time.sleep(.02)
        sys.stdout.write(prompt[midpoint:]); sys.stdout.flush()
        line = sys.stdin.readline()
        if not line: raise EOFError()
        return line.rstrip("\n")
console = FixtureConsole({"emit": emit, "sleep": time.sleep, "spawn_child": spawn_child,
                          "stream_delayed": stream_delayed})
console.interact(banner="SYNTHETIC VolShell transport fixture; no image is opened.")
'''


def make_fake_python(root):
    path = root / 'fake python'
    path.write_text('#!' + sys.executable + '\n' + FAKE_PYTHON)
    path.chmod(0o700)
    return path


async def wait_until(predicate, timeout=4):
    end = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() > end:
            raise AssertionError('Synthetic VolShell condition did not become true')
        await asyncio.sleep(.01)


def session_text(manager):
    return ''.join(entry['text'] + ('' if entry['kind'] == 'output' else '\n')
                   for entry in manager.snapshot()['session']['entries'])


class VolshellManagerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='volshell fixture ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.image = self.root / 'synthetic memory.raw'
        self.image.write_bytes(b'SYNTHETIC fixture, never parsed')
        self.config = SimpleNamespace(vol_python=make_fake_python(self.root),
            symbols=self.root / 'symbols', cache_path=self.root / 'cache')
        self.config.symbols.mkdir()
        self.directory = self.root / 'case'
        self.directory.mkdir()
        self.spawned = []
        self.spawn_calls = []
        async def spawn(*argv, **kwargs):
            self.spawn_calls.append((argv, kwargs))
            process = await asyncio.create_subprocess_exec(*argv, **kwargs)
            self.spawned.append(process)
            return process
        self.manager = VolshellManager(spawn=spawn, startup_timeout=.6, stop_timeout=.2)
        self.addAsyncCleanup(self.manager.shutdown)
        self.addAsyncCleanup(self.force_fixture_cleanup)

    async def force_fixture_cleanup(self):
        for process in self.spawned:
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            await asyncio.wait_for(process.wait(), 2)

    async def start(self, mode='windows'):
        await self.manager.start('case', 'E001', self.image, mode, self.config, self.directory)
        await wait_until(lambda: self.manager.snapshot()['session']['ready'])
        return self.manager.snapshot()['session']['id']

    async def send_ready(self, ident, text):
        await self.manager.send('case', ident, text)
        await wait_until(lambda: self.manager.snapshot()['session']['ready'])

    async def test_exact_startup_and_persistent_python_commands(self):
        with patch.dict(os.environ, {'PYTHONPATH':'PRIVATE_UNTRUSTED_PATH',
                'PYTHONSTARTUP':'PRIVATE_STARTUP', 'OPENAI_API_KEY':'PRIVATE_SECRET'}):
            ident = await self.start()
        argv, options = self.spawn_calls[0]
        self.assertEqual(argv[0], str(self.config.vol_python))
        self.assertIn('-u', argv)
        self.assertIn('-c', argv)
        self.assertIn('--offline', argv)
        self.assertIn('-w', argv)
        self.assertEqual(argv[argv.index('-f') + 1], str(self.image))
        self.assertEqual(options['stdin'], asyncio.subprocess.PIPE)
        self.assertEqual(options['stdout'], asyncio.subprocess.PIPE)
        self.assertEqual(options['stderr'], asyncio.subprocess.STDOUT)
        self.assertTrue(options['start_new_session'])
        self.assertEqual(Path(options['cwd']), self.directory / 'volshell' / ident / 'output')
        for secret in ('PYTHONPATH', 'PYTHONSTARTUP', 'OPENAI_API_KEY'):
            self.assertNotIn(secret, options['env'])
        self.assertEqual(self.image.read_bytes(), b'SYNTHETIC fixture, never parsed')
        self.assertTrue(self.manager.snapshot()['busy'])
        self.assertIn('(fixture) >>> ', session_text(self.manager))
        await self.send_ready(ident, 'value = 41')
        await self.send_ready(ident, 'print(value + 1)')
        self.assertIn('42', session_text(self.manager))
        await self.send_ready(ident, "for number in range(2):\n    print('MULTILINE', number)")
        self.assertIn('MULTILINE 0', session_text(self.manager))
        self.assertIn('MULTILINE 1', session_text(self.manager))
        await self.send_ready(ident, 'for item in range(2):\n    value = item')
        self.assertFalse(self.manager.snapshot()['session']['continuation'])
        await self.send_ready(ident, 'print("SILENT BLOCK", value)')
        self.assertIn('SILENT BLOCK 1', session_text(self.manager))
        await self.send_ready(ident, 'for number in range(1):')
        self.assertTrue(self.manager.snapshot()['session']['continuation'])
        await self.send_ready(ident, '    print("CONTINUATION", number)')
        await self.send_ready(ident, '')
        self.assertFalse(self.manager.snapshot()['session']['continuation'])
        self.assertIn('CONTINUATION 0', session_text(self.manager))
        transcript = self.directory / 'volshell' / ident / 'transcript.jsonl'
        self.assertTrue(transcript.is_file())
        self.assertIn('print(value + 1)', transcript.read_text())

    async def test_binding_validation_one_session_and_no_automatic_restart(self):
        ident = await self.start()
        for case_id, session_id in (('wrong-case', ident), ('case', 'stale-session')):
            with self.subTest(case=case_id, session=session_id):
                for method, args in ((self.manager.send, ('print(1)',)),
                        (self.manager.interrupt, ()), (self.manager.close, ())):
                    with self.assertRaises(ValueError):
                        await method(case_id, session_id, *args)
        for text in ('', 'x' * 8193, 'é' * 4097, '\x00', '\x1b[31m', 42):
            with self.subTest(text=str(text)[:30]), self.assertRaises(ValueError):
                await self.manager.send('case', ident, text)
        with self.assertRaises(ValueError):
            await self.manager.start('other', 'E001', self.image, 'linux', self.config, self.directory)
        self.assertEqual(len(self.spawn_calls), 1)
        await self.manager.close('case', ident)
        self.assertFalse(self.manager.snapshot()['busy'])
        self.assertTrue(all(process.returncode is not None for process in self.spawned))
        replacement = VolshellManager()
        self.assertIsNone(replacement.snapshot()['session'])
        self.assertEqual(len(self.spawn_calls), 1, 'Reading prior session files never starts a process')

    async def test_output_bounded_and_interrupt_returns_to_prompt(self):
        ident = await self.start()
        await self.send_ready(ident, 'emit(400000)')
        view = self.manager.snapshot()['session']
        self.assertLessEqual(sum(len(e['text']) for e in view['entries']), 128000)
        self.assertGreater(view['earlier_entries'], 0)
        await self.manager.send('case', ident, 'sleep(60)')
        with self.assertRaises(ValueError):
            await self.manager.send('case', ident, 'print("too early")')
        await asyncio.sleep(.05)
        await self.manager.interrupt('case', ident)
        await wait_until(lambda: self.manager.snapshot()['session']['ready'])
        self.assertIn('KeyboardInterrupt', session_text(self.manager))
        await self.send_ready(ident, 'print("AFTER INTERRUPT")')
        self.assertIn('AFTER INTERRUPT', session_text(self.manager))

    async def test_exit_start_failure_and_startup_timeout_reap_processes(self):
        ident = await self.start()
        await self.manager.send('case', ident, 'exit()')
        await wait_until(lambda: not self.manager.snapshot()['busy'])
        self.assertIsNotNone(self.manager.snapshot()['session']['finished_at'])
        for mode in ('failed', 'eof', 'stall'):
            with self.subTest(mode=mode):
                (self.root / 'fixture-mode').write_text(mode)
                await self.manager.start('case', 'E001', self.image, 'generic', self.config, self.directory)
                await wait_until(lambda: not self.manager.snapshot()['busy'])
                view = self.manager.snapshot()['session']
                self.assertFalse(view['ready'])
                self.assertIsNotNone(view['finished_at'])
                self.assertIsNotNone(self.spawned[-1].returncode)
                if mode == 'failed':
                    self.assertEqual(view['returncode'], 7)
                    self.assertIn('SYNTHETIC startup failure', session_text(self.manager))

    async def test_rejects_unknown_modes_and_symlinked_output_root(self):
        with self.assertRaises(ValueError):
            await self.manager.start('case', 'E001', self.image, 'not-an-os', self.config, self.directory)
        outside = self.root / 'outside'
        outside.mkdir()
        (self.directory / 'volshell').symlink_to(outside, target_is_directory=True)
        with self.assertRaises((ValueError, OSError)):
            await self.manager.start('case', 'E001', self.image, 'windows', self.config, self.directory)
        self.assertFalse(self.spawn_calls)
        self.assertEqual(list(outside.iterdir()), [])

    async def test_mode_flags_are_explicit_and_starting_rejects_input(self):
        for mode, flag in (('linux', '-l'), ('mac', '-m'), ('generic', None)):
            ident = await self.start(mode)
            argv = self.spawn_calls[-1][0]
            self.assertEqual([item for item in argv if item in ('-w', '-l', '-m')], [flag] if flag else [])
            await self.manager.close('case', ident)
        (self.root / 'fixture-mode').write_text('stall')
        await self.manager.start('case', 'E001', self.image, 'generic', self.config, self.directory)
        ident = self.manager.snapshot()['session']['id']
        with self.assertRaises(ValueError):
            await self.manager.send('case', ident, 'print("before prompt")')

    async def test_cancelled_start_reaps_child_created_during_cancellation(self):
        spawning, release = asyncio.Event(), asyncio.Event()
        original_spawn = self.manager._spawn
        async def delayed_spawn(*args, **kwargs):
            process = await original_spawn(*args, **kwargs)
            spawning.set()
            await release.wait()
            return process
        manager = VolshellManager(spawn=delayed_spawn, startup_timeout=.6, stop_timeout=.2)
        self.addAsyncCleanup(manager.shutdown)
        pending = asyncio.create_task(manager.start('case', 'E001', self.image, 'generic', self.config, self.directory))
        await spawning.wait()
        pending.cancel(); release.set()
        with self.assertRaises(asyncio.CancelledError):
            await pending
        self.assertFalse(manager.busy)
        self.assertIsNotNone(self.spawned[-1].returncode)

    async def test_interpreter_exit_reaps_descendants_holding_output_pipe(self):
        ident = await self.start()
        await self.send_ready(ident, 'spawn_child()')
        await self.manager.send('case', ident, 'exit()')
        await wait_until(lambda: not self.manager.busy)
        self.assertIsNotNone(self.spawned[-1].returncode)
        self.assertFalse(self.manager.snapshot()['session']['ready'])

    async def test_prompt_and_utf8_chunk_fragmentation(self):
        (self.root / 'fixture-mode').write_text('split')
        ident = await self.start()
        self.assertIn('UTF8: é', session_text(self.manager))
        self.assertNotIn('�', session_text(self.manager))
        await self.send_ready(ident, 'print("SPLIT PROMPT")')
        self.assertIn('SPLIT PROMPT', session_text(self.manager))
        transcript = self.directory / 'volshell' / ident / 'transcript.jsonl'
        self.assertNotIn('WBVS:', transcript.read_text())
        self.assertNotIn('WBVS:', session_text(self.manager))

    async def test_partial_output_is_visible_before_command_completion(self):
        ident = await self.start()
        previous = int(self.manager.snapshot()['session']['entries'][-1]['id'])
        def output():
            return ''.join(item['text'] for item in self.manager.snapshot()['session']['entries']
                           if item['kind'] == 'output' and int(item['id']) > previous)
        await self.manager.send('case', ident, 'stream_delayed()')
        # The fixture cannot finish until these independent gates are released.
        # Each write is much smaller than 4096 bytes and has no trailing newline.
        await wait_until(lambda: 'PARTIAL ' in output())
        self.assertTrue(output().endswith('PARTIAL '))
        self.assertNotIn('�', output())
        self.assertNotIn('SECOND', output())
        self.assertFalse(self.manager.snapshot()['session']['ready'])
        self.assertEqual(self.manager.snapshot()['session']['status'], 'running')
        transcript = self.directory / 'volshell' / ident / 'transcript.jsonl'
        retained = ''.join(item['text'] for item in map(json.loads, transcript.read_text().splitlines())
                           if item['kind'] == 'output')
        self.assertIn('PARTIAL ', retained, 'The private transcript is flushed before completion too')
        (self.root / 'release-unicode').touch()
        await wait_until(lambda: 'PARTIAL é SECOND' in output())
        self.assertTrue(output().endswith('PARTIAL é SECOND'))
        self.assertNotIn('�', output())
        self.assertNotIn('COMPLETE', output())
        self.assertFalse(self.manager.snapshot()['session']['ready'])
        (self.root / 'release-completion').touch()
        await wait_until(lambda: self.manager.snapshot()['session']['ready'])
        self.assertIn('PARTIAL é SECOND COMPLETE\n', output())
        self.assertNotIn('WBVS:', output())

    async def test_printed_prompt_lookalike_cannot_enable_input_while_running(self):
        ident = await self.start()
        await self.manager.send('case', ident, "print('(fake) >>> ', end='', flush=True); sleep(.2); print('FINISHED')")
        await wait_until(lambda: '(fake) >>> ' in ''.join(item['text'] for item in
            self.manager.snapshot()['session']['entries'] if item['kind'] == 'output'))
        self.assertFalse(self.manager.snapshot()['session']['ready'])
        with self.assertRaises(ValueError):
            await self.manager.send('case', ident, 'print("early")')
        await wait_until(lambda: self.manager.snapshot()['session']['ready'])
        self.assertIn('FINISHED', session_text(self.manager))

    async def test_unavailable_process_groups_fail_only_when_connecting(self):
        with patch('volatility_workbench.volshell.os.killpg', None):
            manager = VolshellManager()
            self.assertEqual(manager.snapshot(), {'session':None, 'busy':False})
            with self.assertRaisesRegex(ValueError, 'process-group'):
                await manager.start('case', 'E001', self.image, 'generic', self.config, self.directory)
        self.assertEqual(list(self.directory.iterdir()), [])


class VolshellHttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fixture = BackendFixture(); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        # Reuse only the harmless fixture's registration/configuration scaffolding.
        self.fixture.fake.write_text('#!' + sys.executable + '\n' + FAKE_PYTHON)
        config = self.fixture.root / 'config.json'
        config.write_text(json.dumps(self.fixture.config.to_dict()))
        self.app = Workbench(config, self.fixture.root / 'ui')
        self.case = self.app.add([str(self.fixture.image)])[0]
        second = self.fixture.evidence / 'second.raw'; second.write_text('SYNTHETIC second image')
        self.other = self.app.add([str(second)])[0]
        self.addAsyncCleanup(self.app.volshell.shutdown)
        self.server = Server(self.app, 0, asyncio.get_running_loop())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addAsyncCleanup(self.close_server)
        self.cookie = 'volatility_ui=' + self.server.token

    async def close_server(self):
        await asyncio.to_thread(self.server.shutdown)
        self.server.server_close()

    async def request(self, path, body=None, authenticated=True, origin=True, extra_headers=None):
        def send():
            headers = {'Content-Type':'application/json'}
            if authenticated: headers['Cookie'] = self.cookie
            if origin: headers['Origin'] = self.server.origin if origin is True else origin
            if extra_headers: headers.update(extra_headers)
            request = urllib.request.Request(self.server.origin + path,
                data=json.dumps(body).encode() if body is not None else None, headers=headers)
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            try:
                with opener.open(request, timeout=5) as response:
                    return response.status, json.load(response)
            except urllib.error.HTTPError as error:
                try:
                    return error.code, json.load(error)
                finally:
                    error.close()
        return await asyncio.to_thread(send)

    async def start(self):
        status, body = await self.request('/api/volshell/start',
            {'case_id':self.case['id'], 'image_id':'E001', 'mode':'windows'})
        self.assertEqual(status, 200, body)
        await wait_until(lambda: self.app.volshell.snapshot()['session']['ready'])
        return self.app.volshell.snapshot()['session']['id']

    async def open_stream(self, case_id):
        def connect():
            request = urllib.request.Request(self.server.origin + '/api/volshell/events?case=' + case_id,
                headers={'Cookie':self.cookie, 'Origin':self.server.origin})
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            response = opener.open(request, timeout=3)
            self.assertEqual(response.headers.get_content_type(), 'text/event-stream')
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            return response
        response = await asyncio.to_thread(connect)
        self.addCleanup(response.close)
        return response

    async def stream_event(self, response):
        def read():
            event, data = '', []
            while True:
                line = response.readline()
                if not line:
                    raise AssertionError('SSE closed before the expected fixture event')
                text = line.decode('utf-8').rstrip('\r\n')
                if not text:
                    if data:
                        self.assertEqual(event, 'volshell')
                        return json.loads('\n'.join(data))
                    continue
                if text.startswith('event: '): event = text[7:]
                if text.startswith('data: '): data.append(text[6:])
        return await asyncio.to_thread(read)

    async def test_sse_auth_case_binding_and_incremental_partial_output(self):
        endpoint = '/api/volshell/events?case=' + self.case['id']
        for kwargs in ({'authenticated':False}, {'origin':'https://example.invalid'}):
            status, _ = await self.request(endpoint, **kwargs)
            self.assertEqual(status, 403)
        for endpoint in ('/api/volshell/events', '/api/volshell/events?case=missing'):
            status, _ = await self.request(endpoint)
            self.assertEqual(status, 400)
        ident = await self.start()
        own, other = await self.open_stream(self.case['id']), await self.open_stream(self.other['id'])
        initial = await self.stream_event(own)
        self.assertEqual(initial['case_id'], self.case['id'])
        self.assertEqual(initial['session']['id'], ident)
        hidden = await self.stream_event(other)
        self.assertEqual(hidden['case_id'], self.other['id'])
        self.assertIsNone(hidden['session'])
        self.assertTrue(hidden['busy'], 'Global occupancy is visible without exposing another case transcript')
        self.assertNotIn('SYNTHETIC VolShell transport', json.dumps(hidden))
        async def until(predicate):
            for _ in range(20):
                frame = await self.stream_event(own)
                if predicate(frame): return frame
            self.fail('Too many stream frames without the expected output')
        output = lambda frame: ''.join(item['text'] for item in frame['session']['entries'] if item['kind'] == 'output')
        await self.app.volshell.send(self.case['id'], ident, 'stream_delayed()')
        partial = await until(lambda frame: 'PARTIAL ' in output(frame))
        self.assertTrue(output(partial).endswith('PARTIAL '))
        self.assertFalse(partial['session']['ready'])
        self.assertNotIn('�', output(partial))
        (self.fixture.root / 'release-unicode').touch()
        unicode = await until(lambda frame: 'PARTIAL é SECOND' in output(frame))
        self.assertFalse(unicode['session']['ready'])
        self.assertNotIn('COMPLETE', output(unicode))
        self.assertNotIn('�', output(unicode))
        # Reconnection starts with current bounded state, not a replayed command.
        resumed = await self.open_stream(self.case['id'])
        replay = await self.stream_event(resumed)
        self.assertIn('PARTIAL é SECOND', output(replay))
        self.assertFalse(replay['session']['ready'])
        (self.fixture.root / 'release-completion').touch()
        complete = await until(lambda frame: frame['session']['ready'])
        self.assertIn('PARTIAL é SECOND COMPLETE\n', output(complete))
        await self.app.volshell.close(self.case['id'], ident)
        terminal = await until(lambda frame: frame['session']['status'] == 'closed')
        self.assertFalse(terminal['busy'])
        self.assertFalse(terminal['session']['ready'])
        self.assertEqual(len((self.fixture.root / 'spawn.jsonl').read_text().splitlines()), 1)
        activity = {'id':'observation', 'case_id':self.case['id'], 'job_id':'fixture-job',
                    'status':'running', 'entries':[{'kind':'output', 'text':'PRIVATE AI OBSERVATION'}]}
        with patch.object(self.app, 'volshell_agent', SimpleNamespace(snapshot=lambda: activity), create=True):
            agent_stream = await self.open_stream(self.case['id'])
            agent_view = await self.stream_event(agent_stream)
            self.assertEqual(agent_view['agent_activity'], activity)
            self.assertNotIn('investigation', agent_view, 'SSE carries bounded terminal state, not complete job history')
            hidden_stream = await self.open_stream(self.other['id'])
            hidden = await self.stream_event(hidden_stream)
            self.assertIsNone(hidden['agent_activity'])
            self.assertNotIn('PRIVATE AI OBSERVATION', json.dumps(hidden))

    async def test_sse_connection_count_is_bounded(self):
        streams = [await self.open_stream(self.case['id']) for _ in range(8)]
        for response in streams:
            self.assertIsNone((await self.stream_event(response))['session'])
        status, body = await self.request('/api/volshell/events?case=' + self.case['id'])
        self.assertEqual(status, 429)
        self.assertIn('Too many', body['error'])
        self.assertFalse((self.fixture.root / 'spawn.jsonl').exists())
        for response in streams:
            response.close()
        replacement = None
        deadline = asyncio.get_running_loop().time() + 1
        while asyncio.get_running_loop().time() < deadline:
            try:
                replacement = await self.open_stream(self.case['id'])
                break
            except urllib.error.HTTPError as error:
                self.assertEqual(error.code, 429)
                error.close()
                await asyncio.sleep(.05)
        self.assertIsNotNone(replacement, 'Closed streams must promptly release capacity for case changes/reopening')

    async def test_internal_bridge_requires_case_capability_and_local_origin(self):
        token = hmac.new(self.app.volshell_bridge_secret, self.case['id'].encode(), hashlib.sha256).hexdigest()
        headers = {'Authorization':'Bearer ' + token}
        arguments = {'image_id':'E001', 'action':'ps'}
        body = {'case_id':self.case['id'], 'request_id':'1' * 32, 'arguments':arguments}
        with patch.object(self.app, 'run_agent_volshell', new=AsyncMock(return_value={'status':'completed'}), create=True) as run:
            for invalid, options in (
                    (body, {'extra_headers':{'Authorization':'Bearer wrong'}}),
                    (body, {}),
                    ({**body, 'case_id':self.other['id']}, {'extra_headers':headers}),
                    (body, {'extra_headers':headers, 'origin':False}),
                    (body, {'extra_headers':headers, 'origin':'https://example.invalid'})):
                status, _ = await self.request('/api/internal/volshell', invalid, authenticated=False, **options)
                self.assertEqual(status, 403)
            run.assert_not_awaited()
            status, _ = await self.request('/api/internal/volshell', {**body, 'request_id':'bad'},
                authenticated=False, extra_headers=headers)
            self.assertEqual(status, 400)
            run.assert_not_awaited()
            status, result = await self.request('/api/internal/volshell', body,
                authenticated=False, extra_headers=headers)
            self.assertEqual(status, 200, result)
            self.assertEqual(result, {'status':'completed'})
            run.assert_awaited_once_with(self.case['id'], arguments)
            self.assertFalse(self.server.bridge_requests, 'Completed requests leave no cancellation registry entry')
        self.assertFalse((self.fixture.root / 'spawn.jsonl').exists())

    async def test_http_authority_image_binding_and_explicit_input(self):
        body = {'case_id':self.case['id'], 'image_id':'E001', 'mode':'windows'}
        for kwargs in ({'authenticated':False}, {'origin':False}, {'origin':'https://example.invalid'}):
            status, _ = await self.request('/api/volshell/start', body, **kwargs)
            self.assertEqual(status, 403)
        for invalid in ({**body, 'image_id':'missing'}, {**body, 'image_id':str(self.fixture.image)},
                {**body, 'case_id':'missing-case'}, {**body, 'mode':'shell'}):
            status, _ = await self.request('/api/volshell/start', invalid)
            self.assertEqual(status, 400)
        self.assertFalse((self.fixture.root / 'spawn.jsonl').exists())
        ident = await self.start()
        status, snapshot = await self.request('/api/volshell?case=' + self.other['id'])
        self.assertEqual(status, 200)
        self.assertEqual(snapshot['session']['case_id'], self.case['id'], 'Global busy state retains its explicit owning case')
        for route in ('input', 'interrupt', 'close'):
            status, _ = await self.request('/api/volshell/' + route,
                {'case_id':self.other['id'], 'session_id':ident, 'text':'print("wrong case")'})
            self.assertEqual(status, 400)
        status, _ = await self.request('/api/volshell/input',
            {'case_id':self.case['id'], 'session_id':ident, 'text':'print("EXPLICIT USER INPUT")'})
        self.assertEqual(status, 200)
        await wait_until(lambda: self.app.volshell.snapshot()['session']['ready'])
        self.assertIn('EXPLICIT USER INPUT', session_text(self.app.volshell))
        status, _ = await self.request('/api/volshell/close', {'case_id':self.case['id'], 'session_id':ident})
        self.assertEqual(status, 200)
        self.assertFalse(self.app.volshell.busy)
        self.assertEqual(self.fixture.image.read_text(), 'normal')

    async def test_ai_suggestions_do_not_submit_and_stale_reply_is_discarded(self):
        ident = await self.start()
        request = {'case_id':self.case['id'], 'session_id':ident, 'text':'Show available layers'}
        with patch('volatility_workbench.volshell_assist.suggest', new=AsyncMock(return_value={
                'command':'list(context.layers)', 'explanation':'Lists loaded layer names.'})), \
                patch.object(self.app.volshell, 'send', side_effect=AssertionError('AI must not execute')):
            status, suggestion = await self.request('/api/volshell/suggest', request)
        self.assertEqual(status, 200, suggestion)
        self.assertEqual(suggestion['command'], 'list(context.layers)')
        self.assertEqual(suggestion['session_id'], ident)
        self.assertNotIn('list(context.layers)', session_text(self.app.volshell))
        started, release = asyncio.Event(), asyncio.Event()
        async def slow(*args):
            started.set(); await release.wait()
            return {'command':'print("stale")', 'explanation':'SYNTHETIC'}
        with patch('volatility_workbench.volshell_assist.suggest', side_effect=slow):
            pending = asyncio.create_task(self.app.suggest_volshell(self.case['id'], ident, 'SYNTHETIC question'))
            await started.wait()
            with self.assertRaises(ValueError):
                await self.app.suggest_volshell(self.case['id'], ident, 'Duplicate request')
            await self.app.volshell.close(self.case['id'], ident)
            release.set()
            with self.assertRaises(ValueError):
                await pending
        self.assertIsNone(self.app.volshell_assistance)

    async def test_active_jobs_maintenance_and_registered_image_escape_are_blocked(self):
        self.app.state['jobs'] = [{'id':'busy', 'status':'queued'}]
        with self.assertRaises(ValueError):
            await self.app.start_volshell(self.case['id'], 'E001', 'windows')
        self.app.state['jobs'].clear()
        self.app.settings_manager = SimpleNamespace(busy=True)
        with self.assertRaises(ValueError):
            await self.app.start_volshell(self.case['id'], 'E001', 'windows')
        self.app.settings_manager.busy = False
        self.case['images'][0]['path'] = str(self.fixture.root / 'not-registered.raw')
        with self.assertRaises((ValueError, OSError)):
            await self.app.start_volshell(self.case['id'], 'E001', 'windows')
        self.assertFalse((self.fixture.root / 'spawn.jsonl').exists())

    async def test_ai_investigation_is_explicit_case_bound_and_preserves_approvals(self):
        ident = await self.start()
        request = {'case_id':self.case['id'], 'session_id':ident,
            'text':'Explain the saved synthetic process evidence', 'request_id':'synthetic-ai-request'}
        await self.app.volshell.send(self.case['id'], ident, 'sleep(60)')
        status, _ = await self.request('/api/volshell/investigate', request)
        self.assertEqual(status, 400, 'AI waits for the manual console prompt')
        self.assertFalse(self.app.state['jobs'])
        await asyncio.sleep(.05)
        await self.app.volshell.interrupt(self.case['id'], ident)
        await wait_until(lambda: self.app.volshell.snapshot()['session']['ready'])
        for invalid in ({**request, 'case_id':self.other['id']},
                {**request, 'session_id':'stale'}, {**request, 'request_id':[]},
                {**request, 'text':''}):
            status, _ = await self.request('/api/volshell/investigate', invalid)
            self.assertEqual(status, 400)
        with patch.object(self.app.volshell, 'send', side_effect=AssertionError('AI investigation must not inject Python')):
            status, job = await self.request('/api/volshell/investigate', request)
            self.assertEqual(status, 200, job)
            self.assertEqual(job['kind'], 'question')
            self.assertEqual(job['case_id'], self.case['id'])
            self.assertEqual(job['volshell_session_id'], ident)
            self.assertEqual(job['volshell_image_id'], 'E001')
            self.assertEqual(self.app.queue.qsize(), 1, 'Only the explicit investigation enters the existing case queue')
            status, duplicate = await self.request('/api/volshell/investigate', request)
            self.assertEqual(status, 200)
            self.assertEqual(duplicate['id'], job['id'])
            self.assertEqual(self.app.queue.qsize(), 1)
            for route, body in (
                    ('/api/volshell/input', {**request, 'text':'print("do not execute")'}),
                    ('/api/volshell/suggest', request),
                    ('/api/volshell/close', request),
                    ('/api/jobs', {'case_id':self.case['id'], 'kind':'readiness'})):
                status, _ = await self.request(route, body)
                self.assertEqual(status, 400)
            self.assertEqual(len(self.app.state['jobs']), 1)
            self.assertTrue(self.app.volshell.busy)
            active = self.app.state['jobs'][0]
            active['status'] = 'running'; self.app.active = active
            self.case['thread_id'] = 'synthetic-ai-thread'
            pending = asyncio.create_task(self.app.agent_request({
                'method':'item/commandExecution/requestApproval',
                'params':{'threadId':'synthetic-ai-thread', 'command':'SYNTHETIC proposed action'}}))
            await wait_until(lambda: bool(self.app.approvals))
            self.assertFalse(pending.done(), 'AI investigation preserves explicit user approvals')
            approval = next(iter(self.app.approvals))
            status, _ = await self.request('/api/approval', {'id':approval, 'answer':'decline'})
            self.assertEqual(status, 200)
            self.assertEqual(await pending, {'decision':'decline'})
            self.app.active = None
        active['status'] = 'completed'
        self.case['messages'] += [
            {'role':'assistant', 'text':'Unrelated prior message', 'job_id':'other-job'},
            {'role':'assistant', 'text':'SYNTHETIC scoped answer', 'job_id':job['id']}]
        self.case['activity'].append({'id':'tool-record', 'time':'2026-10-18T00:00:00Z',
            'job_id':job['id'], 'kind':'local_tool_completed',
            'detail':{'tool':'synthetic', 'output':'SYNTHETIC bounded tool output'}})
        snapshot = self.app.volshell_snapshot()
        self.assertEqual(snapshot['investigation']['job']['id'], job['id'])
        self.assertEqual(snapshot['investigation']['messages'], [{'role':'assistant', 'text':'SYNTHETIC scoped answer'}])
        self.assertIn('SYNTHETIC bounded tool output', json.dumps(snapshot['investigation']['console']))
        self.assertNotIn('Unrelated prior message', json.dumps(snapshot))
        next_job = self.app.investigate_volshell(self.case['id'], ident, 'SYNTHETIC follow-up', 'next-ai-request')
        self.assertNotEqual(next_job['id'], job['id'])
        self.assertFalse(self.app.volshell_snapshot()['investigation']['messages'])
        await self.app.stop()
        self.assertEqual(next_job['status'], 'cancelled')
        self.assertFalse(self.app.volshell.busy)
