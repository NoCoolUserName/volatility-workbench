"""Optional native macOS shell over the same authenticated Workbench server.

There is no JavaScript-to-Python application bridge. Native controls are owned by
this shell; forensic and settings requests retain the existing HTTP protections.
"""
from __future__ import annotations
import argparse
import asyncio
import concurrent.futures
import fcntl
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import threading
from urllib.parse import urlsplit

from volatility_mcp.api import Config, load_config
from .storage import atomic_json, private_dir


def preferences_directory():
    return Path.home()/'Library/Application Support/Volatility Workbench' if sys.platform=='darwin' else Path.home()/'.config/volatility-workbench'


def bundle_resources():
    value=os.environ.get('VOLATILITY_WORKBENCH_RESOURCES')
    return Path(value).resolve() if value else None


def bootstrap(args, resources):
    """Copy operator configuration once; never move evidence or rewrite old paths."""
    root=private_dir(Path(args.preferences_dir).expanduser())
    prefs_path=root/'desktop.json'
    prefs=json.loads(prefs_path.read_text()) if prefs_path.exists() else {}
    if args.config:
        config_path=Path(args.config).expanduser().absolute()
    elif prefs.get('config_path'):
        config_path=Path(prefs['config_path'])
    else:
        candidates=[Path.home()/'src/Forensics/volatility-mcp/config.local.json',
                    Path.home()/'.config/volatility-mcp/config.json']
        found=next((p for p in candidates if p.is_file()),None) if not args.clean_setup else None
        config_path=root/'config.json'
        if found:
            config=load_config(found)
            atomic_json(config_path,config.to_dict())
            prefs['imported_from']=str(found)
            legacy_state=found.parent.parent/'reports/workbench'
            if (legacy_state/'state.json').is_file(): prefs['state_dir']=str(legacy_state)
            prefs['setup_complete']=True
        else:
            if not resources: raise ValueError('A new setup needs the packaged runtime or an explicit --config.')
            documents=Path.home()/'Documents/Volatility Workbench'
            config=Config(evidence_root=documents/'Evidence',output_root=documents/'Outputs',
                vol_python=resources/'analyzer/bin/python3',vol_executable=resources/'analyzer/bin/vol',
                symbols=root/'symbols',cache_path=Path.home()/'Library/Caches/Volatility Workbench/symbols')
            for directory in (config.evidence_root,config.output_root,config.symbols,config.cache_path): private_dir(directory)
            atomic_json(config_path,config.to_dict())
            prefs['bundled_analyzer']=str(resources/'analyzer')
            prefs['setup_complete']=False
    config=load_config(config_path)
    prefs.setdefault('setup_complete',bool(args.config))
    state=Path(args.state_dir or prefs.get('state_dir') or config.output_root/'workbench').expanduser().absolute()
    prefs.update(config_path=str(config_path),state_dir=str(state))
    atomic_json(prefs_path,prefs)
    return root,config_path,state,prefs


def visible_geometry(saved, screens):
    """Clamp normal window bounds to a visible monitor, including after undocking."""
    if not screens: return {'width':1180,'height':820}
    try:
        x,y,w,h=(int(saved[k]) for k in ('x','y','width','height'))
    except (TypeError,KeyError,ValueError):
        x,y,w,h=screens[0]['x'],screens[0]['y'],1180,820
    screen=next((s for s in screens if x<s['x']+s['width'] and x+w>s['x'] and y<s['y']+s['height'] and y+h>s['y']),screens[0])
    w=min(max(800,w),screen['width']);h=min(max(600,h),screen['height'])
    return {'x':max(screen['x'],min(x,screen['x']+screen['width']-w)),
            'y':max(screen['y'],min(y,screen['y']+screen['height']-h)), 'width':w,'height':h}


def navigation_allowed(url, origin):
    if url=='about:blank': return True
    p=urlsplit(url); expected=urlsplit(origin)
    return p.scheme==expected.scheme and p.netloc==expected.netloc and not p.username and not p.password


