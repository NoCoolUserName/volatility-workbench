#!/usr/bin/env python3
"""Replace an idle user-owned app and optionally its real native Desktop launcher."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile


def run(argv,**kwargs):
    return subprocess.run([str(x) for x in argv],check=True,shell=False,**kwargs)


def desktop_launcher(installed,backup_root,desktop=None):
    """Activate an independently signed, real .app, preserving old Finder metadata."""
    desktop=Path(desktop or Path.home()/'Desktop')
    target=desktop/'Launch Volatility Workbench.app'
    command=desktop/'Launch Volatility Workbench.command'
    if desktop.is_symlink() or target.is_symlink() or command.is_symlink():
        raise ValueError('Desktop launcher paths must not be aliases/symlinks')
    if target.exists():
        info=plistlib.loads((target/'Contents/Info.plist').read_bytes())
        if info.get('CFBundleIdentifier')!='org.volatilityworkbench.launcher':
            raise ValueError('An unrelated app occupies the Desktop launcher destination')
    if command.exists() and not command.is_file():
        raise ValueError('Existing command launcher is not a regular file')
    resources=installed/'Contents/Resources'
    helper=resources/'desktop-launcher'
    if not helper.is_file() or helper.is_symlink():
        raise ValueError('Installed application is missing its native desktop launcher')
    desktop.mkdir(parents=True,exist_ok=True)
    stage_parent=Path(tempfile.mkdtemp(prefix='.workbench-launcher-',dir=desktop))
    stage=stage_parent/target.name
    previous=backup_root/'Desktop'/target.name
    old_command=backup_root/'Desktop'/command.name
    replaced=False; activated=False
    try:
        (stage/'Contents/MacOS').mkdir(parents=True);(stage/'Contents/Resources').mkdir()
        binary=stage/'Contents/MacOS/Launch Volatility Workbench'
        shutil.copy2(helper,binary);binary.chmod(0o755)
        shutil.copy2(resources/'Workbench.icns',stage/'Contents/Resources/Workbench.icns')
        metadata={'CFBundleName':'Launch Volatility Workbench','CFBundleDisplayName':'Launch Volatility Workbench',
            'CFBundleIdentifier':'org.volatilityworkbench.launcher','CFBundleExecutable':binary.name,
            'CFBundlePackageType':'APPL','CFBundleShortVersionString':'1.0','CFBundleVersion':'1',
            'CFBundleIconFile':'Workbench.icns','LSUIElement':True,'LSMinimumSystemVersion':'13.0',
            'WorkbenchApplicationPath':str(installed)}
        (stage/'Contents/Info.plist').write_bytes(plistlib.dumps(metadata))
        run(['/usr/bin/codesign','--force','--sign','-',stage])
        run(['/usr/bin/codesign','--verify','--strict',stage])
        run([binary,'--check-target'],capture_output=True,text=True)
        previous.parent.mkdir(parents=True,exist_ok=True)
        if command.exists():
            # ditto preserves the existing .command's resource fork/Finder icon.
            run(['/usr/bin/ditto',command,old_command])
            if command.read_bytes()!=old_command.read_bytes():raise ValueError('Old launcher backup did not verify')
        if target.exists():os.replace(target,previous);replaced=True
        os.replace(stage,target);activated=True
        run(['/usr/bin/codesign','--verify','--strict',target])
        run([target/'Contents/MacOS/Launch Volatility Workbench','--check-target'],capture_output=True,text=True)
        # Remove the old launcher only once the final native path is validated.
        if command.exists():command.unlink()
        return target
    except BaseException:
        if activated and target.exists():shutil.rmtree(target)
        if replaced and previous.exists():os.replace(previous,target)
        if old_command.exists() and not command.exists():run(['/usr/bin/ditto',old_command,command])
        raise
    finally:shutil.rmtree(stage_parent,ignore_errors=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('app',type=Path)
    parser.add_argument('--destination',type=Path,default=Path.home()/'Applications/Volatility Workbench.app')
    parser.add_argument('--desktop-launcher',action='store_true',help='Install a real native Desktop launcher and retain the old launcher in rollback storage')
    args=parser.parse_args();source=args.app.resolve();destination=args.destination.expanduser().absolute()
    info=json.loads((source/'Contents/Resources/build-info.json').read_text())
    if info.get('source_dirty'):raise SystemExit('Refusing installation of an uncommitted development build')
    if destination.is_symlink():raise SystemExit('Application destination must not be an alias/symlink')
    # A live app or its bundled child owns work. Never stop it from an installer.
    processes=run(['/bin/ps','-axo','command='],capture_output=True,text=True).stdout
    if str(destination/'Contents')+'/' in processes:
        raise SystemExit('Quit the installed app while idle before replacing it; no process was stopped')
    run([sys.executable,Path(__file__).with_name('validate_macos.py'),source])
    destination.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.workbench-install-',dir=destination.parent))/destination.name
    stamp=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%S.%fZ')
    backup_root=Path.home()/'Library/Application Support/Volatility Workbench/rollback'/stamp
    backup=None;activated=False;launcher=None
    try:
        run(['/usr/bin/ditto',source,stage])
        run(['/usr/bin/codesign','--verify','--deep','--strict',stage])
        backup_root.mkdir(parents=True,exist_ok=False)
        if destination.exists():
            backup=backup_root/'Applications'/destination.name
            backup.parent.mkdir();os.replace(destination,backup)
        try:
            os.replace(stage,destination);activated=True
            if args.desktop_launcher:launcher=desktop_launcher(destination,backup_root)
        except BaseException:
            if activated and destination.exists():shutil.rmtree(destination)
            if backup and backup.exists():os.replace(backup,destination)
            raise
    finally:shutil.rmtree(stage.parent,ignore_errors=True)
    print(json.dumps({'installed':str(destination),'desktop_launcher':str(launcher) if launcher else None,
                     'rollback':str(backup_root),'previous_app':str(backup) if backup else None,
                     'workbench_commit':info['workbench_commit']}))

if __name__=='__main__':main()
