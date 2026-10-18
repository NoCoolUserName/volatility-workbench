"""Case-bound transport for the installed upstream Volshell, not a Python sandbox.

The caller resolves the registered image through the public core API and owns
application job/settings exclusions. This module owns one interactive child and
its private transcript; it does not implement memory analysis or alter reports.
"""
from __future__ import annotations

import asyncio
import codecs
from collections import deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import uuid

from volatility_mcp.api import Config, check_components, private_dir


MAX_COMMAND = 8192
MAX_OUTPUT = 128000
MAX_ENTRIES = 200
MODES = {"generic": (), "windows": ("-w",), "linux": ("-l",), "mac": ("-m",)}
ACTIVE = {"starting", "running", "stopping"}
# Upstream's first parse includes argv[0], so Python's '-c' must not reach it.
# Disable implicit user startup scripts and IPython startup/configuration. The
# installed CLI still creates every layer, symbol table and forensic command.
BOOTSTRAP = """import sys, code, os
sys.argv[0] = 'volshell'
_workbench_token = os.environ.pop('WORKBENCH_VOLSHELL_TOKEN')
_workbench_raw_input = code.InteractiveConsole.raw_input
def _workbench_input(self, prompt=''):
    continued = prompt == getattr(sys, 'ps2', '... ')
    sys.stderr.write('\\x1eWBVS:' + _workbench_token + ':' + ('1' if continued else '0') + '\\x1f')
    sys.stderr.flush()
    return _workbench_raw_input(self, prompt)
code.InteractiveConsole.raw_input = _workbench_input
from volatility3.cli.volshell import VolShell, generic
generic.has_ipython = False
class WorkbenchVolshell(VolShell):
    def load_system_defaults(self, filename):
        return [], {}
WorkbenchVolshell().run()
"""
_ANSI = re.compile(r"\x1b\][^\x07]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]")


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _display(text):
    text = _ANSI.sub("", text).replace("\r\n", "\n").replace("\r", "\n")
    return "".join(c for c in text if c in "\n\t" or ord(c) >= 32 and not 127 <= ord(c) <= 159)


