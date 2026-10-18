"""Provider-shaped usage fixtures; no model requests or forensic execution."""
import asyncio
import copy
import json
from types import SimpleNamespace
import unittest

from volatility_workbench import generation
from volatility_workbench.app import Workbench


class GenerationTests(unittest.TestCase):
    def test_counter_differences_duplicates_reset_and_unknown_baseline(self):
        g=generation.begin('codex',{'model':'synthetic','reasoningEffort':'high'})
        generation.usage(g,{'totalTokens':9000,'inputTokens':8000},None)
        self.assertIsNone(g['token_usage']['total_tokens'])
        self.assertIn('case thread',generation.summary(g))
        for _ in range(2):generation.usage(g,{'totalTokens':9000,'inputTokens':8000},{'totalTokens':7000,'inputTokens':6500})
        self.assertEqual(g['token_usage']['total_tokens'],2000)
        self.assertEqual(g['token_usage']['breakdown']['inputTokens'],1500)
        generation.usage(g,{'totalTokens':100},{'totalTokens':7000})
        self.assertEqual(g['token_usage']['status'],'unavailable')
        for bad in ({'totalTokens':True},{'totalTokens':-1},{'totalTokens':'12'}):
            self.assertIsNone(generation.token_counts(bad))

    def test_portable_metadata_is_idempotent_and_never_invents_historical_settings(self):
        text='# Synthetic report\n\n## Executive summary\nFixture.\n'
        g=generation.begin('codex',{'model':'synthetic','reasoningEffort':'low'})
        prepared=generation.markdown(text,g)
        self.assertEqual(prepared,generation.markdown(prepared,g))
        self.assertIn('`synthetic`',prepared)
        self.assertIn('token usage not reported',prepared)
        self.assertIn('not recorded for this report',generation.summary(None))
        self.assertIsNone(generation.begin('codex',{'model':'bad`<script>'})['model'])
        requested=generation.begin('compatible',{'model':'synthetic','reasoning_effort':'xhigh'})
        self.assertEqual(requested['reasoning_effort'],'xhigh')
        self.assertIn('requested effort; effective effort not reported',generation.summary(requested))


class GenerationEventTests(unittest.IsolatedAsyncioTestCase):
    async def test_case_turn_isolation_restart_snapshot_and_no_late_sealed_mutation(self):
        app=object.__new__(Workbench)
        case={'id':'case-a','thread_id':'thread-a'}
        app.state={'cases':[case]};app.save=lambda:None
        future=asyncio.get_running_loop().create_future();app.turns={'thread-a':future}
        app.active={'case_id':'case-a','turn_id':'turn-a','generation':generation.begin('codex',{'model':'synthetic'}),
                    'token_usage_baseline':{'totalTokens':100}}
        def event(thread='thread-a',turn='turn-a',total=150):
            return {'threadId':thread,'turnId':turn,'tokenUsage':{'total':{'totalTokens':total}}}
        await app.agent_event('thread/tokenUsage/updated',event(thread='other'))
        await app.agent_event('thread/tokenUsage/updated',event(turn='stale',total=10000))
        self.assertNotIn('token_usage_snapshot',case)
        await app.agent_event('thread/tokenUsage/updated',event())
        self.assertEqual(app.active['generation']['token_usage']['total_tokens'],50)
        await app.agent_event('model/rerouted',{'threadId':'thread-a','turnId':'turn-a','toModel':'synthetic-fallback'})
        self.assertEqual(app.active['generation']['models'],['synthetic','synthetic-fallback'])
        await app.agent_event('turn/completed',{'threadId':'thread-a','turn':{'id':'turn-a','status':'completed'}})
        persisted=json.loads(json.dumps(case))
        self.assertEqual(persisted['token_usage_snapshot']['total'],{'totalTokens':150})
        self.assertTrue(persisted['token_usage_snapshot']['complete'])
        before=copy.deepcopy(app.active['generation'])
        await app.agent_event('thread/tokenUsage/updated',event(total=200))
        self.assertEqual(app.active['generation'],before)

    async def test_missing_usage_turn_invalidates_next_baseline(self):
        app=object.__new__(Workbench)
        case={'id':'case-a','thread_id':'thread-a','token_usage_snapshot':{
            'thread_id':'thread-a','turn_id':'prior','total':{'totalTokens':100},'complete':True}}
        app.state={'cases':[case]};app.save=lambda:None
        app.turns={};app.cancel=asyncio.Event();app.active=None
        async def call(method,params):
            # Must already be invalid on disk before an accepted turn can crash.
            self.assertFalse(case['token_usage_snapshot']['complete'])
            await app.agent_event('turn/completed',{'threadId':'thread-a','turn':{'id':'new','status':'completed'}})
            return {'turn':{'id':'new'}}
        app.agent=SimpleNamespace(call=call)
        job={}
        await app.codex_turn(case,job,'fixture')
        self.assertEqual(job['token_usage_baseline'],{'totalTokens':100})
        self.assertFalse(case['token_usage_snapshot']['complete'])
        again={}
        await app.codex_turn(case,again,'fixture')
        self.assertIsNone(again['token_usage_baseline'])

    async def test_resumed_legacy_thread_is_not_treated_as_zero_usage(self):
        # ensure_thread must not invent a zero baseline for an existing case.
        app=object.__new__(Workbench)
        app.case_provider=lambda case:{'provider':'codex','model':'synthetic','reasoning_effort':'medium'}
        async def connect(provider):pass
        async def call(method,params,timeout):
            self.assertEqual(method,'thread/resume')
            return {'model':'synthetic','reasoningEffort':'medium', 'approvalPolicy':'on-request',
                    'approvalsReviewer':'user','sandbox':{'type':'readOnly'}}
        app.connect=connect;app.agent=SimpleNamespace(call=call);app.loaded_threads=set()
        app.investigation_instructions=lambda:'';app.thread_config=lambda case:{}
        app.directory=lambda case:__import__('pathlib').Path('/tmp')
        app.save=lambda:None
        case={'thread_id':'legacy'}
        await app.ensure_thread(case)
        self.assertNotIn('token_usage_snapshot',case)
        self.assertEqual(case['agent_settings']['reasoningEffort'],'medium')
