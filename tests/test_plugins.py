"""Real authenticated catalog HTTP without a case, model call, or memory analysis."""
import asyncio
import json
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

import support
from volatility_workbench.app import Workbench
from volatility_workbench.http import Server


class PluginCatalogTests(unittest.IsolatedAsyncioTestCase):
    async def test_catalog_is_global_read_only_and_refreshable(self):
        fixture = support.BackendFixture(); fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        config = fixture.root / 'config.json'
        config.write_text(json.dumps(fixture.config.to_dict()))
        app = Workbench(config, fixture.root / 'ui')
        await app.start()
        original_state = app.state_path.read_bytes()
        server = Server(app, 0, asyncio.get_running_loop())
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()

        def get(path, authenticated=True):
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            headers = {'Cookie': 'volatility_ui=' + server.token} if authenticated else {}
            with opener.open(urllib.request.Request(server.origin + path, headers=headers)) as response:
                return json.load(response)

        try:
            with patch.object(app, 'connect', side_effect=AssertionError('model forbidden')), \
                 patch.object(app.backend, 'run_plugin', side_effect=AssertionError('analysis forbidden')), \
                 patch('volatility_mcp.backend.file_fingerprint', side_effect=AssertionError('image hashing forbidden')):
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    await asyncio.to_thread(get, '/api/plugins', False)
                self.assertEqual(denied.exception.code, 403)
                first = await asyncio.to_thread(get, '/api/plugins')
                self.assertGreater(first['total'], 0)
                app.backend._catalog['plugins']['synthetic.New'] = {'description': 'cached fixture', 'options': []}
                cached = await asyncio.to_thread(get, '/api/plugins')
                self.assertEqual(cached['total'], first['total'] + 1)
                fresh = await asyncio.to_thread(get, '/api/plugins?refresh=1')
                self.assertEqual(fresh['total'], first['total'])
                self.assertFalse((fixture.root / 'analysis-count.jsonl').exists())
                self.assertEqual(app.state_path.read_bytes(), original_state)
                self.assertIsNone(app.agent)
        finally:
            await app.close()
            await asyncio.to_thread(server.shutdown)
            server.server_close()
