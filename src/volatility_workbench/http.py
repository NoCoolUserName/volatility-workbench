"""Loopback HTTP transport with per-launch capability, origin checks and no uploads."""
from __future__ import annotations
import argparse
import asyncio
import fcntl
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import secrets
import select
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit, parse_qs
import webbrowser
from .app import Workbench
from .storage import atomic_json, private_dir, safe_file
from volatility_mcp.api import load_config
import volatility_mcp
from .compatibility import require_core


def open_browser(url):
    """Use the registered macOS browser without AppleScript automation."""
    try:
        if sys.platform == 'darwin':
            opened = subprocess.run(['/usr/bin/open', url], capture_output=True, timeout=15).returncode == 0
        else:
            opened = webbrowser.open(url)
    except (OSError, subprocess.TimeoutExpired, webbrowser.Error):
        opened = False
    if not opened:
        print('Could not open the browser automatically. Open the private launch URL printed above in your browser. Workbench remains available.', file=sys.stderr)
    return opened


def runtime_fingerprint():
    """Identify installed server/UI code without reading private case data."""
    digest=hashlib.sha256()
    for root in (Path(__file__).resolve().parent, Path(volatility_mcp.__file__).resolve().parent):
        digest.update(root.name.encode())
        for path in sorted(root.rglob('*')):
            if path.is_file() and path.suffix in ('.py','.js','.css','.html','.md'):
                digest.update(str(path.relative_to(root)).encode())
                digest.update(b'\0'+path.read_bytes()+b'\0')
    return digest.hexdigest()


def check_running_version(session, fingerprint):
    if session.get('runtime_fingerprint') != fingerprint:
        raise ValueError('An older Workbench is still running. Stop it with Ctrl-C in its Terminal window, then launch again. Refreshing the browser does not load updated server code. Completed case artifacts are preserved.')


