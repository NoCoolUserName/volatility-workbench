"""Synthetic provider responses only; no model service, credentials or memory scan."""
import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import httpx2 as httpx
from volatility_workbench.providers import CompatibleClient, ProviderError, provider_config, normalize_endpoint
from volatility_workbench.credentials import CredentialStore, CredentialError
from volatility_workbench.codex import child_environment, discover_codex, CodexError
from volatility_workbench.app import Workbench
from test_ui import FakeCodex
from support import BackendFixture


def response(message):
    return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':message}]})


def call(name,args,ident='synthetic-call'):
    return {'id':ident,'type':'function','function':{'name':name,'arguments':json.dumps(args)}}


class CredentialsTests(unittest.TestCase):
    def test_endpoint_binding_and_no_plaintext_fallback(self):
        store=CredentialStore(keychain_factory=lambda: (_ for _ in ()).throw(CredentialError('unavailable')))
        store.set('https://synthetic.example/v1','SYNTHETIC-SECRET','session')
        self.assertEqual(store.get('https://synthetic.example/v1/','session'),'SYNTHETIC-SECRET')
        with self.assertRaises(CredentialError):store.get('https://other.example/v1','session')
        with self.assertRaisesRegex(CredentialError,'unavailable'):store.set('https://synthetic.example/v1','x','keychain')
        store.clear()
        with self.assertRaises(CredentialError):store.get('https://synthetic.example/v1','session')
        for url in ['http://remote.example/v1','https://user:secret@example.com/v1','https://example.com/v1?q=secret',
                    'https://example.com/v1#secret','https://example.com/%2e%2e','https://example.com/../v1']:
            with self.assertRaises(ValueError,msg=url):normalize_endpoint(url)
        self.assertEqual(normalize_endpoint('http://127.0.0.1:8000/v1/'),'http://127.0.0.1:8000/v1')
        self.assertNotEqual(provider_config({'provider':'compatible','endpoint':'https://example.com/v1','model':'a'})['id'],
                            provider_config({'provider':'compatible','endpoint':'https://example.com/v1','model':'b'})['id'])

    def test_gui_native_codex_discovery_and_secret_free_children(self):
        with tempfile.TemporaryDirectory() as root:
            base=Path(root).resolve()/'codex';(base/'bin').mkdir(parents=True)
            launcher=base/'bin'/'codex.js';launcher.write_text('synthetic');launcher.chmod(0o700)
            native=base/'node_modules/@openai/codex-darwin-arm64/vendor/aarch64-apple-darwin/bin/codex'
            native.parent.mkdir(parents=True);native.write_text('synthetic');native.chmod(0o700)
            with patch('volatility_workbench.codex.platform.system',return_value='Darwin'),patch('volatility_workbench.codex.platform.machine',return_value='arm64'):
                self.assertEqual(discover_codex(str(launcher)),str(native))
        with patch.dict(os.environ,{'API_KEY':'SYNTHETIC','OPENAI_API_KEY':'SYNTHETIC','GITHUB_TOKEN':'SYNTHETIC','PATH':'/usr/bin:/bin'},clear=True):
            env=child_environment()
            self.assertNotIn('API_KEY',env);self.assertNotIn('OPENAI_API_KEY',env);self.assertNotIn('GITHUB_TOKEN',env)
            self.assertIn('/opt/homebrew/bin',env['PATH'])


