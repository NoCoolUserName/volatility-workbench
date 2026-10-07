import contextlib
import io
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from volatility_workbench.http import open_browser


class BrowserTests(unittest.TestCase):
    def test_macos_uses_default_browser_without_applescript(self):
        with patch('volatility_workbench.http.sys.platform', 'darwin'), \
             patch('volatility_workbench.http.subprocess.run', return_value=SimpleNamespace(returncode=0)) as run, \
             patch('volatility_workbench.http.webbrowser.open') as browser:
            self.assertTrue(open_browser('http://127.0.0.1:1234/#synthetic'))
            self.assertEqual(run.call_args.args[0], ['/usr/bin/open', 'http://127.0.0.1:1234/#synthetic'])
            browser.assert_not_called()

    def test_failures_are_reported_without_leaking_capability(self):
        for failure in (None, OSError('unavailable'), subprocess.TimeoutExpired('open', 15)):
            with self.subTest(failure=failure), patch('volatility_workbench.http.sys.platform', 'darwin'), \
                 patch('volatility_workbench.http.subprocess.run', return_value=SimpleNamespace(returncode=1), side_effect=failure), \
                 contextlib.redirect_stderr(io.StringIO()) as error:
                self.assertFalse(open_browser('http://127.0.0.1:1234/#private-capability'))
                self.assertIn('Workbench remains available', error.getvalue())
                self.assertNotIn('private-capability', error.getvalue())

    def test_other_platforms_keep_standard_browser_support(self):
        with patch('volatility_workbench.http.sys.platform', 'linux'), \
             patch('volatility_workbench.http.webbrowser.open', return_value=True) as browser:
            self.assertTrue(open_browser('http://127.0.0.1:1234/'))
            browser.assert_called_once()
