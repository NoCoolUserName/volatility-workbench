"""Only explicit tool events appear in the read-only live report console."""
import json
import unittest
from unittest.mock import patch

from volatility_workbench import live_console
from volatility_workbench.app import Workbench
from support import BackendFixture
from test_ui import FakeCodex


def event(ident, kind, detail, job_id='job'):
    return {'id':str(ident),'time':'2026-10-18T12:00:00Z','job_id':job_id,'kind':kind,'detail':detail}


class ConsoleTests(unittest.TestCase):
    def test_only_current_job_and_turn_tool_events_are_exposed(self):
        job={'id':'job','case_id':'case','kind':'update','turn_id':'turn'}
        events=[event(1,'item/completed',{'type':'reasoning','text':'PRIVATE REASONING'}),
                event(2,'item/completed',{'type':'userMessage','text':'PRIVATE PROMPT'}),
                event(3,'tool_progress',{'message':'wrong job'},'other'),
                event(4,'tool_progress',{'message':'wrong turn','turn_id':'other'}),
                event(5,'item/started',{'type':'mcpToolCall','server':'volatility','tool':'run_plugin','arguments':{'plugin':'synthetic.Plugin'}}),
                event(6,'tool_progress',{'message':'Scanning synthetic fixture','turn_id':'turn'}),
                event(7,'item/completed',{'type':'mcpToolCall','server':'volatility','tool':'run_plugin','status':'completed',
                    'result':{'content':[{'type':'text','text':'<script>untrusted fixture</script>'}]}})]
        view=live_console.snapshot(job,events)
        self.assertEqual([e['id'] for e in view['entries']],['5','6','7'])
        text=json.dumps(view)
        self.assertNotIn('PRIVATE',text);self.assertNotIn('wrong',text)
        self.assertIn('<script>untrusted fixture</script>',text)
        self.assertIsNone(live_console.snapshot({**job,'kind':'question'},events))

    def test_output_is_plain_bounded_and_recent(self):
        self.assertEqual(live_console.excerpt('\x1b[31mred\x1b[0m\x00\x1b]0;title\x07'),'red')
        output=live_console.tool_output({'content':[{'type':'image','data':'DO NOT SHOW BASE64'}],
                                         'structuredContent':{'status':'success'}})
        self.assertEqual(output,{'status':'success'})
        job={'id':'job','case_id':'case','kind':'report'}
        events=[event(i,'local_tool_completed',{'tool':'synthetic','output':'x'*20000}) for i in range(140)]
        view=live_console.snapshot(job,events)
        self.assertLessEqual(len(view['entries']),live_console.MAX_ENTRIES)
        self.assertLessEqual(sum(len(e['text']) for e in view['entries']),live_console.MAX_CHARS)
        self.assertEqual(view['entries'][-1]['id'],'139')
        self.assertGreater(view['earlier_entries'],0)
        self.assertIn('Console excerpt',view['entries'][-1]['text'])


class ConsoleEventTests(unittest.IsolatedAsyncioTestCase):
    def saved_app(self):
        fixture=BackendFixture();fixture.setUp();self.addCleanup(fixture.doCleanups)
        config=fixture.root/'config.json';config.write_text(json.dumps(fixture.config.to_dict()))
        app=Workbench(config,fixture.root/'ui',codex_factory=FakeCodex)
        case=app.add([str(fixture.image)])[0]
        return app,case,config,fixture

    async def test_finished_console_survives_restart_and_activity_window_rollover(self):
        app,case,config,fixture=self.saved_app()
        job={'id':'job','case_id':case['id'],'kind':'update','status':'completed','finished_at':'2026-10-18T12:00:00Z'}
        app.state['jobs'].append(job)
        records=[event(1,'local_tool_completed',{'tool':'synthetic','output':'Saved plugin output'}),
                 event(2,'job_completed',{})]+[event(i,'tool_progress',{'message':'Other request'},'other') for i in range(3,180)]
        log=app.directory(case)/'activity.jsonl';log.write_text(''.join(json.dumps(r)+'\n' for r in records));original=log.read_bytes()
        case['activity']=records[-150:];app.save()
        restarted=Workbench(config,fixture.root/'ui',codex_factory=FakeCodex)
        view=restarted.report_console(restarted.case(case['id']),'job')
        self.assertEqual(view['status'],'completed');self.assertIn('Saved plugin output',json.dumps(view))
        self.assertNotIn('Other request',json.dumps(view));self.assertEqual(view['warnings'],[])
        self.assertEqual(log.read_bytes(),original)
        with patch.object(live_console,'saved_snapshot',side_effect=AssertionError('Cached view should not reread log')):
            self.assertEqual(restarted.report_console(restarted.case(case['id']),'job'),view)
        with self.assertRaises(ValueError):restarted.report_console(case,'another-job')
        with self.assertRaises(ValueError):restarted.report_console({**case,'id':'different-case'},'job')
        job['status']='running'
        with self.assertRaises(ValueError):app.report_console(case,'job')

    async def test_saved_console_bounds_corrupt_records_and_missing_log(self):
        app,case,_,_=self.saved_app()
        job={'id':'job','case_id':case['id'],'kind':'report','status':'failed'};app.state['jobs'].append(job)
        log=app.directory(case)/'activity.jsonl'
        records=[event(i,'local_tool_completed',{'tool':'synthetic','output':'x'*12000}) for i in range(120)]
        log.write_text('invalid json\n'+''.join(json.dumps(r)+'\n' for r in records))
        view=app.report_console(case,'job')
        self.assertGreater(view['earlier_entries'],0);self.assertTrue(view['warnings'])
        self.assertLessEqual(sum(len(e['text']) for e in view['entries']),live_console.MAX_CHARS)
        with patch.object(live_console,'MAX_LOG_RECORD',20):
            self.assertIn('oversized',json.dumps(live_console.saved_snapshot(job,log)))
        log.unlink();app.console_cache.clear();case['activity']=[event(9,'tool_progress',{'message':'Recent fallback'})]
        self.assertIn('Recent fallback',json.dumps(app.report_console(case,'job')))
        self.assertTrue(app.report_console(case,'job')['warnings'])

    async def test_actual_tool_progress_is_tagged_and_available_to_polling(self):
        fixture=BackendFixture();fixture.setUp();self.addCleanup(fixture.doCleanups)
        config=fixture.root/'config.json';config.write_text(json.dumps(fixture.config.to_dict()))
        app=Workbench(config,fixture.root/'ui',codex_factory=FakeCodex)
        case=app.add([str(fixture.image)])[0];case['thread_id']='synthetic-thread'
        job={'id':'job','case_id':case['id'],'kind':'update','turn_id':'turn','status':'running'}
        app.active=job;app.state['jobs'].append(job)
        await app.agent_event('item/started',{'threadId':case['thread_id'],'turnId':'turn',
            'item':{'id':'call','type':'mcpToolCall','server':'volatility','tool':'run_plugin','arguments':{}}})
        await app.agent_event('item/mcpToolCall/progress',{'threadId':case['thread_id'],'turnId':'turn','message':'Synthetic progress'})
        await app.agent_event('item/mcpToolCall/progress',{'threadId':case['thread_id'],'turnId':'stale','message':'STALE'})
        view=app.snapshot()['live_console']
        self.assertEqual(len(view['entries']),2)
        self.assertIn('Synthetic progress',view['entries'][-1]['text'])
        self.assertNotIn('STALE',json.dumps(view))