class Server(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, app, port, loop):
        self.app, self.loop = app, loop
        self.token = secrets.token_urlsafe(32)
        self.stream_slots = threading.BoundedSemaphore(8)
        self.streams_stopping = threading.Event()
        self.bridge_lock = threading.Lock()
        self.bridge_requests = {}
        self.bridge_cancelled = {}
        super().__init__(('127.0.0.1', port), Handler)
        self.authority = '127.0.0.1:' + str(self.server_port)
        self.origin = 'http://' + self.authority
        app.volshell_bridge_origin = self.origin
        app.volshell_bridge_secret = secrets.token_bytes(32)

    def server_close(self):
        self.streams_stopping.set()
        super().server_close()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # URLs, paths, questions and evidence must not enter access logs.

    def send(self, status, value, content_type='application/json', cookie=False):
        data = json.dumps(value).encode() if content_type=='application/json' else value
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        if cookie:self.send_header('Set-Cookie','volatility_ui='+self.server.token+'; HttpOnly; SameSite=Strict; Path=/')
        self.end_headers()
        self.wfile.write(data)

    def guard(self, action=False):
        if self.headers.get('Host') != self.server.authority:
            raise PermissionError('Unrecognized Host')
        origin=self.headers.get('Origin')
        if origin and origin!=self.server.origin:
            raise PermissionError('Unrecognized browser origin')
        if action and origin!=self.server.origin:
            raise PermissionError('Actions require the local application Origin')
        if self.headers.get('Sec-Fetch-Site') in ('cross-site','same-site'):
            raise PermissionError('Cross-site requests are forbidden')

    def authenticated(self):
        cookie=SimpleCookie()
        cookie.load(self.headers.get('Cookie',''))
        actual=cookie.get('volatility_ui')
        if not actual or not secrets.compare_digest(actual.value,self.server.token):
            raise PermissionError('Open the private launch URL printed in Terminal to connect')

    def invoke(self, coro, timeout=200):
        return asyncio.run_coroutine_threadsafe(coro,self.server.loop).result(timeout)

    async def dispatch(self,path,body):
        app=self.server.app
        if path=='/api/reports/purge-hidden':return await app.purge_hidden_reports(body['case_id'])
        if path=='/api/reports/restore':return await app.restore_recycled_report(body['case_id'],body['report_id'])
        if path=='/api/reports/purge-recycled':return await app.purge_recycled_report(body['case_id'],body['report_id'])
        if path.startswith('/api/settings/'):
            return await app.settings_manager.dispatch(path,body)
        if path=='/api/volshell/start':
            return await app.start_volshell(body['case_id'],body['image_id'],body.get('mode','generic'))
        if path=='/api/volshell/input':
            return await app.input_volshell(body['case_id'],body['session_id'],body['text'])
        if path=='/api/volshell/interrupt':
            return await app.volshell.interrupt(body['case_id'],body['session_id'])
        if path=='/api/volshell/close':
            return await app.close_volshell(body['case_id'],body['session_id'])
        if path=='/api/volshell/suggest':
            return await app.suggest_volshell(body['case_id'],body['session_id'],body['text'])
        if path=='/api/volshell/investigate':
            return app.investigate_volshell(body['case_id'],body['session_id'],body['text'],body.get('request_id'))
        if path=='/api/cases':return {'cases':app.add(body['paths'],body.get('related',False),body.get('title',''),body.get('source',''))}
        if path=='/api/history-order':return app.set_history_order(body['case_id'],body['section'],body['order'])
        if path=='/api/jobs':return app.enqueue(body['case_id'],body['kind'],body.get('text',''),body.get('request_id'),retry_of=body.get('retry_of'))
        if path=='/api/reports/remove':return await app.remove_report(body['case_id'],body['report_id'],body['action'])
        if path=='/api/reports/determination':return app.set_human_determination(body['case_id'],body['report_id'],body.get('value'))
        if path=='/api/reports/error-acknowledgment':return await app.set_plugin_error_acknowledgment(
            body['case_id'],body['report_id'],body.get('error_id'),body.get('acknowledged'))
        if path=='/api/reports/acknowledge-all-errors':return await app.acknowledge_all_plugin_errors(
            body['case_id'],body['report_id'])
        if path=='/api/stop':return await app.stop()
        if path=='/api/pick':return await app.native_pick()
        if path=='/api/approval':
            pending=app.approvals[body['id']]
            if pending['future'].done():raise ValueError('Approval is no longer pending')
            pending['future'].set_result(body['answer']);return {'submitted':True}
        raise ValueError('Unknown action')

    async def get_data(self,path,query):
        app=self.server.app
        one=lambda k,d='':query.get(k,[d])[0]
        if path=='/api/state':
            snapshot = app.snapshot()
            manager = getattr(app, 'settings_manager', None)
            if manager is not None:
                snapshot = {**snapshot, 'appearance': manager.appearance()}
            return snapshot
        if path=='/api/volshell':
            app.case(one('case'))
            return app.volshell_snapshot()
        if path=='/api/settings':return app.settings_manager.snapshot()
        if path=='/api/settings/zoom':return app.settings_manager.zoom()
        if path=='/api/plugins':
            if one('refresh', '0') not in ('0', '1'):
                raise ValueError('refresh must be 0 or 1')
            return await app.plugin_catalog(refresh=one('refresh', '0') == '1')
        if path=='/api/browse':return app.browse(one('path'),one('location') or None)
        if path=='/api/artifacts':return app.artifacts(app.case(one('case')))
        if path=='/api/coverage':
            return await asyncio.to_thread(app.coverage, app.case(one('case')), one('image'),
                int(one('offset','0')), one('entry') or None, int(one('attempt_offset','0')))
        if path=='/api/citations':
            return await asyncio.to_thread(app.citations, app.case(one('case')), one('report'),
                int(one('offset','0')), one('finding') or None, int(one('index','0')))
        if path=='/api/report-plugins':
            return await asyncio.to_thread(app.report_plugins, app.case(one('case')), one('report'),
                int(one('offset','0')), int(one('limit','20')))
        if path=='/api/report-console':
            return await asyncio.to_thread(app.report_console, app.case(one('case')), one('job'))
        if path=='/api/file':return app.read_file(app.case(one('case')),one('path'),int(one('offset','0')))
        raise ValueError('Unknown route')

    async def shell_stream_data(self, case_id):
        app = self.server.app
        app.case(case_id)
        # Stream only terminal transport state. Investigation history and other
        # cases remain on their existing authenticated snapshot routes.
        view = app.volshell.snapshot(case_id)
        agent = getattr(app, 'volshell_agent', None)
        activity = agent.snapshot() if agent else None
        view['agent_activity'] = activity if activity and activity.get('case_id') == case_id else None
        return view

    def stream_shell(self, query):
        case_id = query.get('case', [''])[0]
        initial = self.invoke(self.shell_stream_data(case_id))
        if not self.server.stream_slots.acquire(blocking=False):
            return self.send(429, {'error':'Too many terminal streams; close another console'})
        try:
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Connection', 'close')
            self.end_headers()
            self.connection.settimeout(5)
            self.close_connection = True
            previous = None
            heartbeat = time.monotonic()
            # Bounded connections reconnect through EventSource with a complete
            # current view. Flush fragments without waiting for newline/prompt.
            deadline = heartbeat + 120
            while not self.server.streams_stopping.is_set() and time.monotonic() < deadline:
                if select.select([self.connection], [], [], 0)[0] and not self.connection.recv(1, socket.MSG_PEEK):
                    break
                view = initial if initial is not None else self.invoke(self.shell_stream_data(case_id), timeout=5)
                initial = None
                data = json.dumps({'case_id':case_id, **view}, ensure_ascii=True, separators=(',', ':')).encode()
                if data != previous:
                    self.wfile.write(b'event: volshell\ndata: ' + data + b'\n\n')
                    self.wfile.flush()
                    previous = data
                    heartbeat = time.monotonic()
                elif time.monotonic() - heartbeat >= 10:
                    self.wfile.write(b': heartbeat\n\n')
                    self.wfile.flush()
                    heartbeat = time.monotonic()
                self.server.streams_stopping.wait(.05)
        except (OSError, TimeoutError, ValueError, RuntimeError):
            # A closed browser is not an app error; never append JSON after SSE.
            pass
        finally:
            self.server.stream_slots.release()

    def do_GET(self):
        try:
            self.guard()
            url=urlsplit(self.path)
            assets={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8'),'/icon.png':('icon.png','image/png')}
            assets.update({'/settings.html':('settings.html','text/html; charset=utf-8'),
                '/settings.js':('settings.js','text/javascript; charset=utf-8'),
                '/settings.css':('settings.css','text/css; charset=utf-8'),
                '/themes.js':('themes.js','text/javascript; charset=utf-8'),
                '/zoom.js':('zoom.js','text/javascript; charset=utf-8'),
                '/volshell.js':('volshell.js','text/javascript; charset=utf-8'),
                '/themes.css':('themes.css','text/css; charset=utf-8'),
                '/halloween-night.png':('halloween-night.png','image/png')})
            # Asset paths originate only in the package, never in request text.
            assets.update({'/'+p.name:(p.name,'image/svg+xml')
                for p in (Path(__file__).parent/'static').glob('theme-*.svg') if p.is_file()})
            if url.path in assets:
                name,mime=assets[url.path]
                return self.send(200,(Path(__file__).parent/'static'/name).read_bytes(),mime)
            self.authenticated()
            if url.path=='/api/volshell/events':
                return self.stream_shell(parse_qs(url.query))
            if url.path=='/api/coin':
                query=parse_qs(url.query)
                case=self.server.app.case(query['case'][0])
                path=query['path'][0]
                if not re.fullmatch(r'(?:reports/[A-Za-z0-9_+. -]+/)?assets/coins/[a-f0-9]{64}\.(png|svg)',path):
                    raise ValueError('Invalid coin path')
                asset=safe_file(self.server.app.directory(case),path)
                if asset.stat().st_size>8*1024*1024:raise ValueError('Coin exceeds size limit')
                return self.send(200,asset.read_bytes(),'image/png' if path.endswith('.png') else 'image/svg+xml')
            self.send(200,self.invoke(self.get_data(url.path,parse_qs(url.query))))
        except PermissionError as exc:self.send(403,{'error':str(exc)})
        except (Exception,) as exc:self.send(400,{'error':str(exc)})

    def do_POST(self):
        try:
            self.guard(action=True)
            if self.headers.get('Content-Type')!='application/json':raise ValueError('JSON content type required')
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=2_000_000:raise ValueError('Invalid request size; file uploads are not supported')
            self.connection.settimeout(15)
            body=json.loads(self.rfile.read(size))
            if self.path=='/api/unlock':
                if not secrets.compare_digest(str(body.get('token','')),self.server.token):raise PermissionError('Invalid launch token')
                return self.send(200,{'connected':True},cookie=True)
            if self.path in ('/api/internal/volshell', '/api/internal/volshell/cancel'):
                case_id = body.get('case_id')
                if not isinstance(case_id, str) or not 0 < len(case_id) <= 256:
                    raise PermissionError('Invalid VolShell case capability')
                expected = hmac.new(self.server.app.volshell_bridge_secret,
                                    case_id.encode(), hashlib.sha256).hexdigest()
                if not secrets.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + expected):
                    raise PermissionError('Invalid VolShell case capability')
                return self.bridge_shell(case_id, body, cancel=self.path.endswith('/cancel'))
            self.authenticated()
            self.send(200,self.invoke(self.dispatch(self.path,body)))
        except PermissionError as exc:self.send(403,{'error':str(exc)})
        except (Exception,) as exc:self.send(400,{'error':str(exc)})

    def bridge_shell(self, case_id, body, cancel=False):
        ident = body.get('request_id')
        if not isinstance(ident, str) or not re.fullmatch(r'[a-f0-9]{32}', ident):
            raise ValueError('A unique VolShell request identity is required')
        key = (case_id, ident)
        with self.server.bridge_lock:
            current = time.monotonic()
            self.server.bridge_cancelled = {k:v for k,v in self.server.bridge_cancelled.items() if v > current}
            if cancel:
                future = self.server.bridge_requests.get(key)
                if future:
                    future.cancel()
                # Cancellation may arrive before the original HTTP request.
                if len(self.server.bridge_cancelled) >= 64:
                    self.server.bridge_cancelled.pop(next(iter(self.server.bridge_cancelled)))
                self.server.bridge_cancelled[key] = current + 180
            else:
                if key in self.server.bridge_cancelled:
                    raise ValueError('VolShell request has already finished or was cancelled')
                if key in self.server.bridge_requests or len(self.server.bridge_requests) >= 8:
                    raise ValueError('VolShell request is already active or capacity is full')
                future = asyncio.run_coroutine_threadsafe(
                    self.server.app.run_agent_volshell(case_id, body.get('arguments', {})), self.server.loop)
                self.server.bridge_requests[key] = future
        if cancel:
            return self.send(200, {'cancelled':True})
        try:
            result = future.result(timeout=180)
        except TimeoutError:
            future.cancel()
            raise
        finally:
            with self.server.bridge_lock:
                self.server.bridge_requests.pop(key, None)
                if len(self.server.bridge_cancelled) >= 64:
                    self.server.bridge_cancelled.pop(next(iter(self.server.bridge_cancelled)))
                self.server.bridge_cancelled[key] = time.monotonic() + 180
        return self.send(200, result)


