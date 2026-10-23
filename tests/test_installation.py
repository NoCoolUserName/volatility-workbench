import hashlib
import json
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from importlib.resources import files
from volatility_workbench.compatibility import require_core
from volatility_mcp import api

class InstallationTests(unittest.TestCase):
    def test_assets_and_installed_contract(self):
        root=files('volatility_workbench')
        for name in ('static/app.js','static/style.css','static/themes.js','static/themes.css','static/theme-halloween.svg','static/halloween-night.png',
                     'static/bezel-fallout3-robco-2.png','static/bezel-fallout3-vault112-2.png','static/bezel-new-vegas-2.png',
                     'static/index.html','static/icon.png','templates/report.md'):
            self.assertTrue(root.joinpath(name).read_bytes())
        scenes=[p for p in root.joinpath('static').iterdir() if p.name.startswith('theme-') and p.name.endswith('.svg')]
        self.assertEqual(len(scenes),30)
        self.assertTrue(all(p.read_bytes() for p in scenes))
        self.assertIn('Executive summary',api.report_spec())
        self.assertIs(require_core(), api)

    def test_reference_terminal_art_matches_bundled_manifest(self):
        root = files('volatility_workbench')
        manifest = json.loads(root.joinpath('resources/reference-terminal-assets.json').read_text())
        prompts = json.loads(root.joinpath('resources/reference-terminal-prompts.json').read_text())
        self.assertEqual(manifest['schema'], 'workbench-reference-terminal-assets/1')
        self.assertEqual(prompts['schema'], 'workbench-reference-terminal-prompts/1')
        self.assertEqual({entry['asset'] for entry in manifest['assets']}, {
            'bezel-fallout3-robco-2.png', 'bezel-fallout3-vault112-2.png', 'bezel-new-vegas-2.png'})
        self.assertEqual(len(manifest['assets']), 3)
        self.assertEqual(len(prompts['prompts']), 3)
        for entry in manifest['assets']:
            with self.subTest(asset=entry['asset']):
                image = root.joinpath('static', entry['asset']).read_bytes()
                self.assertEqual(len(image), entry['bytes'])
                self.assertEqual(hashlib.sha256(image).hexdigest(), entry['sha256'])
                self.assertEqual(image[:8], b'\x89PNG\r\n\x1a\n')
                self.assertEqual([int.from_bytes(image[16:20], 'big'), int.from_bytes(image[20:24], 'big')], entry['dimensions'])
                self.assertEqual(image[25], 6, 'Reference bezels retain RGBA transparency')

    def test_incompatible_core_is_actionable(self):
        with patch('volatility_workbench.compatibility.importlib.import_module',return_value=SimpleNamespace(API_VERSION=2)):
            with self.assertRaisesRegex(RuntimeError,'Restore its tested core pin'):require_core()
        with patch('volatility_workbench.compatibility.importlib.import_module',side_effect=ImportError):
            with self.assertRaisesRegex(RuntimeError,'editable mode'):require_core()
