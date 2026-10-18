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


# JSON-RPC records can contain large saved tool results. Read bounded chunks rather
# than StreamReader.readline(), whose small transport limit also limits a record.
# Reject oversized records explicitly; never truncate JSON or conversation history.
MAX_MESSAGE_BYTES = 128 * 1024 * 1024
READ_CHUNK_BYTES = 64 * 1024


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
        self.failure = None
        self._closing = False

    @property
    def connected(self):
        return (self.proc is not None and self.proc.returncode is None
                and not self.failure and not self._closing
                and hasattr(self, 'reader') and not self.reader.done())

    async def start(self):
        # Reuse the user's supported login/provider. Do not set API keys, provider,
        # model, CODEX_HOME, or billing configuration.
        self.proc = await asyncio.create_subprocess_exec(
            self.executable, 'app-server', '--listen', 'stdio://',
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, limit=READ_CHUNK_BYTES, env=child_environment())
        self.reader = asyncio.create_task(self._read())
        self.errors = asyncio.create_task(self._stderr())
        try:
            await self.call('initialize', {'clientInfo': {'name': 'volatility_workbench',
                'title': 'Volatility Workbench', 'version': '0.1.0'},
                'capabilities': {'experimentalApi': True}})
            await self.send({'method': 'initialized', 'params': {}})
        except BaseException:
            await self.close()
            raise

    async def send(self, message):
        if not self.connected:
            raise CodexError(self.failure or 'Codex app-server is disconnected; retry to reconnect. Saved case work is retained.')
        try:
            self.proc.stdin.write((json.dumps(message) + '\n').encode())
            await self.proc.stdin.drain()
        except (BrokenPipeError, ConnectionResetError) as exc:
            raise CodexError('Codex app-server closed its input connection') from exc

    async def call(self, method, params=None, timeout=120):
        self.counter += 1
        ident = self.counter
        future = asyncio.get_running_loop().create_future()
        self.pending[ident] = future
        try:
            await self.send({'id': ident, 'method': method, 'params': params or {}})
            try:
                return await asyncio.wait_for(future, timeout)
            except asyncio.TimeoutError as exc:
                raise CodexError(f'Codex {method} timed out after {timeout:g} seconds waiting for the app-server response') from exc
        finally:
            self.pending.pop(ident, None)

    async def _message(self, line):
        message = json.loads(line)
        if not isinstance(message, dict):
            raise CodexError('Expected a JSON-RPC object')
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

    async def _read(self):
        record = bytearray()
        reason = 'Codex app-server closed its output connection'
        try:
            while chunk := await self.proc.stdout.read(READ_CHUNK_BYTES):
                # Split only the new chunk, avoiding repeated scans of a growing
                # multi-megabyte record. At most one bounded record is buffered.
                parts = chunk.split(b'\n')
                for index, part in enumerate(parts):
                    if len(record) + len(part) > MAX_MESSAGE_BYTES:
                        raise CodexError(f'JSON-RPC record exceeds the {MAX_MESSAGE_BYTES:,}-byte limit')
                    record.extend(part)
                    if index < len(parts) - 1:
                        await self._message(record)
                        record.clear()
            if record:
                raise CodexError('Incomplete JSON-RPC record at end of connection')
        except Exception as exc:
            reason = 'Codex protocol error: ' + (str(exc) or type(exc).__name__)
        finally:
            if not self._closing:
                self.failure = reason + (': ' + self.stderr_tail[-2000:] if self.stderr_tail else '')
                # A live subprocess with a dead reader cannot answer future calls.
                # Stop it immediately; connect() creates a fresh transport on retry.
                if self.proc.returncode is None:
                    try:
                        self.proc.kill()
                    except ProcessLookupError:
                        pass
                for future in list(self.pending.values()):
                    if not future.done():
                        future.set_exception(CodexError(self.failure))
                # Drain remaining pipe bytes after killing, without accumulating
                # them, so paused StreamReader buffers cannot delay process exit.
                try:
                    async def discard():
                        while await self.proc.stdout.read(READ_CHUNK_BYTES):
                            pass
                    await asyncio.wait_for(discard(), 2)
                except (OSError, asyncio.TimeoutError):
                    pass
                await self.event('workbench/disconnected', {'error': self.failure})

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
        self._closing = True
        for future in list(self.pending.values()):
            if not future.done():
                future.set_exception(CodexError(self.failure or 'Codex app-server connection was closed'))
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
