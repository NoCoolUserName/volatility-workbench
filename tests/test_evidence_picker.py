"""Finder cancellation is a no-op; actual failures and path guards remain visible."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from volatility_workbench.app import Workbench
import support


class PickerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        fixture = support.BackendFixture(); fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        config = fixture.root / 'config.json'
        config.write_text(json.dumps(fixture.config.to_dict()))
        self.app = Workbench(config, fixture.root / 'ui')

    async def pick(self, stdout=b'', stderr=b'', returncode=0):
        proc = SimpleNamespace(returncode=returncode,
            communicate=AsyncMock(return_value=(stdout, stderr)), kill=Mock(), wait=AsyncMock())
        with patch('volatility_workbench.app.platform.system', return_value='Darwin'), \
             patch('volatility_workbench.app.asyncio.create_subprocess_exec', return_value=proc) as spawn:
            result = await self.app.native_pick()
        self.script = spawn.call_args.args[2]
        return result

    async def test_cancel_is_explicit_and_changes_nothing(self):
        before = self.app.state_path.read_bytes()
        with patch.object(self.app, 'selected_image', side_effect=AssertionError('cancel must not inspect images')):
            result = await self.pick(stdout=b'\n')  # osascript prints a newline for return \"\"
        self.assertEqual(result, {'paths': [], 'cancelled': True})
        self.assertIn('on error number -128\nreturn ""', self.script)
        self.assertEqual(self.app.state_path.read_bytes(), before)
        self.assertFalse((self.fixture.root / 'analysis-count.jsonl').exists())

    async def test_real_failure_is_actionable_without_raw_osascript_trace(self):
        with self.assertRaisesRegex(ValueError, 'Enter image paths directly') as caught:
            await self.pick(stderr=b'14:131 execution error: SYNTHETIC FAILURE (-999)', returncode=1)
        self.assertNotIn('14:131', str(caught.exception))
        self.assertNotIn('(-999)', str(caught.exception))

    async def test_selected_external_image_uses_current_add_evidence_validator(self):
        image = self.fixture.root / 'Other folder' / 'capture.mem'
        image.parent.mkdir(); image.write_text('SYNTHETIC IMAGE')
        result = await self.pick(stdout=(str(image)+'\n').encode())
        self.assertEqual(result, {'paths': [str(image)], 'cancelled': False})
        self.assertEqual(self.app.state['cases'], [])  # picker never submits a case or job
        linked = image.parent / 'linked.mem'; linked.symlink_to(image)
        with self.assertRaises(ValueError):
            await self.pick(stdout=(str(linked)+'\n').encode())
        self.assertFalse((self.fixture.root / 'analysis-count.jsonl').exists())


if __name__ == '__main__': unittest.main()
