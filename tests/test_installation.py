import unittest
from unittest.mock import patch
from types import SimpleNamespace
from importlib.resources import files
from volatility_workbench.compatibility import require_core
from volatility_mcp import api

class InstallationTests(unittest.TestCase):
    def test_assets_and_installed_contract(self):
        root=files('volatility_workbench')
        for name in ('static/app.js','static/style.css','static/index.html','templates/report.md'):
            self.assertTrue(root.joinpath(name).read_bytes())
        self.assertIn('Executive summary',api.report_spec())
        self.assertIs(require_core(), api)

    def test_incompatible_core_is_actionable(self):
        with patch('volatility_workbench.compatibility.importlib.import_module',return_value=SimpleNamespace(API_VERSION=2)):
            with self.assertRaisesRegex(RuntimeError,'Restore its tested core pin'):require_core()
        with patch('volatility_workbench.compatibility.importlib.import_module',side_effect=ImportError):
            with self.assertRaisesRegex(RuntimeError,'editable mode'):require_core()
