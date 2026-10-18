"""Real MCP/loopback transport with synthetic observations, no model or analyzer."""
import json
import asyncio
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import threading
import unittest
import urllib.error
import urllib.request
from types import SimpleNamespace
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from volatility_workbench import guarded_scoped
from volatility_workbench.http import Server as WorkbenchServer


class BridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_mcp_cancellation_revokes_exact_request_and_rejects_replay(self):
        entered, cancelled = asyncio.Event(), asyncio.Event()
        calls = []
        async def inspect(case_id, arguments):
            calls.append((case_id, arguments))
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        app = SimpleNamespace(run_agent_volshell=inspect)
        server = WorkbenchServer(app, 0, asyncio.get_running_loop())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        async def cleanup():
            await asyncio.to_thread(server.shutdown)
            server.server_close()
        self.addAsyncCleanup(cleanup)
        token = hmac.new(app.volshell_bridge_secret, b'case-a', hashlib.sha256).hexdigest()
        class Capture:
            def tool(self):
                def register(fn): self.function = fn; return fn
                return register
        capture = Capture()
        guarded_scoped.install_volshell_bridge(capture, json.dumps({
            'url':server.origin+'/api/internal/volshell','case_id':'case-a','token':token}))
        task = asyncio.create_task(capture.function('E001', 'hh'))
        await asyncio.wait_for(entered.wait(), 3)
        request_id = next(iter(server.bridge_requests))[1]
        task.cancel()
        with self.assertRaises(asyncio.CancelledError): await task
        await asyncio.wait_for(cancelled.wait(), 3)
        self.assertEqual(len(calls), 1)
        def post(ident, cancel=False):
            request = urllib.request.Request(server.origin+'/api/internal/volshell'+('/cancel' if cancel else ''),
                data=json.dumps({'case_id':'case-a','request_id':ident,'arguments':{'helper':'hh'}}).encode(),
                headers={'Content-Type':'application/json','Origin':server.origin,'Authorization':'Bearer '+token})
            try:
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=3) as response:
                    return response.status
            except urllib.error.HTTPError as error:
                with error:
                    return error.code
        self.assertEqual(await asyncio.to_thread(post, request_id), 400)
        # A cancellation that wins the network race prevents the first request.
        ident = 'b' * 32
        self.assertEqual(await asyncio.to_thread(post, ident, True), 200)
        self.assertEqual(await asyncio.to_thread(post, ident), 400)
        self.assertEqual(len(calls), 1)

    async def test_bridge_does_not_follow_redirects_with_capability(self):
        calls = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                calls.append(self.path)
                self.send_response(302)
                self.send_header('Location', '/redirected')
                self.send_header('Content-Length', '0')
                self.end_headers()
            def do_GET(self):
                calls.append(self.path)
                self.send_response(200)
                self.end_headers()
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        class Capture:
            def tool(self):
                def register(fn): self.function = fn; return fn
                return register
        capture = Capture()
        guarded_scoped.install_volshell_bridge(capture, json.dumps({
            'url':f'http://127.0.0.1:{server.server_port}/api/internal/volshell',
            'case_id':'case-a','token':'a'*64}))
        with self.assertRaisesRegex(ValueError, 'HTTP 302'):
            await capture.function('E001', 'hh')
        self.assertEqual(calls, ['/api/internal/volshell'])

    async def test_registered_tool_returns_observation_for_next_plugin(self):
        calls = []
        token = 'a' * 64
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                calls.append((self.path, self.headers.get('Authorization'), self.headers.get('Origin'), body))
                data = json.dumps({'kind':'exploratory', 'output':'PID 120 synthetic.exe',
                                   'validated_core_evidence':False}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        origin = 'http://127.0.0.1:' + str(server.server_port)
        config = {'url':origin+'/api/internal/volshell', 'case_id':'case-a', 'token':token}
        transport = StdioServerParameters(command=sys.executable,
            args=[str(Path(__file__).parent/'fixtures/volshell_bridge_server.py')],
            env={'PYTHONPATH':str(Path(guarded_scoped.__file__).parents[1]),
                 'WORKBENCH_VOLSHELL_BRIDGE':json.dumps(config)})
        async with Client(transport) as client:
            catalog = await client.list_tools()
            self.assertEqual({t.name for t in catalog.tools}, {'case_volshell', 'run_plugin'})
            result = await client.call_tool('case_volshell', {'image_id':'E001', 'helper':'ps',
                'mode':'windows', 'arguments':{'limit':20}, 'reason':'Identify a PID for follow-up'})
            self.assertFalse(result.is_error)
            observation = json.loads(result.content[0].text)
            self.assertFalse(observation['validated_core_evidence'])
            # A simulated agent derives the next exact parameter from returned
            # output, proving the tool result is available to its investigation.
            pid = observation['output'].split()[1]
            follow = await client.call_tool('run_plugin', {'image':'fixture.raw',
                'plugin':'windows.pslist.PsList', 'arguments':['--pid',pid]})
            self.assertEqual(json.loads(follow.content[0].text)['arguments'], ['--pid','120'])
        self.assertEqual(len(calls), 1)
        path, auth, actual_origin, body = calls[0]
        self.assertEqual(path, '/api/internal/volshell')
        self.assertEqual(auth, 'Bearer '+token)
        self.assertEqual(actual_origin, origin)
        self.assertEqual(body['case_id'], 'case-a')
        self.assertEqual(body['arguments']['arguments'], {'limit':20})

    def test_bridge_cannot_be_redirected_or_enabled_without_capability(self):
        class Server:
            def tool(self):
                raise AssertionError('Invalid configuration must not register a tool')
        guarded_scoped.install_volshell_bridge(Server(), None)
        for url in ('https://example.com/api/internal/volshell',
                    'http://127.0.0.1:1234/wrong',
                    'http://127.0.0.1:1234/api/internal/volshell?token=secret',
                    'http://user@127.0.0.1:1234/api/internal/volshell'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                guarded_scoped.install_volshell_bridge(Server(), json.dumps(
                    {'url':url, 'token':'a'*64, 'case_id':'case-a'}))
