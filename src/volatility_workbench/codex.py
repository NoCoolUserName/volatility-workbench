"""Replaceable Codex app-server stdio adapter; no credential handling or model API."""
from __future__ import annotations
import asyncio
import json
import os
import time
from pathlib import Path
import platform
import shutil


def child_environment():
    """GUI-safe child environment without inherited API keys or provider secrets."""
    allowed = {'HOME','USER','LOGNAME','PATH','TMPDIR','LANG','LC_ALL','LC_CTYPE',
               'SYSTEMROOT','WINDIR','APPDATA','LOCALAPPDATA','CODEX_HOME'}
    result = {key:value for key,value in os.environ.items() if key in allowed}
    result['PATH'] = os.pathsep.join(dict.fromkeys([
        '/opt/homebrew/bin', '/usr/local/bin', '/usr/bin', '/bin',
        *result.get('PATH','').split(os.pathsep)]))
    return result


def discover_codex(explicit=None):
    """Find the existing native CLI without sourcing a shell or installing software."""
    candidates = [Path(explicit).expanduser()] if explicit else [
        Path(p) for p in (shutil.which('codex'),
            '/opt/homebrew/bin/codex', '/usr/local/bin/codex',
            str(Path.home()/'.local/bin/codex'),
            '/Applications/Codex.app/Contents/Resources/codex') if p]
    for candidate in candidates:
        if not candidate.is_file() or not os.access(candidate, os.X_OK):
            continue
        resolved = candidate.resolve()
        if resolved.suffix == '.js':
            # Official npm launcher uses /usr/bin/env node. Prefer its own native
            # payload so Finder's PATH does not require Node or a shell startup.
            base = resolved.parent.parent
            arch = 'arm64' if platform.machine() in ('arm64','aarch64') else 'x64'
            system = 'darwin' if platform.system() == 'Darwin' else 'linux'
            matches = list((base/'node_modules'/'@openai'/('codex-'+system+'-'+arch)/'vendor').glob('*/bin/codex'))
            matches += list((base/'vendor').glob('*/codex/codex'))
            native = next((p for p in matches if p.is_file() and os.access(p, os.X_OK)), None)
            if native:
                return str(native.resolve())
            if shutil.which('node', path=child_environment()['PATH']):
                return str(resolved)
            continue
        return str(resolved)
    raise CodexError('Codex executable was not found. Select an installed Codex CLI in Settings; no account or billing configuration was changed.')


class CodexError(RuntimeError):
    pass


class CodexClient:
    def __init__(self, event, request, executable='codex'):
        self.event, self.request_handler = event, request
        self.executable = discover_codex(None if executable == 'codex' else executable)
        self.pending = {}
        self.counter = 0
        self.proc = None
        self.tasks = set()
        self.stderr_tail = ''

    async def start(self):
        # Reuse the user's supported login/provider. Do not set API keys, provider,
        # model, CODEX_HOME, or billing configuration.
        self.proc = await asyncio.create_subprocess_exec(
            self.executable, 'app-server', '--listen', 'stdio://',
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, limit=16 * 1024 * 1024, env=child_environment())
        self.reader = asyncio.create_task(self._read())
        self.errors = asyncio.create_task(self._stderr())
        await self.call('initialize', {'clientInfo': {'name': 'volatility_workbench',
            'title': 'Volatility Workbench', 'version': '0.1.0'},
            'capabilities': {'experimentalApi': True}})
        await self.send({'method': 'initialized', 'params': {}})

    async def send(self, message):
        if self.proc is None or self.proc.returncode is not None:
            raise CodexError('Codex app-server stopped. Restart the UI; saved case work is retained.')
        self.proc.stdin.write((json.dumps(message) + '\n').encode())
        await self.proc.stdin.drain()

    async def call(self, method, params=None, timeout=120):
        self.counter += 1
        ident = self.counter
        future = asyncio.get_running_loop().create_future()
        self.pending[ident] = future
        try:
            await self.send({'id': ident, 'method': method, 'params': params or {}})
            return await asyncio.wait_for(future, timeout)
        finally:
            self.pending.pop(ident, None)

    async def _read(self):
        try:
            while line := await self.proc.stdout.readline():
                message = json.loads(line)
                if 'method' in message:
                    if 'id' in message:
                        task = asyncio.create_task(self._request(message))
                        self.tasks.add(task)
                        task.add_done_callback(self.tasks.discard)
                    else:
                        await self.event(message['method'], message.get('params', {}))
                elif message.get('id') in self.pending:
                    future = self.pending[message['id']]
                    if not future.done():
                        if 'error' in message:
                            future.set_exception(CodexError(json.dumps(message['error'])))
                        else:
                            future.set_result(message.get('result', {}))
        except Exception as exc:
            self.stderr_tail += '\nProtocol error: ' + str(exc)
        finally:
            for future in list(self.pending.values()):
                if not future.done():
                    future.set_exception(CodexError('Codex connection closed: ' + self.stderr_tail[-2000:]))
            await self.event('workbench/disconnected', {'error': self.stderr_tail[-2000:]})

    async def _request(self, message):
        try:
            result = await self.request_handler(message)
            await self.send({'id': message['id'], 'result': result})
        except Exception as exc:
            await self.send({'id': message['id'], 'error': {'code': -32000, 'message': str(exc)}})

    async def _stderr(self):
        while data := await self.proc.stderr.read(8192):
            self.stderr_tail = (self.stderr_tail + data.decode(errors='replace'))[-16000:]

    async def close(self):
        if self.proc:
            if self.proc.returncode is None:
                self.proc.stdin.close()
                try:
                    await asyncio.wait_for(self.proc.wait(), 12)
                except asyncio.TimeoutError:
                    self.proc.terminate()
                    try:
                        await asyncio.wait_for(self.proc.wait(), 12)
                    except asyncio.TimeoutError:
                        self.proc.kill()
                        await self.proc.wait()
            for task in [self.reader, self.errors, *self.tasks]:
                task.cancel()
            await asyncio.gather(self.reader, self.errors, *self.tasks, return_exceptions=True)
