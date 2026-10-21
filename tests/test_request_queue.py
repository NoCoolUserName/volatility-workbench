"""Report request ordering and duplicate protection with synthetic jobs only."""
import asyncio
import json
import unittest
from unittest.mock import patch

import support
from volatility_workbench.app import Workbench


class RequestQueueTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        fixture=support.BackendFixture();fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.fixture=fixture
        config=fixture.root/'config.json';config.write_text(json.dumps(fixture.config.to_dict()))
        self.app=Workbench(config,fixture.root/'ui')
        self.case=self.app.add([str(fixture.image)])[0]
        self.case['readiness']={'status':'Ready','reasons':[]}
        self.case['reports']=[{'id':'base','status':'sealed'}]

    async def asyncTearDown(self):
        if hasattr(self.app,'worker'): await self.app.close()
        self.assertEqual(self.fixture.image.read_text(),'normal')
        self.assertFalse((self.fixture.root/'analysis-count.jsonl').exists())

    async def finished(self,*jobs):
        for _ in range(1000):
            if all(j['status'] not in ('queued','running','stopping') for j in jobs): return
            await asyncio.sleep(.005)
        self.fail('Synthetic queue did not finish')

    async def test_fifo_distinct_prompts_duplicates_idempotency_and_failure_continuation(self):
        entered,release=asyncio.Event(),asyncio.Event();seen=[]
        async def execute(case,job):
            seen.append(job['text'])
            if len(seen)==1: entered.set();await release.wait()
            if job['text']=='fail': raise ValueError('Synthetic report failure')
        with patch.object(self.app,'_execute',side_effect=execute):
            first=self.app.enqueue(self.case['id'],'update','first','one')
            self.assertIs(self.app.enqueue(self.case['id'],'update','first','one'),first)
            with self.assertRaisesRegex(ValueError,'different submission'):
                self.app.enqueue(self.case['id'],'update','changed','one')
            with self.assertRaisesRegex(ValueError,'identical'):
                self.app.enqueue(self.case['id'],'update','  first\r\n','duplicate')
            second=self.app.enqueue(self.case['id'],'update','fail','two')
            third=self.app.enqueue(self.case['id'],'update','third','three')
            await self.app.start();await entered.wait()
            self.assertEqual(seen,['first']);self.assertEqual(third['status'],'queued')
            with self.assertRaisesRegex(ValueError,'identical'):
                self.app.enqueue(self.case['id'],'update','first','active-duplicate')
            release.set();await self.finished(first,second,third)
            self.assertEqual(seen,['first','fail','third'])
            self.assertEqual([j['status'] for j in (first,second,third)],['completed','failed','completed'])
            repeated=self.app.enqueue(self.case['id'],'update','first','new-deliberate-request')
            await self.finished(repeated);self.assertEqual(seen[-1],'first')

    async def test_rerun_is_original_prompt_and_does_not_duplicate_pending_retry(self):
        original={'id':'failed','request_id':'old','case_id':self.case['id'],'kind':'update',
                  'text':'original prompt','status':'failed'}
        self.app.state['jobs'].append(original)
        retry=self.app.enqueue(self.case['id'],'update','original prompt','retry',retry_of='failed')
        self.assertIs(self.app.enqueue(self.case['id'],'update','original prompt','another-tab',retry_of='failed'),retry)
        with self.assertRaisesRegex(ValueError,'identical'):
            self.app.enqueue(self.case['id'],'update','original prompt','same-prompt')
        with self.assertRaisesRegex(ValueError,'Rerun must'):
            self.app.enqueue(self.case['id'],'update','edited prompt','bad-retry',retry_of='failed')
        followup=self.app.enqueue(self.case['id'],'update','new prompt','followup')
        self.assertEqual([j['text'] for j in self.app.state['jobs'][-2:]],['original prompt','new prompt'])
        self.assertEqual(followup['status'],'queued')

    async def test_queued_update_without_successful_base_fails_before_model_or_collection(self):
        self.case['reports']=[]
        report=self.app.enqueue(self.case['id'],'report','first generation','generation')
        update=self.app.enqueue(self.case['id'],'update','follow up','update')
        question=self.app.enqueue(self.case['id'],'question','next question','question')
        execute_original=self.app._execute
        async def execute(case,job):
            if job['kind']=='report': raise ValueError('Synthetic generation failed')
            if job['kind']=='update': return await execute_original(case,job)
        with patch.object(self.app,'_execute',side_effect=execute), patch.object(self.app,'ensure_thread',side_effect=AssertionError('No model allowed')):
            await self.app.start();await self.finished(report,update,question)
        self.assertEqual(report['status'],'failed');self.assertEqual(update['status'],'failed')
        self.assertIn('no successfully sealed report',update['error'])
        self.assertEqual(question['status'],'completed');self.assertEqual(self.case['reports'],[])

    async def test_explicit_delete_runs_between_jobs_and_stop_cancels_followups(self):
        old={'id':'old','status':'incomplete'};self.case['reports'].append(old)
        folder=self.app.directory(self.case)/'reports/old';folder.mkdir(parents=True)
        (folder/'report.md').write_text('Synthetic unfinished report')
        entered,release=asyncio.Event(),asyncio.Event()
        async def execute(case,job):
            if job['text']=='first': entered.set();await release.wait()
            else: self.assertFalse(folder.exists(),'Deferred cleanup finishes before the next report reads its case')
        with patch.object(self.app,'_execute',side_effect=execute):
            first=self.app.enqueue(self.case['id'],'update','first','first')
            second=self.app.enqueue(self.case['id'],'update','second','second')
            await self.app.start();await entered.wait()
            result=await self.app.remove_report(self.case['id'],'old','delete')
            self.assertTrue(result['queued']);self.assertTrue(folder.exists());self.assertIn('delete_requested_at',old)
            release.set();await self.finished(first,second)
            self.assertTrue(old['deleted_at']);self.assertEqual(len(self.app.state['recycle_bin']),1)
        entered.clear();release.clear()
        with patch.object(self.app,'_execute',side_effect=execute):
            running=self.app.enqueue(self.case['id'],'update','first','stop-first')
            queued=self.app.enqueue(self.case['id'],'update','second','stop-second')
            await entered.wait();await self.app.stop();await self.finished(running,queued)
            self.assertEqual(running['status'],'incomplete');self.assertEqual(queued['status'],'cancelled')
