"""Synthetic model catalogs and transport; never start a real model turn."""
import json
import unittest

import httpx2 as httpx

from volatility_workbench.app import Workbench
from volatility_workbench.credentials import CredentialStore
from volatility_workbench.models import codex_models
from volatility_workbench.providers import CompatibleClient, ProviderError, provider_config
from support import BackendFixture
from test_ui import FakeCodex


class ModelConfigTests(unittest.TestCase):
    def test_defaults_and_catalog_effort_order_are_model_specific(self):
        self.assertEqual(provider_config({})['model'],'gpt-6-astra')
        self.assertEqual(provider_config({})['reasoning_effort'],'high')
        catalog=codex_models([{'model':'synthetic','supportedReasoningEfforts':[
            {'reasoningEffort':'xhigh'},{'reasoningEffort':'low'}], 'defaultReasoningEffort':'low'},
            {'model':'hidden','hidden':True}, {'model':'bad\nidentifier'}])
        self.assertEqual(catalog,[{'model':'synthetic','label':'synthetic','efforts':['xhigh','low'],'default_effort':'low'}])
        for effort in (False,13,'High','high\n'):
            with self.assertRaises(ValueError):provider_config({'reasoning_effort':effort})


class ModelSettingsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fixture=BackendFixture();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.config=self.fixture.root/'config.json';self.config.write_text(json.dumps(self.fixture.config.to_dict()))
        self.app=Workbench(self.config,self.fixture.root/'ui',codex_factory=FakeCodex);await self.app.start()
        self.case=self.app.add([str(self.fixture.image)])[0]
    async def asyncTearDown(self):await self.app.close()

    async def test_catalog_is_explicit_no_thread_and_rejects_unsupported_setting(self):
        clients=[]
        def factory(*args):
            client=FakeCodex(*args);clients.append(client);return client
        self.app.factory=factory
        catalog=await self.app.provider_models({'provider':'codex'})
        self.assertEqual(catalog['models'][0]['efforts'],['low','medium','high','xhigh'])
        self.assertEqual([method for client in clients for method,_ in client.calls],['model/list'])
        original=dict(self.app.provider)
        with self.assertRaisesRegex(ValueError,'not supported'):
            await self.app.configure_provider({'provider':'codex','model':'synthetic-alternate','reasoning_effort':'xhigh'})
        with self.assertRaisesRegex(ValueError,'not in the available'):
            await self.app.configure_provider({'provider':'codex','model':'unlisted','reasoning_effort':'high'})
        self.assertEqual(self.app.provider,original)
        self.assertIsNone(self.case['thread_id'])

    async def test_default_only_and_explicit_case_preserve_conversation_and_next_turn(self):
        await self.app.ensure_thread(self.case)
        thread=self.case['thread_id']
        await self.app.configure_provider({'provider':'codex','model':'gpt-6-astra','reasoning_effort':'xhigh'})
        self.assertEqual(self.app.case_provider(self.case)['reasoning_effort'],'high')
        await self.app.configure_provider({'provider':'codex','model':'gpt-6-astra','reasoning_effort':'xhigh','case_id':self.case['id']})
        self.assertEqual(self.case['thread_id'],thread)
        await self.app.ensure_thread(self.case)
        resume=next(params for method,params in self.app.agent.calls if method=='thread/resume')
        self.assertEqual(resume['model'],'gpt-6-astra')
        self.assertEqual(resume['config']['model_reasoning_effort'],'xhigh')
        await self.app.codex_turn(self.case,{'id':'synthetic','kind':'question'},'Synthetic response only')
        turn=next(params for method,params in self.app.agent.calls if method=='turn/start')
        self.assertEqual((turn['model'],turn['effort']),('gpt-6-astra','xhigh'))
        reopened=Workbench(self.config,self.app.root,codex_factory=FakeCodex)
        self.assertEqual(reopened.case_provider(reopened.case(self.case['id']))['reasoning_effort'],'xhigh')
        await self.app.configure_provider({'provider':'codex','model':'synthetic-alternate','reasoning_effort':'low','case_id':self.case['id']})
        self.assertEqual(self.app.case_provider(self.case)['model'],'synthetic-alternate')
        self.assertEqual(self.app.provider['model'],'gpt-6-astra','A named-case save does not change the new-case default')
        self.assertEqual(self.app.provider['reasoning_effort'],'xhigh')

    async def test_compatible_effort_change_requires_new_capability_check(self):
        config={'provider':'compatible','endpoint':'https://synthetic.example/v1','model':'synthetic','reasoning_effort':'high','case_id':self.case['id']}
        await self.app.configure_provider(config)
        self.case['provider']['capability_check']='passed'
        self.case['thread_id']='compatible-synthetic'
        await self.app.configure_provider({**config,'reasoning_effort':'xhigh'})
        self.assertNotIn('capability_check',self.app.case_provider(self.case))
        self.assertNotIn('capability_check',self.app.provider)
        self.assertEqual(self.case['thread_id'],'compatible-synthetic')

    async def test_capability_check_targets_saved_case_without_changing_default(self):
        config={'provider':'compatible','endpoint':'https://synthetic.example/v1','model':'synthetic',
                'reasoning_effort':'xhigh','case_id':self.case['id']}
        await self.app.configure_provider(config)
        checked=[]
        class SyntheticCheck:
            def __init__(self, configuration, credentials):checked.append(configuration)
            async def check(self):return {'connected':True,'tool_round_trip':'passed'}
        self.app.compatible_factory=SyntheticCheck
        await self.app.check_provider(self.case['id'])
        self.assertEqual(checked[0]['reasoning_effort'],'xhigh')
        self.assertEqual(self.case['provider']['capability_check'],'passed')
        self.assertEqual(self.app.provider['provider'],'codex')
        self.assertNotIn('capability_check',self.app.provider)


class CompatibleModelTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_omits_effort_override_is_transmitted_and_catalog_is_get_only(self):
        requests=[]
        def handler(request):
            requests.append(request)
            if request.method=='GET':return httpx.Response(200,json={'data':[{'id':'synthetic-a'},{'id':'synthetic-b'}]})
            return httpx.Response(200,json={'choices':[{'message':{'role':'assistant','content':'synthetic'}}]})
        config={'provider':'compatible','endpoint':'https://synthetic.example/v1','model':'synthetic-a'}
        store=CredentialStore();adapter=CompatibleClient(config,store,httpx.MockTransport(handler))
        self.assertIsNone(adapter.config['reasoning_effort'])
        await adapter.request([],[])
        self.assertNotIn('reasoning_effort',json.loads(requests[-1].content))
        adapter=CompatibleClient({**config,'reasoning_effort':'xhigh'},store,httpx.MockTransport(handler))
        await adapter.request([],[])
        self.assertEqual(json.loads(requests[-1].content)['reasoning_effort'],'xhigh')
        self.assertEqual([m['model'] for m in await adapter.list_models()],['synthetic-a','synthetic-b'])
        self.assertEqual((requests[-1].method,str(requests[-1].url),requests[-1].content),('GET','https://synthetic.example/v1/models',b''))

    async def test_catalog_refuses_redirect_and_secret_reflection(self):
        store=CredentialStore();store.set('https://synthetic.example/v1','SYNTHETIC-SECRET','session')
        config={'provider':'compatible','endpoint':'https://synthetic.example/v1','model':'synthetic','credential_storage':'session'}
        seen=[]
        def redirect(request):
            seen.append(request)
            return httpx.Response(307,headers={'Location':'https://other.example/models'})
        adapter=CompatibleClient(config,store,httpx.MockTransport(redirect))
        with self.assertRaisesRegex(ProviderError,'redirected'):await adapter.list_models()
        self.assertEqual(len(seen),1)
        adapter.transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'data':[{'id':'SYNTHETIC-SECRET'}]}))
        with self.assertRaisesRegex(ProviderError,'credential; response discarded'):await adapter.list_models()
        adapter.transport=httpx.MockTransport(lambda request:httpx.Response(200,
            content=json.dumps({'data':[{'id':'SYNTHETIC-SECRET'}]}).replace('SYNTHETIC','\\u0053YNTHETIC')))
        with self.assertRaisesRegex(ProviderError,'credential; response discarded'):await adapter.list_models()
