"""Real local subprocess framing with synthetic messages; no model turns or evidence."""
import asyncio
import json
from pathlib import Path
import shlex
import sys
import tempfile
import unittest
from unittest.mock import patch

from volatility_workbench.codex import CodexClient, CodexError, MAX_MESSAGE_BYTES


SERVER = r'''
import json, sys, time
for line in sys.stdin.buffer:
    message=json.loads(line)
    method=message.get('method')
    if 'id' not in message:
        continue
    ident=message['id']
    if method=='large':
        sys.stdout.buffer.write(('{'+'"id":'+str(ident)+',"result":{"payload":"').encode())
        for _ in range(273):
            sys.stdout.buffer.write(b'x'*65537)
            sys.stdout.buffer.flush()
        sys.stdout.buffer.write(b'"}}\n')
    elif method=='malformed':
        sys.stdout.buffer.write(b'{invalid JSON}\n')
    elif method=='oversized':
        sys.stdout.buffer.write(b'{'+b'x'*4096+b'\n')
    elif method=='partial':
        sys.stdout.buffer.write(b'{"id":')
        sys.stdout.buffer.flush()
        sys.exit(0)
    elif method=='stall':
        continue
    elif method=='multiple':
        sys.stdout.buffer.write(b'{"method":"synthetic/event","params":{"ok":true}}\n')
        sys.stdout.buffer.write(json.dumps({'id':ident,'result':{'ok':True}}).encode()+b'\n')
    else:
        sys.stdout.buffer.write(json.dumps({'id':ident,'result':{}}).encode()+b'\n')
    sys.stdout.buffer.flush()
'''


class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        script=root/'synthetic.py';script.write_text(SERVER)
        launcher=root/'synthetic-codex'
        launcher.write_text('#!/bin/sh\nexec '+shlex.quote(sys.executable)+' -u '+shlex.quote(str(script))+' "$@"\n')
        launcher.chmod(0o700)
        self.events=[]
        async def event(method,params):self.events.append((method,params))
        async def refuse_request(message):raise AssertionError('No requests expected')
        self.client=CodexClient(event,refuse_request,str(launcher))
        await self.client.start()

    async def asyncTearDown(self):
        await self.client.close()

    async def test_large_fragmented_record_exceeds_previous_16_mib_limit_without_truncation(self):
        result=await self.client.call('large',timeout=10)
        expected=273*65537
        self.assertGreater(expected,16*1024*1024)
        self.assertEqual(len(result['payload']),expected)
        self.assertEqual(result['payload'],'x'*expected)
        self.assertTrue(self.client.connected)
        self.assertEqual(await self.client.call('multiple'),{'ok':True})
        self.assertIn(('synthetic/event',{'ok':True}),self.events)

    async def test_oversized_record_is_bounded_explicit_and_transport_stops(self):
        self.assertEqual(MAX_MESSAGE_BYTES,128*1024*1024)
        with patch('volatility_workbench.codex.MAX_MESSAGE_BYTES',1024):
            with self.assertRaisesRegex(CodexError,'record exceeds the 1,024-byte limit'):
                await self.client.call('oversized',timeout=2)
            await asyncio.wait_for(self.client.reader,2)
        self.assertFalse(self.client.connected)
        self.assertIsNotNone(self.client.proc.returncode)
        with self.assertRaisesRegex(CodexError,'record exceeds'):
            await asyncio.wait_for(self.client.call('initialize'),.2)
        self.assertFalse(self.client.pending)

    async def test_malformed_record_fails_pending_and_subsequent_call_immediately(self):
        with self.assertRaisesRegex(CodexError,'Codex protocol error:'):
            await self.client.call('malformed',timeout=2)
        await asyncio.wait_for(self.client.reader,2)
        self.assertFalse(self.client.connected)
        with self.assertRaisesRegex(CodexError,'Codex protocol error:'):
            await asyncio.wait_for(self.client.call('account/read'),.2)
        self.assertFalse(self.client.pending)

    async def test_incomplete_record_has_explicit_diagnostic(self):
        with self.assertRaisesRegex(CodexError,'Incomplete JSON-RPC record'):
            await self.client.call('partial',timeout=2)
        await asyncio.wait_for(self.client.reader,2)

    async def test_timeout_names_operation_and_deadline(self):
        with self.assertRaisesRegex(CodexError,'Codex stall timed out after 0.02 seconds'):
            await self.client.call('stall',timeout=.02)
        self.assertFalse(self.client.pending)
        self.assertEqual(await self.client.call('initialize'),{})

    async def test_protocol_failure_releases_all_outstanding_calls(self):
        stalled=asyncio.create_task(self.client.call('stall'))
        await asyncio.sleep(.02)
        with self.assertRaises(CodexError):
            await self.client.call('malformed',timeout=2)
        with self.assertRaisesRegex(CodexError,'Codex protocol error:'):
            await asyncio.wait_for(stalled,.2)
        self.assertFalse(self.client.pending)

    async def test_intentional_close_releases_outstanding_calls(self):
        stalled=asyncio.create_task(self.client.call('stall'))
        await asyncio.sleep(.02)
        await self.client.close()
        with self.assertRaisesRegex(CodexError,'connection was closed'):
            await asyncio.wait_for(stalled,.2)
        self.assertFalse(self.client.pending)
        self.assertNotIn('workbench/disconnected',[method for method,_ in self.events])


class ReconnectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_unhealthy_reader_is_replaced_and_resume_excludes_response_history(self):
        # FakeCodex supplies synthetic server replies; never invoke a live turn.
        from support import BackendFixture
        from test_ui import FakeCodex
        from volatility_workbench.app import Workbench
        fixture=BackendFixture();fixture.setUp();self.addCleanup(fixture.doCleanups)
        config=fixture.root/'config.json';config.write_text(json.dumps(fixture.config.to_dict()))
        app=Workbench(config,fixture.root/'ui',codex_factory=FakeCodex)
        await app.start()
        try:
            case=app.add([str(fixture.image)])[0]
            await app.ensure_thread(case)
            old=app.agent
            old.connected=False  # Process still alive, but its stdout reader failed.
            closed=[]
            async def close():closed.append(True)
            old.close=close
            self.assertIsNone(old.proc.returncode)
            await app.ensure_thread(case)
            self.assertEqual(closed,[True])
            self.assertIsNot(app.agent,old)
            resume=next(params for method,params in app.agent.calls if method=='thread/resume')
            self.assertTrue(resume['excludeTurns'])
            self.assertEqual(resume['threadId'],case['thread_id'])
        finally:
            await app.close()
