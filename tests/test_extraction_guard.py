"""Consent through real SDK, using dummy tools and no forensic execution."""
import unittest
from pathlib import Path
import sys
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from mcp_types import ElicitResult
from volatility_workbench import guarded_scoped
from volatility_workbench.guarded_scoped import extraction_reason
from mcp.shared.exceptions import MCPError


class GuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_decisions_gate_exact_request_and_never_preapprove_next_call(self):
        for mode in ('auto','legacy'):
            runs=[];prompts=[];answers=iter([
                ElicitResult(action='decline'),ElicitResult(action='accept',content={'confirm':False}),
                ElicitResult(action='accept',content={'confirm':True}),ElicitResult(action='cancel')])
            server=StdioServerParameters(command=sys.executable,args=[str(Path(__file__).parent/'fixtures/extraction_server.py')],env={'PYTHONPATH':str(Path(guarded_scoped.__file__).parents[1])})
            async def elicit(context,params):
                prompts.append(params.message);return next(answers)
            async with Client(server,mode=mode,elicitation_callback=elicit) as client:
                params={'image':'fixture.raw','plugin':'windows.dumpfiles.DumpFiles','arguments':['--filter','synthetic']}
                for failed in (True,True,False,True):
                    result=await client.call_tool('run_plugin',params)
                    self.assertEqual(result.is_error,failed)
                    if not failed:runs.append(result)
            self.assertEqual(len(runs),1);self.assertEqual(len(prompts),4)
            self.assertIn('fixture.raw',prompts[0]);self.assertIn('/synthetic/outputs',prompts[0]);self.assertIn('malware',prompts[0])

    async def test_read_only_calls_do_not_prompt_and_missing_callback_fails_closed(self):
        server=StdioServerParameters(command=sys.executable,args=[str(Path(__file__).parent/'fixtures/extraction_server.py')],env={'PYTHONPATH':str(Path(guarded_scoped.__file__).parents[1])})
        async with Client(server) as client:
            self.assertFalse((await client.call_tool('query_output',{})).is_error)
            self.assertFalse((await client.call_tool('run_plugin',{'image':'fixture','plugin':'windows.pslist.PsList'})).is_error)
            result=await client.session.call_tool('run_plugin',{'image':'fixture','plugin':'windows.pslist.PsList','arguments':['--dump']},allow_input_required=True)
            self.assertEqual(result.result_type,'input_required')


    async def test_passwordmanager_is_automatic_but_sshkeys_still_requires_approval(self):
        server=StdioServerParameters(command=sys.executable,args=[str(Path(__file__).parent/'fixtures/extraction_server.py')],env={'PYTHONPATH':str(Path(guarded_scoped.__file__).parents[1])})
        for mode in ('auto','legacy'):
            async def unexpected_prompt(context,params):
                self.fail('Authorized PasswordManager should not request extraction approval')
            async with Client(server,mode=mode,elicitation_callback=unexpected_prompt) as client:
                result=await client.call_tool('run_plugin',{'image':'fixture','plugin':'windows.passwordmanagers.PasswordManager','arguments':['--pid','123']})
                self.assertFalse(result.is_error)
        async with Client(server) as client:
            result=await client.session.call_tool('run_plugin',{'image':'fixture','plugin':'linux.openssh_sessionkeys.SSHKeys','arguments':['--pid','123','--address','0x1000']},allow_input_required=True)
            self.assertEqual(result.result_type,'input_required')

    async def test_modern_approval_cannot_be_replayed_or_moved_to_another_call(self):
        server=StdioServerParameters(command=sys.executable,args=[str(Path(__file__).parent/'fixtures/extraction_server.py')],env={'PYTHONPATH':str(Path(guarded_scoped.__file__).parents[1])})
        async with Client(server) as client:
            args={'image':'fixture','plugin':'windows.dumpfiles.DumpFiles'}
            request=await client.session.call_tool('run_plugin',args,allow_input_required=True)
            response={'extraction':ElicitResult(action='accept',content={'confirm':True})}
            with self.assertRaises(MCPError):
                await client.session.call_tool('run_plugin',{**args,'image':'different'},request_state=request.request_state,input_responses=response,allow_input_required=True)

            result=await client.session.call_tool('run_plugin',args,request_state=request.request_state,input_responses=response,allow_input_required=True)
            self.assertFalse(result.is_error)
            replay=await client.session.call_tool('run_plugin',args,request_state=request.request_state,input_responses=response,allow_input_required=True)
            self.assertTrue(replay.is_error)

    def test_conservative_classification(self):
        normal={'description':'Lists modules','options':[{'flag':'--dump'}]}
        self.assertIsNone(extraction_reason('windows.modules.Modules',[],normal))
        self.assertTrue(extraction_reason('windows.modules.Modules',['--dump'],normal))
        self.assertTrue(extraction_reason('vol_pypykatz.pypykatz',[],{'description':'Credentials'}))
        self.assertIsNone(extraction_reason('windows.truecrypt.Passphrase',[],{'description':'TrueCrypt Cached Passphrase Finder'}))
        self.assertIsNone(extraction_reason('windows.truecrypt.Passphrase',[],None))
        self.assertTrue(extraction_reason('synthetic.passphrase.Recover',[],{'description':'Recovers a passphrase'}))
        password='windows.passwordmanagers.PasswordManager'
        self.assertIsNone(extraction_reason(password,['--pid','123'],{'description':'Fragments','manual_only':False}))
        self.assertTrue(extraction_reason(password,[],{'description':'Fragments','manual_only':True}))
        self.assertTrue(extraction_reason(password,[],None))
        self.assertTrue(extraction_reason('synthetic.password.Recover',[],{'description':'Secrets','manual_only':False}))
        layer={'description':'Runs the automagics and writes out the primary layer produced by the stacker.',
               'options':[{'flag':'--list'},{'flag':'--layers'},{'flag':'--block-size'}]}
        self.assertTrue(extraction_reason('layerwriter.LayerWriter',[],layer))
        self.assertTrue(extraction_reason('layerwriter.LayerWriter',['--layers','memory_layer'],layer))
        self.assertIsNone(extraction_reason('layerwriter.LayerWriter',['--list'],layer))
        self.assertTrue(extraction_reason('unknown.Plugin',[],None))
        self.assertTrue(extraction_reason('windows.recovery.Plugin',[],{'description':'Extracts cached files'}))
