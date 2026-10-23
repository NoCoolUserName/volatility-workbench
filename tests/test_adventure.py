"""Synthetic Adventure process tests; no forensic case or game assets are opened."""
import asyncio
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

from volatility_workbench.adventure import AdventureManager
from volatility_workbench.http import Handler


FAKE_GAME = '''#!/usr/bin/env python3
import os, signal, sys
save = os.environ.get("VOLATILITY_ADVENTURE_SAVE") or sys.argv[3]
print("WELCOME TO A SYNTHETIC CAVE", flush=True)
print("RESTORED" if os.path.exists(save) else "NEW", flush=True)
def stop(*_):
    with open(save, "w") as output: output.write("saved")
    sys.exit(0)
signal.signal(signal.SIGTERM, stop)
for line in sys.stdin:
    if line.strip() == "suspend": stop()
    print("CAVE: " + line.strip(), flush=True)
'''


class AdventureTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        assets = root / "assets"
        assets.mkdir()
        game = assets / "advent-430"
        game.write_text(FAKE_GAME)
        game.chmod(0o700)
        classic = assets / "adventure-350"
        classic.write_text(FAKE_GAME)
        classic.chmod(0o700)
        (assets / "manifest.json").write_text(json.dumps({"editions": {
            "1995": {"executable": "advent-430", "sha256": hashlib.sha256(game.read_bytes()).hexdigest()},
            "1977": {"executable": "adventure-350", "sha256": hashlib.sha256(classic.read_bytes()).hexdigest()}}}))
        self.game = game
        self.manager = AdventureManager(root / "state", assets)
        self.addAsyncCleanup(self.manager.shutdown)

    async def until(self, text):
        for _ in range(100):
            if text in self.manager.snapshot()["output"]:
                return
            await asyncio.sleep(.02)
        self.fail("Missing synthetic game output: " + text)

    async def test_launch_input_save_restore_and_new_game(self):
        first = await self.manager.start("1995")
        self.assertEqual(first["edition"], "1995")
        await self.until("NEW")
        await self.manager.input(first["session_id"], "north")
        await self.until("CAVE: north")
        await self.manager.close(first["session_id"])
        self.assertTrue(self.manager.snapshot()["saved"])
        second = await self.manager.start("1995")
        await self.until("RESTORED")
        await self.manager.close(second["session_id"])
        third = await self.manager.start("1995", new=True)
        await self.until("NEW")
        await self.manager.close(third["session_id"])

    async def test_classic_save_restore_and_independent_saves(self):
        first = await self.manager.start("1977")
        self.assertEqual(first["edition"], "1977")
        await self.until("NEW")
        await self.manager.input(first["session_id"], "west")
        await self.until("CAVE: west")
        await self.manager.close(first["session_id"])
        self.assertTrue(self.manager.snapshot()["saves"]["1977"])
        self.assertFalse(self.manager.snapshot()["saves"]["1995"])
        second = await self.manager.start("1977")
        await self.until("RESTORED")
        await self.manager.close(second["session_id"])
        third = await self.manager.start("1977", new=True)
        await self.until("NEW")
        await self.manager.close(third["session_id"])

    async def test_reject_unknown_edition_and_bad_commands_without_affecting_game(self):
        with self.assertRaisesRegex(ValueError, "Unknown"):
            await self.manager.start("other")
        session = await self.manager.start("1995")
        with self.assertRaises(ValueError):
            await self.manager.input(session["session_id"], "x" * 257)
        with self.assertRaises(ValueError):
            await self.manager.input(session["session_id"], "north\nquit")
        with self.assertRaises(ValueError):
            await self.manager.input("other-session", "north")
        self.assertEqual(self.manager.snapshot()["status"], "running")

    async def test_tampered_executable_and_symlink_save_dir(self):
        self.game.write_text(FAKE_GAME + "# tampered\n")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            await self.manager.start("1995")
        self.game.write_text(FAKE_GAME)
        target = Path(self.temp.name) / "elsewhere"
        target.mkdir()
        self.manager.state_root.symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            await self.manager.start("1995")

    async def test_http_dispatch_is_separate_from_case_state(self):
        fake = SimpleNamespace(server=SimpleNamespace(app=object(), adventure=self.manager))
        session = await Handler.dispatch(fake, "/api/adventure/start", {"edition": "1995"})
        await Handler.dispatch(fake, "/api/adventure/input", {"session_id": session["session_id"], "command": "look"})
        await self.until("CAVE: look")
        view = await Handler.get_data(fake, "/api/adventure/status", {})
        self.assertEqual(view["session_id"], session["session_id"])
        await Handler.dispatch(fake, "/api/adventure/close", {"session_id": session["session_id"]})


if __name__ == "__main__":
    unittest.main()
