"""Offline packaging boundary checks; actual Mac runtime is verified separately."""
import hashlib
import importlib.util
import io
import json
import plistlib
import contextlib
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('build_macos',ROOT/'scripts/build_macos.py')
build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)


class MacPackagingTests(unittest.TestCase):
    def test_cached_archive_is_still_verified_and_failed_download_not_activated(self):
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/'python.tar.gz';target.write_bytes(b'corrupt')
            expected=hashlib.sha256(b'expected').hexdigest()
            with patch.object(build.urllib.request,'urlopen',return_value=io.BytesIO(b'wrong')):
                with self.assertRaisesRegex(ValueError,'SHA-256 mismatch'):
                    build.fetch('https://example.invalid/python.tar.gz',target,expected)
            self.assertEqual(target.read_bytes(),b'corrupt')
            self.assertFalse(target.with_suffix('.gz.partial').exists())
            with patch.object(build.urllib.request,'urlopen',return_value=io.BytesIO(b'expected')):
                self.assertEqual(build.fetch('https://example.invalid/python.tar.gz',target,expected),target)
            with patch.object(build.urllib.request,'urlopen',side_effect=AssertionError('no network')):
                build.fetch('https://example.invalid/python.tar.gz',target,expected)

    def test_python_archive_cannot_escape_build_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); archive=root/'bad.tar.gz'
            with tarfile.open(archive,'w:gz') as out:
                entry=tarfile.TarInfo('../outside');entry.size=3;out.addfile(entry,io.BytesIO(b'bad'))
            with self.assertRaises(tarfile.FilterError):build.unpack(archive,root/'runtime')
            self.assertFalse((root/'outside').exists())

    def test_distribution_references_core_inventory_and_resolved_locks(self):
        manifest=json.loads((ROOT/'packaging/distribution.json').read_text())
        self.assertEqual(manifest['community']['inventory'],'volatility_mcp/resources/addons.json')
        self.assertEqual(manifest['community']['bundled_sources'],['spitfirerxf/vol3-plugins', 'NoCoolUserName/volatility3-cryptomem'])
        self.assertEqual(len(manifest['python']['sha256']),64)
        for lock in (manifest['desktop_lock'],manifest['analyzer_lock']):
            for line in (ROOT/lock).read_text().splitlines():
                if line and not line.startswith('#'):self.assertRegex(line,r'^[A-Za-z0-9_\[\],.-]+==[0-9.]+$')
        self.assertEqual(json.loads((ROOT/manifest['core_pin']).read_text())['repository'],'NoCoolUserName/volatility-mcp')

class MacInstallerTests(unittest.TestCase):
    @staticmethod
    def installer():
        spec=importlib.util.spec_from_file_location('install_macos',ROOT/'scripts/install_macos.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    @staticmethod
    def app(root,dirty=False):
        app=root/'new.app';resources=app/'Contents/Resources';resources.mkdir(parents=True)
        (resources/'build-info.json').write_text(json.dumps({'source_dirty':dirty,'workbench_commit':'a'*40}))
        return app

    def test_refuses_uncommitted_build_before_install(self):
        installer=self.installer()
        with tempfile.TemporaryDirectory() as temp:
            app=self.app(Path(temp),dirty=True)
            with patch.object(installer.sys,'argv',['install',str(app)]),patch.object(installer.subprocess,'run',side_effect=AssertionError('must not run')):
                with self.assertRaisesRegex(SystemExit,'uncommitted'):installer.main()

    def test_refuses_active_bundled_child_without_stopping_it(self):
        installer=self.installer()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);app=self.app(root); destination=root/'Installed.app'
            with patch.object(installer.sys,'argv',['install',str(app),'--destination',str(destination)]),patch.object(installer.subprocess,'run',return_value=SimpleNamespace(stdout=str(destination/'Contents/Resources/runtime/bin/python3')+' -m volatility_mcp.scoped')) as run:
                with self.assertRaisesRegex(SystemExit,'Quit'):installer.main()
                self.assertEqual(run.call_count,1)
                self.assertFalse(destination.exists())

    def test_swap_failure_restores_old_application(self):
        installer=self.installer()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);app=self.app(root); destination=root/'Installed.app';destination.mkdir();(destination/'prior').write_text('old')
            original_replace=installer.os.replace
            def replace(source,target):
                if str(source).find('.workbench-install-')>=0:raise OSError('simulated activation failure')
                return original_replace(source,target)
            def run(argv,**kw):
                if argv[0]=='/usr/bin/ditto':installer.shutil.copytree(argv[1],argv[2])
                return SimpleNamespace(stdout='')
            with patch.object(installer.sys,'argv',['install',str(app),'--destination',str(destination)]),patch.object(installer.Path,'home',return_value=root/'home'),patch.object(installer.subprocess,'run',side_effect=run),patch.object(installer.os,'replace',side_effect=replace),contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(OSError,'activation'):installer.main()
            self.assertEqual((destination/'prior').read_text(),'old')
            self.assertFalse(list(root.glob('.workbench-install-*')))