class BackendHost:
    """One server/event loop with the same lock/fingerprint as browser mode."""
    def __init__(self, config_path, state_dir, preferences, resources=None):
        self.config_path,self.root,self.preferences,self.resources=config_path,private_dir(state_dir),preferences,resources
        self.ready=concurrent.futures.Future();self.app=None;self.server=None;self.owned=False
        self.thread=threading.Thread(target=self._thread,name='workbench-backend',daemon=False)
        self.picker=None

    def _thread(self):
        try: asyncio.run(self._serve())
        except BaseException as exc:
            if not self.ready.done():self.ready.set_exception(exc)

    async def _serve(self):
        from .http import runtime_fingerprint,check_running_version,Server
        from .app import Workbench
        from .settings import SettingsManager
        self.loop=asyncio.get_running_loop();self.stop_event=asyncio.Event()
        lock=(self.root/'app.lock').open('a+')
        try:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                session=json.loads((self.root/'session.json').read_text())
                check_running_version(session,runtime_fingerprint())
                self.url=session['url'];self.ready.set_result(self.url);return
            self.owned=True
            from .runtime_management import rebase_bundled_runtime
            rebase_bundled_runtime(self.config_path,self.root,self.preferences,self.resources)
            self.app=Workbench(self.config_path,self.root)
            self.app.settings_manager=SettingsManager(self.app,self.config_path,self.preferences,self.resources,
                                                     folder_picker=lambda kind:self.picker(kind) if self.picker else None)
            await self.app.start()
            self.server=Server(self.app,0,self.loop)
            server_thread=threading.Thread(target=self.server.serve_forever,daemon=True);server_thread.start()
            self.url=self.server.origin+'/#'+self.server.token
            atomic_json(self.root/'session.json',{'url':self.url,'runtime_fingerprint':runtime_fingerprint(),'desktop':True})
            self.ready.set_result(self.url)
            try:await self.stop_event.wait()
            finally:
                await self.app.close()
                await asyncio.to_thread(self.server.shutdown)
                self.server.server_close();server_thread.join(timeout=5)
        finally:lock.close()

    def start(self):
        self.thread.start();return self.ready.result(timeout=45)

    def activity(self):
        if not self.app:return {'active':False,'maintenance':False,'owned':False}
        async def read():
            return {'active':bool(self.app.active or getattr(getattr(self.app,'volshell',None),'busy',False)
                                  or any(j['status'] in ('queued','running','stopping') for j in self.app.state['jobs'])),
                    'maintenance':bool(self.app.settings_manager.busy or getattr(self.app, 'report_cleanup', {})),'owned':True}
        return asyncio.run_coroutine_threadsafe(read(),self.loop).result(timeout=5)

    def shutdown(self):
        if self.owned and self.thread.is_alive():
            self.loop.call_soon_threadsafe(self.stop_event.set)
            self.thread.join(timeout=120)
            if self.thread.is_alive():raise RuntimeError('Backend is still stopping; keep the application open until cleanup completes.')


