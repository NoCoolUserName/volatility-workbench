"""Explicit multi-folder selections, saved-location metadata, and case isolation."""
import asyncio
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from mcp import Client
from mcp.client.stdio import StdioServerParameters
from volatility_mcp.api import decode_result
from volatility_workbench.app import Workbench
from volatility_workbench.settings import SettingsManager
import support


class EvidenceLocationsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fixture = support.BackendFixture(); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.config = self.root / 'config.json'
        self.config.write_text(json.dumps(self.fixture.config.to_dict()))
        self.app = Workbench(self.config, self.root / 'ui')
        self.external = self.root / 'Other drive' / 'capture.mem'
        self.external.parent.mkdir()
        self.external.write_text('SYNTHETIC EXTERNAL IMAGE')
        self.other = self.external.parent / 'not-selected.mem'
        self.other.write_text('SYNTHETIC UNREGISTERED IMAGE')
        self.manager = SettingsManager(self.app, self.config, self.root / 'preferences')

    async def test_selected_folders_appear_deduplicated_without_hashing_or_analysis(self):
        original = self.config.read_bytes()
        with patch('subprocess.Popen', side_effect=AssertionError('no analysis or model')), \
             patch('volatility_mcp.backend.file_fingerprint', side_effect=AssertionError('no hashing')):
            first = self.app.add([str(self.external)])[0]
            self.app.add([str(self.external)])
            self.app.add([str(self.fixture.image)])
            locations = self.manager.snapshot()['evidence_locations']
        self.assertEqual(self.config.read_bytes(), original)
        self.assertTrue(locations[0]['default'])
        external = next(x for x in locations if x['path'] == str(self.external.parent))
        self.assertEqual(external, {'path': str(self.external.parent), 'default': False, 'image_count': 1, 'case_count': 2})
        backend = self.app.case_backend(first)
        self.assertEqual(backend.resolve_input(str(self.external)), self.external)
        with self.assertRaises(ValueError): backend.resolve_input(str(self.other))
        self.assertEqual(self.external.read_text(), 'SYNTHETIC EXTERNAL IMAGE')
        self.assertFalse((self.root / 'analysis-count.jsonl').exists())

    async def test_related_images_share_only_explicit_files_and_reopen_keeps_locations(self):
        case = self.app.add([str(self.fixture.image), str(self.external)], related=True)[0]
        scoped = json.loads((self.app.directory(case) / 'mcp.json').read_text())
        self.assertEqual(scoped['config']['evidence_root'], str(self.root))
        backend = self.app.case_backend(case)
        for image in (self.fixture.image, self.external):
            self.assertEqual(backend.resolve_input(str(image)), image)
        with self.assertRaises(ValueError): backend.resolve_input(str(self.other))
        expected = self.app.evidence_locations()
        with patch('subprocess.Popen', side_effect=AssertionError('no restart analysis')), \
             patch('volatility_mcp.backend.file_fingerprint', side_effect=AssertionError('no hash')):
            reopened = Workbench(self.config, self.app.root)
            self.assertEqual(reopened.evidence_locations(), expected)
            self.assertEqual(reopened.case_backend(reopened.case(case['id'])).resolve_input(str(self.external)), self.external)
        self.assertFalse((self.root / 'analysis-count.jsonl').exists())

    async def test_unavailable_registered_folder_remains_visible_without_reading_evidence(self):
        self.app.add([str(self.external)])
        self.external.unlink()
        self.other.unlink()
        self.external.parent.rmdir()
        locations = self.manager.snapshot()['evidence_locations']
        self.assertTrue(any(x['path'] == str(self.external.parent) for x in locations))

    async def test_invalid_selection_does_not_add_locations_or_cases(self):
        link = self.root / 'linked-drive'; link.symlink_to(self.external.parent)
        bad_file = self.external.parent / 'not-a-dump.txt'; bad_file.touch()
        derived = self.app.root / 'derived.mem'; derived.touch()
        output = self.fixture.config.output_root / 'derived.mem'; output.touch()
        traversal = str(self.external.parent / '..' / self.external.parent.name / self.external.name)
        for value in (str(link / self.external.name), str(bad_file), str(derived), str(output), traversal, '../escape.raw', str(self.external.parent / 'missing.mem')):
            with self.subTest(value=value):
                with self.assertRaises(ValueError): self.app.add([value])
                self.assertEqual(self.app.state['cases'], [])
                self.assertEqual(len(self.app.evidence_locations()), 1)

        nested = Workbench(self.config, self.fixture.evidence / 'ui-state')
        (nested.root / 'derived.raw').touch()
        for value in ('ui-state/derived.raw', str(nested.root / 'derived.raw')):
            with self.assertRaises(ValueError): nested.add([value])

    async def test_real_scoped_mcp_lists_external_images_and_rejects_sibling(self):
        case = self.app.add([str(self.external)])[0]
        transport = StdioServerParameters(command=sys.executable,
            args=['-m', 'volatility_mcp.scoped', str(self.app.directory(case) / 'mcp.json')])
        async with Client(transport) as client:
            names = {t.name for t in (await client.list_tools()).tools}
            self.assertIn('get_coverage', names)
            images = decode_result(await client.call_tool('list_memory_images', {}))
            self.assertEqual(images['count'], 1)
            self.assertEqual(images['images'][0]['path'], str(self.external))
            denied = await client.call_tool('get_coverage', {'image': str(self.other)})
            self.assertTrue(denied.is_error)
            self.assertIn('not registered', denied.content[0].text)
        job = {'progress': ''}
        fingerprint = await self.app.fingerprint(case, case['images'][0], job)
        self.assertEqual(fingerprint['size_bytes'], self.external.stat().st_size)
        self.assertFalse((self.root / 'analysis-count.jsonl').exists())


if __name__ == '__main__': unittest.main()
