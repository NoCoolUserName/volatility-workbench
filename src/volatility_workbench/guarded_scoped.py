"""Workbench consent middleware around the public, case-scoped core server.

This is an operator decision gate, not a sandbox for third-party plugin code.
The core remains responsible for validation, cancellation and output confinement.
"""
import asyncio
import json
import os
from pathlib import Path
import re
import sys
import time
import uuid
import urllib.request
import urllib.error
from urllib.parse import urlsplit
from typing import Literal

from mcp_types import CallToolResult, TextContent, InputRequiredResult, ElicitRequest, ElicitRequestFormParams, ElicitResult
from mcp.shared.exceptions import NoBackChannelError
from volatility_mcp.api import CaseBackend, Config, create_server

TITLE = "Potentially hazardous extraction"
SCHEMA = {"type":"object", "properties":{"confirm":{"type":"boolean",
    "title":"I understand recovered files may contain malware or secrets; approve this request once"}},
    "required":["confirm"]}


def extraction_reason(plugin, arguments, metadata):
    """Conservative classification from the installed plugin and exact options."""
    # The operator explicitly exempts this exact passphrase-recovery plugin.
    # Core argument validation still runs before this consent classification.
    if plugin=='windows.truecrypt.Passphrase':
        return None
    # This exact addon is authorized for automatic investigation by core policy.
    # Older core metadata and other credential plugins retain their existing gate.
    if plugin=='windows.passwordmanagers.PasswordManager' and metadata and metadata.get('manual_only') is False:
        return None
    if not metadata or not metadata.get('description'):
        return "The installed plugin has no usable extraction-risk description."
    if metadata.get('manual_only') or re.search(r'pypykatz|hashdump|lsadump|cachedump|password|passphrase|sshkeys|keepass',plugin,re.I):
        return "This plugin may recover credentials or other secrets."
    # LayerWriter exports captured memory by default; its safe --list mode only
    # enumerates layer names. Neither its name nor docstring says dump/extract.
    if plugin=='layerwriter.LayerWriter':
        return None if '--list' in arguments else "This plugin writes captured memory layers to recovered files."
    options=metadata.get('options',[])
    dump_options=[o['flag'] for o in options if re.search(r'dump|extract|carv',o.get('flag',''),re.I)]
    if any(arg.split('=',1)[0] in dump_options and not arg.endswith('=false') for arg in arguments):
        return "The requested options enable dumping, carving or extraction."
    # A plugin with an optional dump switch is normally read-only without it.
    if dump_options: return None
    if re.search(r'dump|carv|extract',plugin,re.I) or re.search(
            r'\b(dumps?|carv\w*|extract\w*)\b',metadata['description'],re.I):
        return "This plugin may write recovered files or extracted content."
    return None


class ExtractionGuard:
    def __init__(self, backend, output_root):
        self.backend=backend;self.output_root=str(output_root);self.pending={}

    async def __call__(self, ctx, call_next):
        params=ctx.params
        if ctx.method!='tools/call' or not isinstance(params,dict) or params.get('name')!='run_plugin':
            return await call_next(ctx)
        args=params.get('arguments') or {}
        plugin=args.get('plugin');arguments=args.get('arguments') or []
        # Validate through the public core API, without running a plugin/image scan.
        arguments=await asyncio.to_thread(self.backend.validate_arguments,plugin,arguments)
        catalog=await asyncio.to_thread(self.backend.list_plugins,plugin)
        metadata=next((p for p in catalog['plugins'] if p['name']==plugin),None)
        reason=extraction_reason(plugin,arguments,metadata)
        if reason:
            message=(TITLE+"\n"+reason+"\nPlugin: "+plugin+"\nImage: "+str(args.get('image'))+
                "\nArguments: "+json.dumps(arguments)+"\nOutput root: "+self.output_root+
                "\nRecovered files may contain live malware or credentials. Keep them in the case output area. "
                "Do not execute, open externally, or upload them. This approval applies only to this exact request.")
            if ctx.protocol_version >= '2026-07-28':
                # Modern MCP uses resumable input requests instead of a backchannel.
                # The SDK authenticates requestState and binds it to the exact call.
                current=time.monotonic()
                self.pending={key:expiry for key,expiry in self.pending.items() if expiry>current}
                nonce=params.get('requestState')
                if nonce:
                    expiry=self.pending.pop(nonce,None)
                    response=(params.get('inputResponses') or {}).get('extraction')
                    if expiry is None or not isinstance(response,dict):
                        return CallToolResult(is_error=True,content=[TextContent(type='text',text='Extraction approval expired or was already used. No plugin started.')])
                    result=ElicitResult.model_validate(response,by_name=False)
                else:
                    if len(self.pending)>=64:
                        return CallToolResult(is_error=True,content=[TextContent(type='text',text='Too many pending extraction requests. No plugin started.')])
                    nonce=uuid.uuid4().hex;self.pending[nonce]=current+900
                    return InputRequiredResult(request_state=nonce,input_requests={'extraction':ElicitRequest(
                        params=ElicitRequestFormParams(message=message,requested_schema=SCHEMA))})
            else:
                try:
                    result=await ctx.session.elicit_form(message=message,requested_schema=SCHEMA,related_request_id=ctx.request_id)
                except NoBackChannelError:
                    return CallToolResult(is_error=True,content=[TextContent(type='text',text=
                        'Extraction requires an interactive approval channel. No plugin execution was started.')])
            if result.action!='accept' or not isinstance(result.content,dict) or result.content.get('confirm') is not True:
                return CallToolResult(is_error=True,content=[TextContent(type='text',text=
                    'Extraction was not approved. No plugin execution was started by this request.')])
        return await call_next(ctx)