async def serve(args):
    require_core()
    config=load_config(args.config)
    root=private_dir(Path(args.state_dir).expanduser().absolute() if args.state_dir else config.output_root/'workbench')
    lock=(root/'app.lock').open('a+')
    fingerprint=runtime_fingerprint()
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        session=json.loads((root/'session.json').read_text())
        check_running_version(session,fingerprint)
        print('Workbench is already running: '+session['url'])
        if not args.no_open:await asyncio.to_thread(open_browser,session['url'])
        return
    app=Workbench(args.config,root,getattr(args,'project',None))
    from .settings import SettingsManager
    from .desktop import preferences_directory
    settings_config=Path(args.config or os.environ.get('VOLATILITY_MCP_CONFIG') or Path.home()/'.config/volatility-mcp/config.json').expanduser().absolute()
    app.settings_manager=SettingsManager(app,settings_config,preferences_directory())
    await app.start()
    server=Server(app,args.port,asyncio.get_running_loop())
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url=server.origin+'/#'+server.token
    atomic_json(root/'session.json',{'url':url,'runtime_fingerprint':fingerprint})
    print('Volatility Workbench: '+url,flush=True)
    print('Keep this process running. Ctrl-C stops queued and active work. Selected excerpts may reach your configured AI service.',flush=True)
    stop=asyncio.Event()
    loop=asyncio.get_running_loop()
    for signum in (signal.SIGINT,signal.SIGTERM):loop.add_signal_handler(signum,stop.set)
    try:
        if not args.no_open:await asyncio.to_thread(open_browser,url)
        await stop.wait()
    finally:
        await app.close()
        await asyncio.to_thread(server.shutdown)
        server.server_close()
        lock.close()


def main(argv=None):
    parser=argparse.ArgumentParser(description='Optional local Volatility Workbench')
    parser.add_argument('--config')
    parser.add_argument('--project',help='Deprecated: optional source-root exclusion; the report contract is installed with core')
    parser.add_argument('--state-dir',help='Private case output directory outside the repository (default: output_root/workbench)')
    parser.add_argument('--port',type=int,default=0,help='Loopback port; default chooses an available port')
    parser.add_argument('--no-open',action='store_true')
    args=parser.parse_args(argv)
    try:asyncio.run(serve(args))
    except (ValueError,OSError) as exc:parser.exit(2,str(exc)+'\n')


if __name__=='__main__':main()