class CompatibleTests(unittest.IsolatedAsyncioTestCase):
    def adapter(self, handler, **config):
        return CompatibleClient({'provider':'compatible','endpoint':'https://synthetic.example/v1','model':'synthetic',**config},
                                CredentialStore(),httpx.MockTransport(handler))

    async def test_synthetic_capability_roundtrip_and_failure(self):
        requests=[]
        def handler(request):
            data=json.loads(request.content);requests.append(data)
            if len(requests)==1:
                challenge=data['messages'][0]['content'].split('challenge ')[1].split('.')[0]
                return response({'role':'assistant','content':None,'tool_calls':[call('workbench_capability_echo',{'challenge':challenge})]})
            return response({'role':'assistant','content':data['messages'][-1]['content']})
        checked=await self.adapter(handler).check()
        self.assertEqual(checked['tool_round_trip'],'passed');self.assertEqual(len(requests),2)
        with self.assertRaisesRegex(ProviderError,'did not request'):
            await self.adapter(lambda r:response({'role':'assistant','content':'no tools'})).check()

    async def test_capability_has_overall_timeout(self):
        async def slow(request):await asyncio.sleep(20)
        with patch('volatility_workbench.providers.CAPABILITY_TIMEOUT',.02):
            with self.assertRaisesRegex(ProviderError,'capability check timed out'):
                await self.adapter(slow).check()

    async def test_redirect_does_not_forward_secret_or_echo_error(self):
        seen=[]
        def handler(request):
            seen.append(request)
            return httpx.Response(307,headers={'Location':'https://elsewhere.example/'},text='SYNTHETIC-SECRET')
        adapter=self.adapter(handler,credential_storage='session')
        adapter.credentials.set(adapter.config['endpoint'],'SYNTHETIC-SECRET','session')
        with self.assertRaisesRegex(ProviderError,'redirected') as exc:
            await adapter.request([{'role':'user','content':'synthetic'}],[])
        self.assertEqual(len(seen),1);self.assertEqual(seen[0].headers['authorization'],'Bearer SYNTHETIC-SECRET')
        self.assertNotIn('SYNTHETIC-SECRET',str(exc.exception))
        adapter.transport=httpx.MockTransport(lambda r:httpx.Response(401,text='SYNTHETIC-SECRET'))
        with self.assertRaisesRegex(ProviderError,'HTTP 401') as exc:
            await adapter.request([],[])
        self.assertNotIn('SYNTHETIC-SECRET',str(exc.exception))
        adapter.transport=httpx.MockTransport(lambda r:response({'role':'assistant','content':'SYNTHETIC-SECRET'}))
        with self.assertRaisesRegex(ProviderError,'credential; response was discarded'):
            await adapter.request([],[])

    async def test_loop_and_response_limits(self):
        calls=[]
        def handler(request):
            calls.append(request)
            return response({'role':'assistant','content':None,'tool_calls':[call('saved_value',{},'call-'+str(len(calls)))]})
        async def execute(*args):return {'value':'SYNTHETIC'}
        async def event(*args):pass
        tool={'name':'saved_value','inputSchema':{'type':'object','additionalProperties':False}}
        with tempfile.TemporaryDirectory() as root,patch('volatility_workbench.providers.MAX_ROUNDS',2):
            path=Path(root).resolve()/'limit.json'
            with self.assertRaisesRegex(ProviderError,'round limit'):
                await self.adapter(handler).run(path,'i','p',[tool],execute,event,asyncio.Event())
            self.assertEqual(len(calls),2)
            self.assertEqual(json.loads(path.read_text())['status'],'incomplete')
        with patch('volatility_workbench.providers.MAX_RESPONSE',100):
            with self.assertRaisesRegex(ProviderError,'response exceeds'):
                await self.adapter(lambda r:response({'role':'assistant','content':'x'*200})).request([],[])

    async def test_tool_bounds_persistence_and_cancellation(self):
        with tempfile.TemporaryDirectory() as root:
            root=str(Path(root).resolve());path=Path(root)/'session.json';events=[];executions=[];requests=[]
            tool={'name':'saved_value','inputSchema':{'type':'object','properties':{'offset':{'type':'integer'}},'required':['offset'],'additionalProperties':False}}
            def handler(request):
                data=json.loads(request.content);requests.append(data)
                if len(requests)==1:return response({'role':'assistant','content':None,'tool_calls':[call('saved_value',{'offset':7})]})
                return response({'role':'assistant','content':'SYNTHETIC observation'})
            async def execute(name,args):executions.append((name,args));return {'value':'SYNTHETIC'}
            async def event(name,data):events.append(name)
            adapter=self.adapter(handler)
            text=await adapter.run(path,'synthetic instructions','synthetic question',[tool],execute,event,asyncio.Event())
            self.assertEqual(text,'SYNTHETIC observation');self.assertEqual(executions,[('saved_value',{'offset':7})])
            reopened=self.adapter(handler)
            await reopened.run(path,'same instructions','followup',[tool],execute,event,asyncio.Event())
            self.assertEqual(len(json.loads(path.read_text())['messages']),7)
            bad=self.adapter(lambda r:response({'role':'assistant','content':None,'tool_calls':[call('shell',{})]}))
            with self.assertRaisesRegex(ProviderError,'allowlist'):
                await bad.run(Path(root)/'bad.json','i','p',[tool],execute,event,asyncio.Event())
            self.assertEqual(len(executions),1)
            invalid=self.adapter(lambda r:response({'role':'assistant','content':None,'tool_calls':[call('saved_value',{'offset':'bad'})]}))
            with self.assertRaisesRegex(ProviderError,'invalid tool arguments'):
                await invalid.run(Path(root)/'invalid.json','i','p',[tool],execute,event,asyncio.Event())
            async def slow(request):await asyncio.sleep(10)
            cancelpath=Path(root)/'cancel.json'
            task=asyncio.create_task(self.adapter(slow).run(cancelpath,'i','p',[tool],execute,event,asyncio.Event()))
            await asyncio.sleep(.02);task.cancel()
            with self.assertRaises(asyncio.CancelledError):await task
            self.assertEqual(json.loads(cancelpath.read_text())['status'],'incomplete')
            with self.assertRaisesRegex(ProviderError,'incomplete'):
                await adapter.run(cancelpath,'i','p',[tool],execute,event,asyncio.Event())


class WorkbenchProviderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fixture=BackendFixture();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.config=self.fixture.root/'config.json';self.config.write_text(json.dumps(self.fixture.config.to_dict()))
        self.app=Workbench(self.config,self.fixture.root/'ui',codex_factory=FakeCodex);await self.app.start()
        self.case=self.app.add([str(self.fixture.image)])[0]
    async def asyncTearDown(self):await self.app.close()

    async def wait_until(self, predicate, job):
        async def wait():
            while not predicate():
                if job['status'] in ('failed','incomplete','cancelled'):
                    self.fail('Synthetic provider job ended before the expected state: '+str(job))
                await asyncio.sleep(.025)
        await asyncio.wait_for(wait(),15)

    async def configure_extraction_provider(self):
        cfg={'provider':'compatible','endpoint':'http://127.0.0.1:9876/v1','model':'synthetic',
             'allow_case_content':True,'case_id':self.case['id']}
        await self.app.configure_provider(cfg)
        self.case['provider']['capability_check']='passed'
        requests=[];tool_results=[]
        def handler(request):
            data=json.loads(request.content);requests.append(data)
            if data['messages'][-1]['role']=='tool':
                tool_results.append(json.loads(data['messages'][-1]['content']))
                return response({'role':'assistant','content':'SYNTHETIC extraction request handled.'})
            return response({'role':'assistant','content':None,'tool_calls':[call('run_plugin',{
                'image':str(self.fixture.image),'plugin':'windows.pslist.PsList','arguments':['--dump']},
                'synthetic-dump-'+str(len(requests)))]})
        self.app.compatible_factory=lambda config,secrets:CompatibleClient(config,secrets,httpx.MockTransport(handler))
        return requests,tool_results

    async def test_compatible_extraction_waits_for_exact_human_consent(self):
        requests,results=await self.configure_extraction_provider()
        count_path=self.fixture.root/'analysis-count.jsonl'
        # Decline and an unchecked acknowledgement must both prevent execution.
        # A later explicit approval permits one harmless fake-analyzer run only.
        for index,answer in enumerate(({'action':'decline','content':{}},
                {'action':'accept','content':{'confirm':False}},
                {'action':'accept','content':{'confirm':True}})):
            job=self.app.enqueue(self.case['id'],'question','SYNTHETIC dump request '+str(index))
            await self.wait_until(lambda:bool(self.app.approvals),job)
            pending=next(iter(self.app.approvals.values()))
            self.assertEqual(pending['method'],'mcpServer/elicitation/request')
            self.assertEqual(pending['case_id'],self.case['id'])
            self.assertIn('windows.pslist.PsList',pending['params']['message'])
            self.assertIn('--dump',pending['params']['message'])
            self.assertIn(str(self.fixture.image),pending['params']['message'])
            self.assertFalse(count_path.exists(),'Even a valid tool call must wait for the human decision')
            self.assertFalse(list(self.app.directory(self.case).rglob('synthetic-dump.txt')))
            self.assertFalse(pending['future'].done())
            pending['future'].set_result(answer)
            await self.wait_until(lambda:job['status']=='completed' and self.app.active is None,job)
            self.assertFalse(self.app.approvals)
            self.assertEqual(len(requests),(index+1)*2)
            if index<2:
                self.assertFalse(count_path.exists())
                self.assertIn('not approved',json.dumps(results[-1]))
            else:
                executions=[json.loads(line) for line in count_path.read_text().splitlines()]
                self.assertEqual(len(executions),1)
                self.assertIn('--dump',executions[0]['argv'])
                self.assertEqual(len(list(self.app.directory(self.case).rglob('synthetic-dump.txt'))),1)
                self.assertNotIn('error',results[-1])

    async def test_compatible_stop_while_extraction_consent_pending_never_runs(self):
        requests,results=await self.configure_extraction_provider()
        job=self.app.enqueue(self.case['id'],'question','SYNTHETIC pending dump to cancel')
        await self.wait_until(lambda:bool(self.app.approvals),job)
        pending=next(iter(self.app.approvals.values()))
        self.assertFalse((self.fixture.root/'analysis-count.jsonl').exists())
        await self.app.stop()
        async def finished():
            while self.app.active is not None:await asyncio.sleep(.025)
        await asyncio.wait_for(finished(),15)
        self.assertEqual(job['status'],'incomplete')
        self.assertFalse(self.app.approvals)
        self.assertTrue(pending['future'].done())
        self.assertEqual(pending['future'].result(),'decline')
        self.assertFalse((self.fixture.root/'analysis-count.jsonl').exists())
        self.assertFalse(list(self.app.directory(self.case).rglob('synthetic-dump.txt')))
        self.assertEqual(len(requests),1)
        self.assertEqual(results,[])

    async def test_switch_is_explicit_preserves_codex_and_secrets_private(self):
        self.case['thread_id']='saved-codex-thread'
        cfg={'provider':'compatible','endpoint':'http://127.0.0.1:9876/v1','model':'synthetic'}
        status=await self.app.configure_provider(cfg,secret='SYNTHETIC-SECRET')
        self.assertNotIn('SYNTHETIC-SECRET',json.dumps(status));self.assertNotIn('SYNTHETIC-SECRET',self.app.provider_path.read_text())
        self.assertEqual(self.app.case_provider(self.case)['provider'],'codex')
        await self.app.configure_provider({**cfg,'case_id':self.case['id']})
        self.assertIsNone(self.case['thread_id'])
        with self.assertRaisesRegex(ProviderError,'case content'):
            await self.app.ensure_thread(self.case)
        await self.app.configure_provider({'provider':'codex','case_id':self.case['id']})
        self.assertEqual(self.case['thread_id'],'saved-codex-thread')
        reopened=Workbench(self.config,self.app.root,codex_factory=FakeCodex)
        self.assertEqual(reopened.case(self.case['id'])['thread_id'],'saved-codex-thread')
        self.assertEqual(reopened.case_provider(reopened.case(self.case['id']))['provider'],'codex')

    async def test_changed_endpoint_cannot_inherit_inflight_capability_success(self):
        cfg={'provider':'compatible','endpoint':'http://127.0.0.1:9876/v1','model':'synthetic'}
        await self.app.configure_provider(cfg)
        started=asyncio.Event();finish=asyncio.Event()
        class SlowCheck:
            def __init__(self,*args):pass
            async def check(self):
                started.set();await finish.wait()
                return {'connected':True,'tool_round_trip':'passed'}
        self.app.compatible_factory=SlowCheck
        checking=asyncio.create_task(self.app.check_provider())
        await started.wait()
        await self.app.configure_provider({**cfg,'endpoint':'http://127.0.0.1:9877/v1'})
        finish.set()
        with self.assertRaisesRegex(ProviderError,'result was discarded'):await checking
        self.assertNotIn('capability_check',self.app.provider)
        self.assertNotIn('capability_check',json.loads(self.app.provider_path.read_text()))

    async def test_compatible_stop_cancels_queued_work_and_preserves_incomplete_session(self):
        cfg={'provider':'compatible','endpoint':'http://127.0.0.1:9876/v1','model':'synthetic','allow_case_content':True,'case_id':self.case['id']}
        await self.app.configure_provider(cfg);self.case['provider']['capability_check']='passed'
        started=asyncio.Event()
        async def handler(request):started.set();await asyncio.sleep(20)
        self.app.compatible_factory=lambda config,secrets:CompatibleClient(config,secrets,httpx.MockTransport(handler))
        job=self.app.enqueue(self.case['id'],'question','SYNTHETIC cancellable request')
        other=self.app.add([str(self.fixture.image)])[0]
        queued=self.app.enqueue(other['id'],'question','SYNTHETIC queued request')
        await asyncio.wait_for(started.wait(),3)
        await self.app.stop()
        for _ in range(100):
            if self.app.active is None:break
            await asyncio.sleep(.025)
        self.assertEqual(job['status'],'incomplete');self.assertEqual(queued['status'],'cancelled')
        saved=next(self.app.directory(self.case).glob('provider-compatible-*.json'))
        self.assertEqual(json.loads(saved.read_text())['status'],'incomplete')
        self.assertFalse((self.fixture.root/'analysis-count.jsonl').exists())

    async def test_real_mcp_saved_coverage_tool_mock_model_zero_analysis(self):
        cfg={'provider':'compatible','endpoint':'http://127.0.0.1:9876/v1','model':'synthetic','allow_case_content':True,'case_id':self.case['id']}
        await self.app.configure_provider(cfg)
        self.case['provider']['capability_check']='passed'  # separate capability test uses synthetic nonce above
        requests=[]
        def handler(request):
            data=json.loads(request.content);requests.append(data)
            if len(requests)==1:
                names={t['function']['name'] for t in data['tools']}
                self.assertIn('get_coverage',names);self.assertIn('case_save_report',names);self.assertNotIn('shell',names)
                return response({'role':'assistant','content':None,'tool_calls':[call('get_coverage',{'image':str(self.fixture.image)})]})
            self.assertEqual(data['messages'][-1]['role'],'tool')
            tool_result=json.loads(data['messages'][-1]['content']);self.assertNotIn('error',tool_result)
            return response({'role':'assistant','content':'SYNTHETIC: saved coverage is not a clean finding.'})
        self.app.compatible_factory=lambda config,secrets:CompatibleClient(config,secrets,httpx.MockTransport(handler))
        job=self.app.enqueue(self.case['id'],'question','Read saved coverage only')
        for _ in range(200):
            if job['status'] not in ('queued','running','stopping'):break
            await asyncio.sleep(.025)
        self.assertEqual(job['status'],'completed',job)
        self.assertEqual(len(requests),2)
        self.assertFalse((self.fixture.root/'analysis-count.jsonl').exists())
        self.assertIn('SYNTHETIC:',self.case['messages'][-1]['text'])
        self.assertTrue(list(self.app.directory(self.case).glob('provider-compatible-*.json')))