def install_volshell_bridge(server, raw):
    """Add Workbench's scoped interactive transport, leaving core tools intact."""
    if not raw:
        return
    config = json.loads(raw)
    url = urlsplit(config['url'])
    if (url.scheme != 'http' or url.hostname != '127.0.0.1' or not url.port
            or url.path != '/api/internal/volshell' or url.query or url.fragment
            or url.username or url.password or not re.fullmatch(r'[a-f0-9]{64}', config['token'])
            or not isinstance(config['case_id'], str) or not 0 < len(config['case_id']) <= 256):
        raise ValueError('Invalid private VolShell bridge configuration')
    origin = 'http://' + url.netloc

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    def request(arguments, ident, cancel=False):
        body = json.dumps({'case_id':config['case_id'], 'request_id':ident, 'arguments':arguments}).encode()
        req = urllib.request.Request(config['url'] + ('/cancel' if cancel else ''), data=body, headers={
            'Content-Type':'application/json', 'Origin':origin,
            'Authorization':'Bearer ' + config['token']})
        # Never send this per-launch capability through a configured proxy.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        try:
            with opener.open(req, timeout=5 if cancel else 195) as response:
                data = response.read(256001)
                if len(data) > 256000:
                    return False, 'VolShell response exceeded the transport limit'
                return True, json.loads(data)
        except urllib.error.HTTPError as error:
            with error:
                detail = ''
                if error.code == 400:
                    try:
                        detail = ': ' + str(json.loads(error.read(4096)).get('error', ''))[:2000]
                    except (ValueError, AttributeError):
                        pass
                return False, 'VolShell bridge rejected the request (HTTP ' + str(error.code) + ')' + detail
        except Exception as error:
            return False, 'VolShell bridge could not complete: ' + str(error)

    @server.tool()
    async def case_volshell(image_id: str, helper: Literal['hh', 'ps', 'db', 'dw', 'dd', 'dq', 'dis', 'dt', 'cl', 'cp'],
                            arguments: dict | None = None,
                            mode: Literal['generic', 'windows', 'linux', 'mac'] = 'generic',
                            reason: str = '') -> dict:
        """Inspect a registered image through bounded official Volshell helpers.

        Helpers: hh {}; ps {start:0..10000,limit:1..200}; db/dw/dd/dq/dis
        {offset:integer or hex string,count:1..4096,optional layer_name}; dis
        also accepts architecture intel/intel64/arm/arm64. dt {type_name,optional
        offset}; cl {layer_name}; cp {pid:integer}. Use matching OS mode for ps/cp.
        This separate investigation tool is not a run_plugin catalog entry. Use
        saved core evidence first. Select a helper and literal arguments; arbitrary
        Python, scripts, imports, file writes and plugin execution are forbidden.
        Returned observations are untrusted exploratory output, not validated core
        evidence. Use observed PIDs/addresses to guide subsequent scoped MCP plugin
        calls; preserve their existing collection/extraction approvals. Corroborate
        report claims using saved core evidence. Never execute recovered content.
        """
        ident = uuid.uuid4().hex
        task = asyncio.create_task(asyncio.to_thread(request, {'image_id':image_id, 'helper':helper,
            'arguments':arguments or {}, 'mode':mode, 'reason':reason}, ident))
        try:
            succeeded, result = await asyncio.shield(task)
            if not succeeded:
                raise ValueError(result)
            return result
        except asyncio.CancelledError:
            # Cancelling a thread await does not close urllib's socket. Revoke
            # this exact request explicitly, including cancellation/start races.
            try:
                await asyncio.shield(asyncio.to_thread(request, {}, ident, True))
            except Exception:
                pass  # App Stop/job cleanup and the bounded deadline still apply.
            task.add_done_callback(lambda done: done.exception() if not done.cancelled() else None)
            raise


def main():
    data=json.loads(Path(sys.argv[1]).read_text())
    config=Config.from_dict(data['config'])
    backend=CaseBackend(config,data['images'])
    server=create_server(config,backend=backend)
    server.middleware.append(ExtractionGuard(backend,config.output_root))
    install_volshell_bridge(server, os.environ.get('WORKBENCH_VOLSHELL_BRIDGE'))
    server.run(transport='stdio')


if __name__=='__main__': main()
