"""Synthetic AI drafts never become executed Python or provider tool calls."""
import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from volatility_workbench.volshell_assist import parse_proposal, suggest
from volatility_workbench.providers import ProviderError


class ProposalTests(unittest.TestCase):
    def test_draft_is_parsed_without_execution(self):
        draft = 'raise RuntimeError("must never execute")'
        self.assertEqual(parse_proposal(json.dumps({'command':draft,'explanation':'Review first'}))['command'],draft)
        self.assertEqual(parse_proposal('{"command":"","explanation":"Which process?"}')['command'],'')

    def test_invalid_drafts_are_rejected(self):
        for text in ['not json','[]','{}','{"command":"ps(","explanation":"bad"}',
                     json.dumps({'command':'x\x00','explanation':'bad'}),
                     json.dumps({'command':'x'*8001,'explanation':'large'})]:
            with self.subTest(text=text[:40]), self.assertRaises(ValueError):
                parse_proposal(text)


class SuggestionTests(unittest.IsolatedAsyncioTestCase):
    async def test_completion_is_bound_to_accepted_turn_even_before_start_response(self):
        from volatility_workbench.app import Workbench
        app=object.__new__(Workbench)
        case={'id':'case','thread_id':'thread'}
        app.state={'cases':[case]};app.active=None;app.turns={};app.save=lambda:None
        app.cancel=asyncio.Event();app.case_provider=lambda c:{'model':'synthetic'}
        async def call(method,params):
            await app.agent_event('turn/completed',{'threadId':'thread','turn':{'id':'stale','status':'failed'}})
            await app.agent_event('turn/completed',{'threadId':'thread','turn':{'id':'current','status':'completed'}})
            return {'turn':{'id':'current'}}
        app.agent=SimpleNamespace(call=call)
        await app.codex_turn(case,{},'synthetic')
        self.assertEqual(app.turns,{})
        self.assertEqual(app.turn_bindings,{})

    async def test_stale_completion_cannot_resume_manual_input(self):
        from volatility_workbench.app import Workbench
        app=object.__new__(Workbench)
        case={'id':'case','thread_id':'thread'}
        app.state={'cases':[case]};app.active=None;app.turns={};app.save=lambda:None
        app.cancel=asyncio.Event();app.case_provider=lambda c:{'model':'synthetic'}
        async def call(method,params):return {'turn':{'id':'current'}}
        app.agent=SimpleNamespace(call=call)
        job={};task=asyncio.create_task(app.codex_turn(case,job,'synthetic'))
        for _ in range(20):
            if job.get('turn_id'):break
            await asyncio.sleep(0)
        self.assertEqual(job['turn_id'],'current')
        await app.agent_event('turn/completed',{'threadId':'thread','turn':{'id':'stale','status':'completed'}})
        self.assertFalse(task.done());self.assertFalse(app.turns['thread'].done())
        await app.agent_event('turn/completed',{'threadId':'thread','turn':{'id':'current','status':'completed'}})
        await task

    async def test_effective_codex_home_mcp_servers_are_disabled(self):
        from volatility_workbench.app import Workbench
        app=object.__new__(Workbench);app.case_provider=lambda c:{}
        app.directory=lambda c:Path('/synthetic');app.config=SimpleNamespace(command_timeout=10)
        with tempfile.TemporaryDirectory() as temporary:
            (Path(temporary)/'config.toml').write_text('[mcp_servers.unrelated]\ncommand="synthetic"\n')
            with patch.dict(os.environ,{'CODEX_HOME':temporary}):
                settings=app.thread_config({})
        self.assertFalse(settings['mcp_servers.unrelated.enabled'])

    async def test_stale_turn_messages_do_not_become_current_investigation_results(self):
        from volatility_workbench.app import Workbench
        from support import BackendFixture
        fixture=BackendFixture();fixture.setUp();self.addCleanup(fixture.doCleanups)
        config=fixture.root/'config.json';config.write_text(json.dumps(fixture.config.to_dict()))
        app=Workbench(config,fixture.root/'ui')
        case=app.add([str(fixture.image)])[0];case['thread_id']='thread'
        app.active={'id':'current-job','case_id':case['id'],'turn_id':'current-turn'}
        for method,turn,item in [('item/agentMessage/delta','old-turn','old-delta'),
                                 ('item/completed','old-turn','old-complete'),
                                 ('item/completed','current-turn','current')]:
            await app.agent_event(method,{'threadId':'thread','turnId':turn,'itemId':item,'delta':'old',
                'item':{'id':item,'type':'agentMessage','text':item}})
        self.assertEqual([m.get('job_id') for m in case['messages']],[None,None,'current-job'])

    async def test_compatible_has_no_tools_and_sends_no_case_or_console(self):
        calls=[]
        class Client:
            async def request(self,messages,tools):
                calls.append((messages,tools))
                return {'content':'{"command":"ps()","explanation":"List processes"}'}
        selected={'provider':'compatible','allow_case_content':True,'capability_check':'passed'}
        app=SimpleNamespace(case_provider=lambda c:selected,credentials=object(),compatible_factory=lambda *a:Client())
        result=await suggest(app,{'id':'private-case','images':[{'path':'/private/evidence'}]},'windows','List processes')
        self.assertEqual(result['command'],'ps()')
        self.assertEqual(calls[0][1],[])
        self.assertNotIn('/private/evidence',json.dumps(calls))
        self.assertNotIn('private-case',json.dumps(calls))

    async def test_compatible_permissions_and_tool_response_fail_closed(self):
        class Client:
            async def request(self,*args):return {'tool_calls':[{'function':{'name':'run_plugin'}}]}
        selected={'provider':'compatible','allow_case_content':False}
        app=SimpleNamespace(case_provider=lambda c:selected,credentials=object(),compatible_factory=lambda *a:Client())
        with self.assertRaises(ProviderError):await suggest(app,{},'generic','help')
        selected.update(allow_case_content=True,capability_check='passed')
        with self.assertRaises(ProviderError):await suggest(app,{},'generic','help')

    async def test_codex_uses_isolated_tool_free_thread_and_closes(self):
        calls=[];clients=[]
        class Client:
            def __init__(self,event,request):self.event=event;self.request=request;self.closed=False;clients.append(self)
            async def start(self):pass
            async def close(self):self.closed=True
            async def call(self,method,params,**kwargs):
                calls.append((method,params))
                if method=='thread/start':
                    return {'thread':{'id':'draft'},'sandbox':{'type':'readOnly'},'approvalPolicy':'never'}
                await self.event('item/completed',{'threadId':'unrelated','item':{'type':'agentMessage','text':'wrong'}})
                await self.event('item/completed',{'threadId':'draft','item':{'type':'agentMessage',
                    'text':'{"command":"hh()","explanation":"Available helpers"}'}})
                await self.event('turn/completed',{'threadId':'draft','turn':{'status':'completed'}})
                return {'turn':{'id':'turn'}}
        app=SimpleNamespace(case_provider=lambda c:{'provider':'codex','model':'synthetic'},factory=Client,
            directory=lambda c:Path('/synthetic'),thread_config=lambda c:{'mcp_servers.volatility':{'enabled':True}})
        result=await suggest(app,{},'generic','help')
        self.assertEqual(result['command'],'hh()');self.assertTrue(clients[0].closed)
        params=calls[0][1]
        self.assertTrue(params['ephemeral']);self.assertEqual(params['dynamicTools'],[])
        self.assertFalse(params['config']['mcp_servers.volatility.enabled'])
        self.assertNotIn('mcp_servers.volatility',params['config'])
        with self.assertRaises(Exception):await clients[0].request({'method':'run_plugin'})

    async def test_codex_cancel_closes_its_owned_process(self):
        started=asyncio.Event();closed=asyncio.Event()
        class Client:
            def __init__(self,*args):pass
            async def start(self):pass
            async def close(self):closed.set()
            async def call(self,method,params,**kwargs):
                if method=='thread/start':return {'thread':{'id':'draft'},'sandbox':{'type':'readOnly'},'approvalPolicy':'never'}
                started.set();await asyncio.Future()
        app=SimpleNamespace(case_provider=lambda c:{'provider':'codex','model':'synthetic'},factory=Client,
            directory=lambda c:Path('/synthetic'),thread_config=lambda c:{})
        task=asyncio.create_task(suggest(app,{},'generic','help'))
        await started.wait();task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertTrue(closed.is_set())