def install_cocoa_hooks(controller):
    """Small pinned Cocoa adapter: keep window chrome, constrain navigation/lifecycle."""
    import objc
    import AppKit
    from PyObjCTools import AppHelper
    from webview.platforms.cocoa import BrowserView
    original=BrowserView.BrowserDelegate

    class WebKitHost(objc.Category(BrowserView.WebKitHost)):
        def keyDown_(self,event):
            # Route Cmd-Q through the same guarded Quit path as the application menu.
            # WKWebView itself supplies normal editing/selection shortcuts.
            if event.modifierFlags() & AppKit.NSEventModifierFlagCommand and event.charactersIgnoringModifiers().lower()=='q':
                AppKit.NSApplication.sharedApplication().terminate_(self)
                return
            objc.super(BrowserView.WebKitHost,self).keyDown_(event)

        def willOpenMenu_withEvent_(self,menu,event):
            # Restore WebKit's normal copy/save-image menu. No Python bridge is exposed.
            pass

    class WorkbenchNavigationDelegate(original):
        def webView_decidePolicyForNavigationAction_decisionHandler_(self, view, action, handler):
            url=str(action.request().URL().absoluteString())
            if navigation_allowed(url,controller.origin):
                return objc.super(WorkbenchNavigationDelegate,self).webView_decidePolicyForNavigationAction_decisionHandler_(view,action,handler)
            if action.navigationType()==0: controller.open_external(url)
            handler(0)
        def webView_decidePolicyForNavigationResponse_decisionHandler_(self,view,response,handler):
            if not navigation_allowed(str(response.response().URL().absoluteString()),controller.origin):
                handler(0);return
            return objc.super(WorkbenchNavigationDelegate,self).webView_decidePolicyForNavigationResponse_decisionHandler_(view,response,handler)
        def webView_createWebViewWithConfiguration_forNavigationAction_windowFeatures_(self,view,config,action,features):
            if action.navigationType()==0:controller.open_external(str(action.request().URL().absoluteString()))
            return None

    class WorkbenchApplicationDelegate(AppKit.NSObject):
        @objc.typedSelector(b'v@:@')
        def workbenchAbout_(self,sender):controller.about()

        def applicationShouldTerminate_(self, app):
            if controller.quitting:return AppKit.NSTerminateCancel
            state=controller.host.activity()
            if state['maintenance']:
                controller.alert('Maintenance is still running','Keep Workbench open until plugin, symbol or report cleanup finishes. Your current runtime remains available.')
                return AppKit.NSTerminateCancel
            if state['active']:
                alert=AppKit.NSAlert.alloc().init()
                alert.setMessageText_('Investigation work or VolShell is still active')
                alert.setInformativeText_('Keep working, or stop queued work and active sessions safely and quit. Completed evidence will be retained.')
                alert.addButtonWithTitle_('Keep working');alert.addButtonWithTitle_('Cancel work and quit')
                if alert.runModal()!=AppKit.NSAlertSecondButtonReturn:return AppKit.NSTerminateCancel
            controller.quitting=True
            def stop():
                try:
                    controller.save_geometry();controller.host.shutdown()
                    AppHelper.callAfter(app.replyToApplicationShouldTerminate_,True)
                except Exception as exc:
                    controller.quitting=False
                    AppHelper.callAfter(controller.alert,'Could not finish shutting down',str(exc))
                    AppHelper.callAfter(app.replyToApplicationShouldTerminate_,False)
            threading.Thread(target=stop,daemon=False).start()
            return AppKit.NSTerminateLater
        def applicationShouldHandleReopen_hasVisibleWindows_(self,app,visible):
            controller.window.show();return True
        def applicationSupportsSecureRestorableState_(self,app):return True

    BrowserView.BrowserDelegate=WorkbenchNavigationDelegate
    BrowserView.AppDelegate=WorkbenchApplicationDelegate


