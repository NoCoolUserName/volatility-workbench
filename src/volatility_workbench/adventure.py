"""Isolated, bounded terminal session for bundled Colossal Cave Adventure."""
from __future__ import annotations

import asyncio
import codecs
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import stat
import termios

MAX_COMMAND = 256
MAX_OUTPUT = 64 * 1024
MAX_TOTAL_OUTPUT = 1024 * 1024
MAX_SESSION_SECONDS = 6 * 60 * 60
EDITIONS = {"1977": "advent-350.save", "1995": "advent-430.save"}


class AdventureManager:
    """Owns one game process. It has no reference to Workbench or case state."""

    def __init__(self, state_root: Path, assets: Path | None = None):
        self.state_root = Path(state_root)
        self.assets = Path(assets) if assets is not None else Path(
            os.environ.get("VOLATILITY_WORKBENCH_RESOURCES", "/nonexistent")
        ) / "adventure"
        self.process = None
        self.session_id = None
        self.edition = None
        self.status = "idle"
        self.output = ""
        self.total_output = 0
        self.error = None
        self.master = None
        self.waiter = None
        self.timer = None
        self.lock = asyncio.Lock()
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")

    def _executable(self, edition):
        manifest_path = self.assets / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        entry = manifest["editions"][edition]
        executable = self.assets / entry["executable"]
        if executable.parent != self.assets or executable.is_symlink():
            raise ValueError("Invalid Adventure executable path")
        mode = executable.stat().st_mode
        if not stat.S_ISREG(mode) or not mode & stat.S_IXUSR:
            raise ValueError("Adventure executable is missing or not executable")
        if hashlib.sha256(executable.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("Adventure executable hash mismatch")
        return executable

    def _save_dir(self):
        if self.state_root.is_symlink():
            raise ValueError("Adventure save directory cannot be a symlink")
        self.state_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.state_root.is_symlink():
            raise ValueError("Adventure save directory cannot be a symlink")
        os.chmod(self.state_root, 0o700)
        return self.state_root

    def snapshot(self):
        return {
            "session_id": self.session_id,
            "edition": self.edition if self.session_id else None,
            "status": self.status,
            "output": self.output,
            "truncated": self.total_output > len(self.output),
            "error": self.error,
            "saved": bool(self.edition and (self.state_root / EDITIONS[self.edition]).is_file()),
            "saves": {edition: (self.state_root / name).is_file() for edition, name in EDITIONS.items()},
        }

    def _readable(self):
        if self.master is None:
            return
        try:
            chunk = os.read(self.master, 8192)
        except BlockingIOError:
            return
        except OSError:
            chunk = b""
        if not chunk:
            asyncio.get_running_loop().remove_reader(self.master)
            return
        # Never pass terminal escape/control sequences to the page.
        text = self.decoder.decode(chunk)
        text = re.sub(r"\x1b\][^\x07]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]", "", text)
        text = "".join(c for c in text if c in "\n\t" or ord(c) >= 32)
        self.total_output += len(text)
        self.output = (self.output + text)[-MAX_OUTPUT:]
        if self.total_output > MAX_TOTAL_OUTPUT and self.process and self.process.returncode is None:
            self.error = "Adventure produced too much output and was stopped."
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    async def _wait(self, process):
        try:
            code = await process.wait()
            if process is self.process:
                self._readable()
                self.status = "closed" if self.status == "stopping" else "exited"
                if code and not self.error and self.status != "closed":
                    self.error = f"Adventure exited with status {code}."
        finally:
            if self.master is not None and process is self.process:
                asyncio.get_running_loop().remove_reader(self.master)
                os.close(self.master)
                self.master = None
            if self.timer and process is self.process:
                self.timer.cancel()
                self.timer = None

    async def start(self, edition: str, *, new: bool = False):
        if edition not in EDITIONS:
            raise ValueError("Unknown Adventure edition")
        async with self.lock:
            if self.process and self.process.returncode is None:
                raise ValueError("Close the current Adventure session first")
            executable = self._executable(edition)
            directory = self._save_dir()
            save = directory / EDITIONS[edition]
            if save.is_symlink():
                raise ValueError("Adventure save cannot be a symlink")
            if new:
                save.unlink(missing_ok=True)
            resume = directory / "advent-350.resume"
            if edition == "1977" and resume.is_symlink():
                raise ValueError("Adventure resume file cannot be a symlink")
            if edition == "1977":
                resume.unlink(missing_ok=True)
                if save.is_file():
                    shutil.copy2(save, resume)
            master, slave = os.openpty()
            try:
                attrs = termios.tcgetattr(slave)
                attrs[3] &= ~termios.ECHO
                termios.tcsetattr(slave, termios.TCSANOW, attrs)
                os.set_blocking(master, False)
                env = {"HOME": str(directory), "TMPDIR": str(directory),
                       "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "TERM": "dumb"}
                args = ["-o", "-a", str(save), "-"] if edition == "1995" else ([str(resume)] if resume.is_file() else [])
                if edition == "1977":
                    env["VOLATILITY_ADVENTURE_SAVE"] = str(save)
                process = await asyncio.create_subprocess_exec(
                    str(executable), *args,
                    stdin=slave, stdout=slave, stderr=slave, cwd=directory,
                    env=env, start_new_session=True, close_fds=True,
                )
            except BaseException:
                os.close(master)
                raise
            finally:
                os.close(slave)
            self.process = process
            self.master = master
            self.session_id = secrets.token_hex(16)
            self.edition = edition
            self.status = "running"
            self.error = None
            self.output = ""
            self.total_output = 0
            self.decoder = codecs.getincrementaldecoder("utf-8")("replace")
            loop = asyncio.get_running_loop()
            loop.add_reader(master, self._readable)
            self.waiter = asyncio.create_task(self._wait(process))
            self.timer = loop.call_later(MAX_SESSION_SECONDS, self._expire, process)
            return self.snapshot()

    def _expire(self, process):
        if process is self.process and process.returncode is None:
            self.error = "Adventure session reached its time limit."
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

    async def input(self, session_id: str, command: str):
        if not isinstance(command, str) or not 0 < len(command) <= MAX_COMMAND:
            raise ValueError("Adventure command must be 1–256 characters")
        if any(ord(c) < 32 or ord(c) == 127 for c in command):
            raise ValueError("Adventure command contains a control character")
        async with self.lock:
            if session_id != self.session_id or self.status != "running" or self.master is None:
                raise ValueError("Adventure session is not running")
            data = (command + "\n").encode("utf-8")
            if len(data) > 1024:
                raise ValueError("Adventure command is too long")
            written = os.write(self.master, data)
            if written != len(data):
                raise OSError("Adventure input was incomplete")
            return self.snapshot()

    async def close(self, session_id: str | None = None):
        async with self.lock:
            if session_id is not None and session_id != self.session_id:
                raise ValueError("Adventure session has changed")
            process = self.process
            if not process or process.returncode is not None:
                return self.snapshot()
            self.status = "stopping"
            if self.edition == "1977" and self.master is not None:
                try:
                    os.write(self.master, b"suspend\nyes\n")
                    await asyncio.wait_for(asyncio.shield(self.waiter), 2)
                    return self.snapshot()
                except (OSError, asyncio.TimeoutError):
                    pass
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(asyncio.shield(self.waiter), 3)
            except asyncio.TimeoutError:
                if process.returncode is None:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                await self.waiter
            return self.snapshot()

    async def shutdown(self):
        await self.close()