def _environment(token):
    # Do not expose Codex configuration, provider credentials, Python injection
    # variables, shell startup state or the caller's executable search path.
    allowed = ("HOME", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE", "SYSTEMROOT", "WINDIR")
    return {k: os.environ[k] for k in allowed if k in os.environ} | {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "PYTHONNOUSERSITE": "1", "TERM": "dumb",
        "WORKBENCH_VOLSHELL_TOKEN": token}


class VolshellManager:
    def __init__(self, spawn=None, signal_group=None, startup_timeout=60, stop_timeout=2):
        self._spawn = spawn or asyncio.create_subprocess_exec
        self._signal_group = signal_group if signal_group is not None else getattr(os, "killpg", None)
        self._startup_timeout = startup_timeout
        self._stop_timeout = stop_timeout
        self._lock = asyncio.Lock()
        self._session = None

    @property
    def busy(self):
        return bool(self._session and self._session["status"] in ACTIVE)

    def snapshot(self, case_id=None):
        session = self._session
        if session is None or case_id is not None and session["case_id"] != case_id:
            return {"session": None, "busy": self.busy}
        keys = ("id", "case_id", "image_id", "mode", "status", "ready", "continuation",
                "started_at", "finished_at", "error", "returncode", "earlier_entries")
        value = {k: session[k] for k in keys}
        value["entries"] = [dict(entry) for entry in session["entries"]]
        return {"session": value, "busy": self.busy}

    @staticmethod
    def _identity(value, label):
        if not isinstance(value, str) or not value or len(value) > 256 or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("Invalid " + label)

    def _bound(self, case_id, session_id):
        session = self._session
        if not session or session["id"] != session_id or session["case_id"] != case_id:
            raise ValueError("Volshell session does not belong to this case or is no longer current")
        return session

    def _record(self, session, kind, text):
        session["sequence"] += 1
        entry = {"id": str(session["sequence"]), "time": _now(), "kind": kind, "text": text}
        transcript = session["transcript"]
        if transcript and not transcript.closed:
            transcript.write(json.dumps(entry, ensure_ascii=True) + "\n")
            transcript.flush()
        shown = dict(entry, text=_display(text))
        # A single entry and the accumulated view are both bounded. The private
        # transcript retains original text; UI output never becomes markup.
        if len(shown["text"]) > MAX_OUTPUT:
            shown["text"] = shown["text"][-MAX_OUTPUT:]
            session["earlier_entries"] += 1
        session["entries"].append(shown)
        session["characters"] += len(shown["text"])
        while len(session["entries"]) > MAX_ENTRIES or session["characters"] > MAX_OUTPUT:
            old = session["entries"].popleft()
            session["characters"] -= len(old["text"])
            session["earlier_entries"] += 1

    def _output(self, session, text, final=False):
        """Remove trusted transport markers before retaining child output.

        Ordinary prompt-looking output never enables input. The nonce protects
        against accidental/evidence-origin marker text, not arbitrary Python
        intentionally inspecting this process (Volshell is not a sandbox).
        """
        pending = session["marker_tail"] + text
        prefix = session["marker_prefix"]
        shown = []
        while pending:
            index = pending.find(prefix)
            if index < 0:
                keep = next((n for n in range(min(len(prefix) - 1, len(pending)), 0, -1)
                             if pending.endswith(prefix[:n])), 0)
                shown.append(pending[:-keep] if keep else pending)
                pending = pending[-keep:] if keep else ""
                break
            shown.append(pending[:index])
            pending = pending[index:]
            if len(pending) < len(prefix) + 2:
                break
            flag = pending[len(prefix)]
            if flag not in "01" or pending[len(prefix) + 1] != "\x1f":
                shown.append(pending[0])
                pending = pending[1:]
                continue
            pending = pending[len(prefix) + 2:]
            session["prompts_pending"] = max(0, session["prompts_pending"] - 1)
            if session["prompts_pending"] == 0 and session["status"] in ("starting", "running"):
                session.update(status="running", ready=True, continuation=flag == "1")
                if session["watchdog"]:
                    session["watchdog"].cancel()
        # An incomplete transport marker at EOF is not application output.
        session["marker_tail"] = "" if final else pending
        retained = "".join(shown)
        if retained:
            self._record(session, "output", retained)

    async def start(self, case_id, image_id, image_path, mode, config: Config, directory):
        async with self._lock:
            if self._signal_group is None:
                raise ValueError("Interactive Volshell requires POSIX process-group support on this platform")
            if self.busy:
                raise ValueError("Close the existing Volshell session before starting another")
            self._identity(case_id, "case identity")
            self._identity(image_id, "image identity")
            if not isinstance(mode, str) or mode not in MODES:
                raise ValueError("Choose generic, windows, linux or mac Volshell mode")
            image = Path(image_path)
            if not image.is_absolute():
                raise ValueError("Volshell requires a resolved registered image")
            check_components(image)
            if not image.is_file():
                raise ValueError("The registered image is unavailable")
            case_dir = Path(directory)
            if not case_dir.is_absolute():
                raise ValueError("Volshell requires an absolute private case directory")
            check_components(case_dir)
            cache = Path(config.cache_path)
            if not cache.is_absolute():
                raise ValueError("Volshell requires an absolute symbol cache directory")
            check_components(cache)
            cache = private_dir(cache)
            ident = uuid.uuid4().hex
            token = uuid.uuid4().hex
            root = private_dir(case_dir / "volshell" / ident)
            output = private_dir(root / "output")
            fd = os.open(root / "transcript.jsonl", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND | os.O_NOFOLLOW, 0o600)
            session = {"id": ident, "case_id": case_id, "image_id": image_id, "mode": mode,
                       "status": "starting", "ready": False, "continuation": False,
                       "started_at": _now(), "finished_at": None, "error": "", "returncode": None,
                       "entries": deque(), "characters": 0, "earlier_entries": 0, "sequence": 0,
                       "transcript": os.fdopen(fd, "a", encoding="utf-8"), "process": None,
                       "reader": None, "monitor": None, "watchdog": None,
                       "marker_prefix": "\x1eWBVS:" + token + ":", "marker_tail": "",
                       "prompts_pending": 1, "closing": False}
            self._session = session
            argv = [str(config.vol_python), "-I", "-u", "-c", BOOTSTRAP, "-q", "--offline",
                    "--cache-path", str(cache), "-o", str(output), "-f", str(image), *MODES[mode]]
            if config.symbols is not None:
                argv += ["-s", str(config.symbols)]
            try:
                self._record(session, "session", "Starting " + mode + " Volshell for registered image " + image_id)
                spawning = asyncio.create_task(self._spawn(
                    *argv, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT, cwd=str(output), env=_environment(token),
                    start_new_session=True, limit=65536))
                cancelled = False
                try:
                    process = await asyncio.shield(spawning)
                except asyncio.CancelledError:
                    # Process creation can succeed while its caller is being
                    # cancelled. Obtain the handle and stop it before returning.
                    process = await spawning
                    cancelled = True
                session["process"] = process
                session["reader"] = asyncio.create_task(self._read(session))
                session["monitor"] = asyncio.create_task(self._monitor(session))
                session["watchdog"] = asyncio.create_task(self._startup_watchdog(session))
                if cancelled:
                    await self._stop(session)
                    raise asyncio.CancelledError()
            except BaseException as exc:
                if session["process"] is None:
                    session.update(status="failed", error=str(exc) or type(exc).__name__, finished_at=_now())
                    session["transcript"].close()
                raise
            return self.snapshot()

    async def _read(self, session):
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        try:
            while True:
                chunk = await session["process"].stdout.read(4096)
                text = decoder.decode(chunk, final=not chunk)
                self._output(session, text, final=not chunk)
                if not chunk:
                    session["ready"] = False
                    return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            session["error"] = "Volshell output could not be retained: " + str(exc)
            session["ready"] = False
            self._signal(session, signal.SIGTERM)
            await asyncio.sleep(self._stop_timeout)
            self._signal(session, signal.SIGKILL)

    async def _monitor(self, session):
        process = session["process"]
        try:
            # asyncio's Process.wait() can wait for pipe EOF even after the
            # interpreter exits. A descendant retaining stdout must not prevent
            # us from noticing that exit and cleaning up its process group.
            while process.returncode is None:
                await asyncio.sleep(0.05)
            code = process.returncode
            session["returncode"] = code
            # The interpreter may exit while commands it spawned still hold the
            # output pipe. Its isolated process group belongs to this session.
            self._signal(session, signal.SIGKILL, include_exited=True)
            # Drain buffered output, but a child inheriting the pipe cannot keep
            # this application waiting after the interpreter has exited.
            try:
                await asyncio.wait_for(asyncio.shield(session["reader"]), self._stop_timeout)
            except asyncio.TimeoutError:
                session["reader"].cancel()
                await asyncio.gather(session["reader"], return_exceptions=True)
            if session["error"]:
                session["status"] = "failed"
            elif session["closing"]:
                session["status"] = "closed"
            elif code == 0:
                session["status"] = "exited"
            else:
                session.update(status="failed", error="Volshell exited with status " + str(code))
            try:
                self._record(session, "session", session["error"] or "Volshell " + session["status"])
            except OSError as exc:
                session.update(status="failed", error="Volshell transcript could not be saved: " + str(exc))
        finally:
            session.update(ready=False, continuation=False, finished_at=_now())
            if session["watchdog"]:
                session["watchdog"].cancel()
            session["transcript"].close()

    async def _startup_watchdog(self, session):
        await asyncio.sleep(self._startup_timeout)
        async with self._lock:
            if self._session is session and session["status"] == "starting":
                session["error"] = "Volshell did not reach an interactive prompt before the startup timeout"
                await self._stop(session)

    def _signal(self, session, signum, include_exited=False):
        process = session["process"]
        if process and (process.returncode is None or include_exited):
            try:
                self._signal_group(process.pid, signum)
            except ProcessLookupError:
                pass

    async def send(self, case_id, session_id, text):
        if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_COMMAND:
            raise ValueError("Volshell commands must be text of at most 8192 UTF-8 bytes")
        if any(ord(c) < 32 and c not in "\n\t" or 127 <= ord(c) <= 159 for c in text):
            raise ValueError("Volshell commands cannot contain terminal control characters")
        async with self._lock:
            session = self._bound(case_id, session_id)
            if session["status"] != "running" or not session["ready"]:
                raise ValueError("Wait for the Volshell prompt before sending another command")
            if not text.strip() and not session["continuation"]:
                raise ValueError("Enter a Volshell command; a blank line only ends a continued block")
            process = session["process"]
            if process.returncode is not None:
                raise ValueError("Volshell has already exited")
            self._record(session, "input", text)
            wire = text.rstrip("\n") + ("\n\n" if "\n" in text.rstrip("\n") else "\n")
            session.update(ready=False, continuation=False, prompts_pending=wire.count("\n"))
            try:
                process.stdin.write(wire.encode("utf-8"))
                await process.stdin.drain()
            except (BrokenPipeError, ConnectionResetError) as exc:
                session["error"] = "Volshell input disconnected"
                await self._stop(session)
                raise ValueError(session["error"]) from exc
            return self.snapshot()

    async def interrupt(self, case_id, session_id):
        async with self._lock:
            session = self._bound(case_id, session_id)
            if session["status"] not in ("starting", "running"):
                raise ValueError("Volshell is no longer running")
            self._record(session, "control", "Interrupt requested")
            session.update(ready=False, continuation=False, prompts_pending=1)
            self._signal(session, signal.SIGINT)
            return self.snapshot()

    async def _stop(self, session):
        if session["status"] not in ACTIVE:
            return
        session.update(status="stopping", ready=False, continuation=False, closing=True)
        watchdog = session["watchdog"]
        if watchdog and watchdog is not asyncio.current_task():
            watchdog.cancel()
        process = session["process"]
        if not process:
            session.update(status="closed", finished_at=_now())
            session["transcript"].close()
            return
        process.stdin.close()
        self._signal(session, signal.SIGTERM)
        try:
            await asyncio.wait_for(asyncio.shield(session["monitor"]), self._stop_timeout)
        except asyncio.TimeoutError:
            self._signal(session, signal.SIGKILL)
            try:
                await asyncio.wait_for(asyncio.shield(session["monitor"]), self._stop_timeout)
            except asyncio.TimeoutError:
                session["error"] = "Volshell has not confirmed exit after termination"
                # Keep status stopping/busy until the monitor confirms exit.

    async def close(self, case_id, session_id):
        async with self._lock:
            await self._stop(self._bound(case_id, session_id))
            return self.snapshot()

    async def shutdown(self):
        async with self._lock:
            if self._session:
                await self._stop(self._session)