class Desktop:
    def __init__(self, host, preferences, prefs, resources):
        self.host,self.preferences,self.prefs,self.resources=host,preferences,prefs,resources
        self.window=None;self.quitting=False
        self.url=host.start();p=urlsplit(self.url);self.origin=f'{p.scheme}://{p.netloc}'

    def open_external(self,url):
        from AppKit import NSWorkspace
        from Foundation import NSURL
        p=urlsplit(url)
        if p.scheme in ('https','http') and p.netloc and not p.username and not p.password:
            NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_(url))

    def alert(self,title,text):
        import AppKit
        alert=AppKit.NSAlert.alloc().init();alert.setMessageText_(title);alert.setInformativeText_(text)
        alert.addButtonWithTitle_('OK');alert.runModal()

    def about(self):
        from PyObjCTools import AppHelper
        data={}
        if self.resources and (self.resources/'build-info.json').exists():data=json.loads((self.resources/'build-info.json').read_text())
        versions=[]
        for name in ('volatility-workbench','volatility-mcp','pywebview'):
            try:versions.append(f'{name}: {importlib.metadata.version(name)}')
            except importlib.metadata.PackageNotFoundError:pass
        versions.append('Python: '+sys.version.split()[0])
        if data:
            versions.append('Build: '+str(data.get('workbench_commit','local')))
            versions.append('Core revision: '+str(data.get('core_commit','unknown')))
            versions.append('Bundled Volatility3: '+str(data.get('packages',{}).get('analyzer',{}).get('volatility3','unknown')))
        catalog=getattr(self.host.app,'_plugin_catalog',None) if self.host.app else None
        if isinstance(catalog,dict):versions.append('Configured Volatility3: '+str(catalog.get('volatility_version','not yet discovered')))
        versions.append('Configured analyzer: '+str(self.host.app.config.vol_python) if self.host.app else 'Shared compatible backend')
        AppHelper.callAfter(self.alert,'Volatility Workbench','\n'.join(versions))

    def settings(self):self.window.load_url(self.origin+'/settings.html#'+urlsplit(self.url).fragment)

    def picker(self,kind):
        import webview
        result=self.window.create_file_dialog(webview.FileDialog.FOLDER if kind=='folder' else webview.FileDialog.OPEN,allow_multiple=False)
        return result[0] if result else None

    def save_geometry(self,*unused):
        if not self.window:return
        if getattr(self.window,'fullscreen',False):return
        try:
            latest=self.preferences/'desktop.json'
            if latest.exists():self.prefs.update(json.loads(latest.read_text()))
            self.prefs['window']={k:int(getattr(self.window,k)) for k in ('x','y','width','height')}
            atomic_json(self.preferences/'desktop.json',self.prefs)
        except (TypeError,ValueError,AttributeError):pass

    def close_window(self):
        self.save_geometry();self.window.hide();return False

    def run(self):
        import webview
        from webview.menu import Menu,MenuAction
        import AppKit
        install_cocoa_hooks(self)
        screens=[{'x':int(s.x),'y':int(s.y),'width':int(s.width),'height':int(s.height)} for s in webview.screens]
        geometry=visible_geometry(self.prefs.get('window',{}),screens)
        webview.settings.update(ALLOW_FILE_URLS=False,ALLOW_DOWNLOADS=True,OPEN_EXTERNAL_LINKS_IN_BROWSER=True)
        initial_url=self.url if self.prefs.get('setup_complete') else self.origin+'/settings.html#'+urlsplit(self.url).fragment
        self.window=webview.create_window('Volatility Workbench',initial_url,**geometry,min_size=(800,600),
            text_select=True,zoomable=False,background_color='#0b1417',frameless=False)
        self.window.events.closing+=self.close_window
        self.window.events.resized+=self.save_geometry
        self.window.events.moved+=self.save_geometry
        self.host.picker=self.picker
        def ready():
            # Preserve standard decorated NSWindow; AppKit supplies native corner clipping.
            from PyObjCTools import AppHelper
            def setup_native():
                native=self.window.native
                native.setCollectionBehavior_(native.collectionBehavior() | AppKit.NSWindowCollectionBehaviorFullScreenPrimary)
                app=AppKit.NSApplication.sharedApplication()
                about=app.mainMenu().itemAtIndex_(0).submenu().itemAtIndex_(0)
                about.setTarget_(app.delegate());about.setAction_('workbenchAbout:')
                app.activateIgnoringOtherApps_(True)
            AppHelper.callAfter(setup_native)
        icon=str(self.resources/'Workbench.icns') if self.resources and (self.resources/'Workbench.icns').exists() else None
        webview.start(ready,private_mode=False,storage_path=str(private_dir(self.preferences/'webview')),menu=[Menu('__app__',[MenuAction('Settings…',self.settings)])],icon=icon)
        # A stopped WebKit event loop is not approval to abandon a live backend.
        # All normal termination paths go through the delegate above.
        while not self.quitting:
            AppKit.NSApplication.sharedApplication().run()
        self.host.shutdown()


def main(argv=None):
    parser=argparse.ArgumentParser(description='Volatility Workbench macOS application')
    parser.add_argument('--config');parser.add_argument('--state-dir')
    parser.add_argument('--preferences-dir',default=str(preferences_directory()))
    parser.add_argument('--clean-setup',action='store_true',help='Ignore existing configurations for an isolated first-run setup')
    args=parser.parse_args(argv)
    if sys.platform!='darwin':parser.exit(2,'The native desktop shell currently supports macOS only. Use browser mode on supported POSIX hosts.\n')
    resources=bundle_resources()
    from .codex import child_environment
    clean=child_environment()
    if resources:clean['VOLATILITY_WORKBENCH_RESOURCES']=str(resources)
    os.environ.clear();os.environ.update(clean)
    host=None
    try:
        from .compatibility import require_core
        require_core()
        root,config,state,prefs=bootstrap(args,resources)
        lock=(root/'desktop.lock').open('a+')
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            from AppKit import NSRunningApplication,NSApplicationActivateIgnoringOtherApps
            for app in NSRunningApplication.runningApplicationsWithBundleIdentifier_('org.volatilityworkbench.app'):
                if app.processIdentifier()!=os.getpid():app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
            return
        host=BackendHost(config,state,root,resources)
        Desktop(host,root,prefs,resources).run()
    except Exception as exc:
        if host:host.shutdown()
        # No token, evidence, questions or provider secrets are written to diagnostics.
        from AppKit import NSAlert
        alert=NSAlert.alloc().init();alert.setMessageText_('Volatility Workbench could not start')
        alert.setInformativeText_(str(exc));alert.addButtonWithTitle_('OK');alert.runModal()
        raise SystemExit(2) from None

if __name__=='__main__':main()