class DesktopLauncherTests(unittest.TestCase):
    @staticmethod
    def fixture(root):
        installed=root/'Applications/Volatility Workbench.app';resources=installed/'Contents/Resources';resources.mkdir(parents=True)
        (resources/'desktop-launcher').write_bytes(b'SYNTHETIC NATIVE HELPER')
        (resources/'Workbench.icns').write_bytes(b'SYNTHETIC ICON')
        desktop=root/'Desktop';desktop.mkdir()
        command=desktop/'Launch Volatility Workbench.command';command.write_text('#!/bin/sh\necho original\n')
        return installed,desktop,command,root/'rollback/time'

    @staticmethod
    def mock_run(installer):
        def run(argv,**kw):
            if argv[0]=='/usr/bin/ditto':
                installer.shutil.copy2(argv[1],argv[2])
            return SimpleNamespace(stdout='verified')
        return run

    def test_real_app_layout_target_icon_and_old_command_backup(self):
        installer=MacInstallerTests.installer()
        with tempfile.TemporaryDirectory() as temp:
            installed,desktop,command,rollback=self.fixture(Path(temp));original=command.read_bytes()
            run=self.mock_run(installer)
            def checked(argv,**kw):
                if argv[-1]=='--check-target':self.assertTrue(command.exists(),'Old launcher must remain until activation verified')
                return run(argv,**kw)
            with patch.object(installer.subprocess,'run',side_effect=checked):
                target=installer.desktop_launcher(installed,rollback,desktop)
            self.assertTrue(target.is_dir());self.assertFalse(target.is_symlink())
            self.assertFalse(command.exists());self.assertEqual((rollback/'Desktop'/command.name).read_bytes(),original)
            metadata=plistlib.loads((target/'Contents/Info.plist').read_bytes())
            self.assertEqual(metadata['WorkbenchApplicationPath'],str(installed))
            self.assertTrue(metadata['LSUIElement'])
            self.assertEqual((target/'Contents/Resources/Workbench.icns').read_bytes(),b'SYNTHETIC ICON')

    def test_final_verification_failure_restores_previous_launcher(self):
        installer=MacInstallerTests.installer()
        with tempfile.TemporaryDirectory() as temp:
            installed,desktop,command,rollback=self.fixture(Path(temp));target=desktop/'Launch Volatility Workbench.app'
            (target/'Contents').mkdir(parents=True)
            (target/'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier':'org.volatilityworkbench.launcher'}))
            (target/'prior').write_text('original native launcher')
            run=self.mock_run(installer)
            def failure(argv,**kw):
                if argv[0]==str(target/'Contents/MacOS/Launch Volatility Workbench'):raise OSError('synthetic verification failure')
                return run(argv,**kw)
            with patch.object(installer.subprocess,'run',side_effect=failure):
                with self.assertRaisesRegex(OSError,'verification'):installer.desktop_launcher(installed,rollback,desktop)
            self.assertEqual((target/'prior').read_text(),'original native launcher')
            self.assertTrue(command.exists());self.assertEqual(command.read_bytes(),(rollback/'Desktop'/command.name).read_bytes())
            self.assertFalse(list(desktop.glob('.workbench-launcher-*')))

    def test_symlink_launcher_is_refused(self):
        installer=MacInstallerTests.installer()
        with tempfile.TemporaryDirectory() as temp:
            installed,desktop,command,rollback=self.fixture(Path(temp));command.unlink();command.symlink_to(installed)
            with self.assertRaisesRegex(ValueError,'aliases/symlinks'):installer.desktop_launcher(installed,rollback,desktop)
            self.assertTrue(command.is_symlink())

if __name__=='__main__':unittest.main()
