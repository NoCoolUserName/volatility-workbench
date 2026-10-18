"""AI helper/controller checks use a toy interpreter and synthetic case only."""
import asyncio
import dataclasses
import hashlib
import hmac
import json
import os
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from volatility_workbench.app import Workbench
from volatility_workbench.volshell import VolshellManager
from volatility_workbench.volshell_agent import AgentVolshell, MAX_OUTPUT, validate_call
from support import BackendFixture
from test_volshell import FAKE_PYTHON, wait_until


HELPERS = r'''
def hh(): print("SYNTHETIC helper descriptions")
def ps(): return ["<fixture!Process in layer Synthetic at 0x100>", "<fixture!Process at 0x200>"]
def db(offset, count=128, layer_name=None):
    if offset == 99: raise ValueError("SYNTHETIC unreadable address")
    if offset == 98: time.sleep(60)
    if offset == 97:
        print("SYNTHETIC partial output", flush=True)
        time.sleep(.3)
    if offset == 96: print("X" * 60000)
    print("SYNTHETIC bytes offset=" + str(offset) + " count=" + str(count))
def dt(type_name, offset=None): print("SYNTHETIC PID 120 for " + type_name + " at " + str(offset))
def cl(layer_name): print("SYNTHETIC layer " + layer_name)
def cp(pid): print("SYNTHETIC PID selected " + str(pid))
console = FixtureConsole({"hh":hh,"ps":ps,"db":db,"dw":db,"dd":db,"dq":db,
                          "dis":db,"dt":dt,"cl":cl,"cp":cp})
console.interact(banner="SYNTHETIC helper adapter; image is never opened.")
'''


class CallSchemaTests(unittest.TestCase):
    def test_only_closed_scalar_helper_calls_are_generated(self):
        call = validate_call({'image_id':'E001','helper':'db','arguments':{'offset':'0x100','count':16}})
        self.assertEqual(call['command'], 'db(offset=256, count=16)')
        self.assertEqual(validate_call({'image_id':'E001','helper':'ps','mode':'windows',
                                      'arguments':{'start':2,'limit':3}})['command'], 'ps()[2:5]')
        malicious = "'); __import__('os').system('should-not-run'); #"
        call = validate_call({'image_id':'E001','helper':'cl','arguments':{'layer_name':malicious}})
        received = []
        eval(call['command'], {'__builtins__':{}, 'cl':lambda **kw:received.append(kw)})
        self.assertEqual(received, [{'layer_name':malicious}])

    def test_rejects_arbitrary_code_scripts_dumps_and_unbounded_scope(self):
        invalid = [
            {'helper':'exec','arguments':{}}, {'helper':'dpo'}, {'helper':'rs'},
            {'helper':'ps'}, {'helper':'ps','mode':'linux','arguments':{'limit':201}},
            {'helper':'db','arguments':{'offset':True}},
            {'helper':'db','arguments':{'offset':-1}},
            {'helper':'db','arguments':{'offset':0,'count':4097}},
            {'helper':'db','arguments':{'offset':0,'count':0}},
            {'helper':'db','arguments':{'offset':'1; print(1)'}},
            {'helper':'db','arguments':{'offset':0,'file':'outside'}},
            {'helper':'dt','arguments':{'type_name':'x\nprint(1)'}},
            {'helper':'hh','arguments':[]}, {'helper':'hh','approved':True},
        ]
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(ValueError):
                validate_call({'image_id':'E001', **data})


class AgentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        fixture = BackendFixture()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        fake = fixture.root / 'fake-helper-python'
        fake.write_text('#!' + sys.executable + '\n' + FAKE_PYTHON.split('console = FixtureConsole',1)[0] + HELPERS)
        fake.chmod(0o700)
        config = dataclasses.replace(fixture.config, vol_python=fake)
        config_path = fixture.root / 'config.json'
        config_path.write_text(json.dumps(config.to_dict()))
        self.app = Workbench(config_path, fixture.root / 'ui')
        self.case = self.app.add([str(fixture.image)])[0]
        self.case['thread_id'] = 'synthetic-thread'
        self.job = {'id':'synthetic-job','case_id':self.case['id'],'kind':'report','status':'running'}
        self.app.active = self.job
        self.app.state['jobs'].append(self.job)
        self.manager = VolshellManager(startup_timeout=1, stop_timeout=.15)
        self.adapter = AgentVolshell(self.app, self.manager, timeout=2)
        self.app.volshell_agent = self.adapter
        self.addAsyncCleanup(self.adapter.shutdown)
        self.call = {'image_id':self.case['images'][0]['id'],'helper':'db','arguments':{'offset':256,'count':16}}
        self.original_image = fixture.image.read_bytes()

    async def execute(self, **changes):
        return await self.app.run_agent_volshell(self.case['id'], {**self.call, **changes})

    def spawns(self):
        path = self.fixture.root / 'spawn.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    async def test_observation_is_streamed_saved_bounded_and_reusable_without_report_promotion(self):
        task = asyncio.create_task(self.execute(arguments={'offset':97,'count':16}))
        await wait_until(lambda: self.adapter.snapshot() and 'partial output' in
                         ''.join(e['text'] for e in self.adapter.snapshot()['entries']))
        self.assertEqual(self.app.volshell_snapshot()['agent_activity']['status'], 'running')
        self.assertFalse(task.done())
        result = await task
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['evidence_status'], 'exploratory_unverified')
        self.assertNotIn('__WORKBENCH', result['output'])
        self.assertNotIn('exec(', result['output'])
        path = self.app.directory(self.case) / result['observation_path']
        saved = json.loads(path.read_text())
        self.assertEqual(saved['id'], result['id'])
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), result['observation_sha256'])
        self.assertTrue((self.app.directory(self.case) / result['transcript_path']).is_file())
        self.assertEqual(self.app.read_file(self.case,result['observation_path'])['evidence_status'],
                         'exploratory_unverified')
        self.assertEqual(self.case['reports'], [])
        self.assertEqual(self.fixture.image.read_bytes(), self.original_image)
        huge = await self.execute(arguments={'offset':96})
        self.assertTrue(huge['truncated'])
        self.assertLessEqual(len(huge['output']), MAX_OUTPUT)
        self.assertIn('offset=96', huge['output'])
        self.assertEqual(len(self.spawns()),1)

    async def test_helper_state_reused_only_inside_same_job_image_and_mode(self):
        first = await self.execute(helper='ps',mode='windows',arguments={'limit':1})
        self.assertIn('0x100', first['output'])
        self.assertNotIn('0x200', first['output'])
        second = await self.execute(helper='dt',mode='windows',arguments={'type_name':'fixture!Process','offset':'0x100'})
        self.assertIn('PID 120', second['output'])
        self.assertEqual(first['session_id'], second['session_id'])
        self.assertGreater(int(second['first_transcript_entry']), int(first['last_transcript_entry']))
        third = await self.execute(helper='hh',arguments={})
        self.assertNotEqual(first['session_id'], third['session_id'])
        self.assertIsNone(self.app.volshell.snapshot()['session'])
        await self.adapter.close_job(self.job['id'])
        self.assertFalse(self.manager.busy)
        self.assertEqual(self.adapter.snapshot()['status'],'completed')

    async def test_failure_timeout_and_cancel_are_terminal_and_clean_up_interpreter(self):
        failure = await self.execute(arguments={'offset':99})
        self.assertEqual(failure['status'], 'failed')
        self.assertIn('unreadable address', failure['error'])
        self.assertFalse(self.manager.busy)
        self.adapter.timeout = .2
        timeout = await self.execute(arguments={'offset':98})
        self.assertEqual(timeout['status'], 'failed')
        self.assertIn('deadline', timeout['error'])
        self.assertFalse(self.manager.busy)
        self.adapter.timeout = 2
        task = asyncio.create_task(self.execute(arguments={'offset':98}))
        await wait_until(lambda: self.adapter.snapshot()['status']=='running')
        self.app.cancel.set()
        with self.assertRaises(asyncio.CancelledError): await task
        self.assertEqual(self.adapter.snapshot()['status'],'cancelled')
        self.assertFalse(self.manager.busy)

    async def test_exact_job_case_image_binding_and_no_manual_session_adoption(self):
        await self.app.volshell.start(self.case['id'],self.call['image_id'],self.fixture.image,
                                      'generic',self.app.config,self.app.directory(self.case))
        self.addAsyncCleanup(self.app.volshell.shutdown)
        await wait_until(lambda:self.app.volshell.snapshot()['session']['ready'])
        manual = self.app.volshell.snapshot()['session']['id']
        result = await self.execute()
        self.assertNotEqual(result['session_id'],manual)
        self.assertEqual(self.app.volshell.snapshot()['session']['id'],manual)
        with self.assertRaises(ValueError): await self.execute(image_id='other-image')
        self.job['volshell_image_id']='other-image'
        with self.assertRaises(ValueError): await self.execute()
        self.job.pop('volshell_image_id')
        self.job['status']='stopping'
        with self.assertRaises(ValueError): await self.execute()
        self.job['status']='running'
        other = self.app.add([str(self.fixture.image)])[0]
        with self.assertRaises(ValueError): await self.app.run_agent_volshell(other['id'],self.call)

    async def test_previous_case_output_cannot_enter_a_new_failed_observation(self):
        await self.execute()
        other = self.app.add([str(self.fixture.image)])[0]
        newjob = {'id':'other-job','case_id':other['id'],'kind':'report','status':'running'}
        self.app.active = newjob
        with patch.object(self.app,'case_backend',side_effect=ValueError('Synthetic resolution failure')):
            result = await self.adapter.execute(other,newjob,{'image_id':other['images'][0]['id'],'helper':'hh'})
        self.assertEqual(result['status'],'failed')
        self.assertEqual(result['output'],'')
        self.assertNotIn('SYNTHETIC bytes',json.dumps(result))

    async def test_question_collection_requires_exact_approval_and_rechecks_owner(self):
        self.job['kind']='question'
        task = asyncio.create_task(self.execute())
        await wait_until(lambda:bool(self.app.approvals))
        approval = next(iter(self.app.approvals.values()))
        self.assertIn(self.call['image_id'], approval['params']['message'])
        self.assertIn('db(offset=256, count=16)',approval['params']['message'])
        self.assertEqual(self.spawns(),[])
        approval['future'].set_result({'action':'decline'})
        with self.assertRaisesRegex(ValueError,'not approved'): await task
        task = asyncio.create_task(self.execute())
        await wait_until(lambda:bool(self.app.approvals))
        next(iter(self.app.approvals.values()))['future'].set_result({'action':'accept','content':{'confirm':True}})
        result = await task
        self.assertEqual(result['status'],'completed')
        task = asyncio.create_task(self.execute())
        await wait_until(lambda:bool(self.app.approvals))
        self.app.active = dict(self.job,id='replacement')
        next(iter(self.app.approvals.values()))['future'].set_result({'action':'accept','content':{'confirm':True}})
        with self.assertRaises(asyncio.CancelledError): await task

    async def test_trusted_volshell_investigation_and_metadata_do_not_prompt(self):
        self.job['kind']='question'
        with patch.object(self.app,'agent_request',side_effect=AssertionError('Unexpected approval')):
            await self.execute(helper='hh',arguments={})
            await self.execute(helper='cl',arguments={'layer_name':'Synthetic'})
            self.job['volshell_session_id']='app-created-session'
            await self.execute()
        self.assertEqual(self.adapter.snapshot()['status'],'completed')

    async def test_concurrent_call_is_rejected_and_stop_closes_gate_before_manual_cleanup(self):
        task = asyncio.create_task(self.execute(arguments={'offset':98}))
        await wait_until(lambda: self.adapter.snapshot() and self.adapter.snapshot()['status']=='running')
        with self.assertRaisesRegex(ValueError,'current AI'): await self.execute()
        entered = asyncio.Event()
        release = asyncio.Event()
        queued={'id':'queued-job','case_id':self.case['id'],'status':'queued','kind':'question'}
        self.app.state['jobs'].append(queued)
        async def slow_manual_cleanup():
            entered.set()
            await release.wait()
        with patch.object(self.app.volshell,'shutdown',slow_manual_cleanup):
            stop = asyncio.create_task(self.app.stop())
            await asyncio.wait_for(entered.wait(),3)
            self.assertTrue(self.app.cancel.is_set())
            self.assertEqual(self.job['status'],'stopping')
            self.assertEqual(queued['status'],'cancelled')
            self.assertFalse(self.manager.busy)
            self.assertEqual(self.adapter.snapshot()['status'],'cancelled')
            with self.assertRaises(ValueError): await self.execute()
            release.set()
            await stop
        with self.assertRaises(asyncio.CancelledError): await task

    async def test_worker_cancels_inflight_helper_and_pending_approval_before_next_job(self):
        for approve in (False,True):
            self.app.active=None
            self.app.cancel=asyncio.Event()
            self.job.update(status='queued',kind='question')
            self.job.pop('finished_at',None)
            if approve:self.job['volshell_session_id']='trusted'
            tasks=[]
            async def execute(case,job):
                task=asyncio.create_task(self.execute(arguments={'offset':98}))
                tasks.append(task)
                if approve:
                    await wait_until(lambda:self.adapter.snapshot() and self.adapter.snapshot()['status']=='running')
                else:
                    await wait_until(lambda:bool(self.app.approvals))
            with patch.object(self.app,'_execute',execute):
                worker=asyncio.create_task(self.app._worker())
                self.app.queue.put_nowait(self.job)
                await wait_until(lambda:self.job.get('finished_at') is not None)
                worker.cancel()
                await asyncio.gather(worker,return_exceptions=True)
                await asyncio.gather(*tasks,return_exceptions=True)
            self.assertIsNone(self.app.active)
            self.assertFalse(self.app.approvals)
            self.assertFalse(self.manager.busy)
            self.assertTrue(tasks[0].cancelled())
        self.assertEqual(self.adapter.snapshot()['status'],'cancelled')

    async def test_observation_read_allowlist_rejects_transcripts_traversal_and_symlinks(self):
        result=await self.execute()
        for path in ('',result['transcript_path'],'volshell-observations/../state.json',
                     'volshell-observations/not-an-id.json','volshell-observations/'+('0'*32)+'.json/extra'):
            with self.subTest(path=path),self.assertRaises(ValueError):self.app.read_file(self.case,path)
        link=self.app.directory(self.case)/'volshell-observations'/('f'*32+'.json')
        link.symlink_to(self.fixture.image)
        with self.assertRaises(ValueError):self.app.read_file(self.case,str(link.relative_to(self.app.directory(self.case))))

    async def test_existing_codex_thread_resume_receives_private_bridge(self):
        self.app.volshell_bridge_origin='http://127.0.0.1:12345'
        self.app.volshell_bridge_secret=b'synthetic-private-key'
        calls=[]
        async def call(method,params,**kwargs):
            calls.append((method,params))
            return {'thread':{'id':self.case['thread_id']},'approvalPolicy':'on-request',
                    'approvalsReviewer':'user','sandbox':{'type':'readOnly'}}
        self.app.agent=SimpleNamespace(call=call)
        with patch.object(self.app,'connect',AsyncMock()),patch.dict(os.environ,{'CODEX_HOME':str(self.fixture.root)}):
            await self.app.ensure_thread(self.case)
        self.assertEqual(calls[0][0],'thread/resume')
        env=calls[0][1]['config']['mcp_servers.volatility']['env']
        bridge=json.loads(env['WORKBENCH_VOLSHELL_BRIDGE'])
        self.assertEqual(bridge['case_id'],self.case['id'])
        self.assertEqual(bridge['token'],hmac.new(b'synthetic-private-key',self.case['id'].encode(),hashlib.sha256).hexdigest())
        self.assertNotIn('dynamicTools',calls[0][1])
        self.assertIn('case_volshell',calls[0][1]['developerInstructions'])

    async def test_compatible_gets_bridge_but_readiness_keeps_exact_core_tool_inventory(self):
        self.app.volshell_bridge_origin='http://127.0.0.1:12345'
        self.app.volshell_bridge_secret=b'synthetic-private-key'
        transports=[]
        class Captured(Exception): pass
        def capture(transport,**kwargs):
            transports.append(transport)
            raise Captured()
        provider={'provider':'compatible','allow_case_content':True,'capability_check':'passed'}
        with patch.object(self.app,'case_provider',return_value=provider),patch('volatility_workbench.app.Client',capture):
            with self.assertRaises(Captured):await self.app.compatible_turn(self.case,self.job,'synthetic')
            with self.assertRaises(Captured):await self.app.readiness(self.case,self.job)
        self.assertIn('WORKBENCH_VOLSHELL_BRIDGE',transports[0].env)
        self.assertNotIn('WORKBENCH_VOLSHELL_BRIDGE',transports[1].env)

    async def test_http_deadline_cancellation_cleans_pending_collection_approval(self):
        self.job['kind']='question'
        task=asyncio.create_task(self.execute())
        await wait_until(lambda:bool(self.app.approvals))
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertFalse(self.app.approvals)
        self.assertIsNone(self.app._agent_volshell_task)
        self.assertEqual(self.spawns(),[])
