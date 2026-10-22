#!/usr/bin/env python3
"""Explicit Mac signing and an opt-in, staged notarization/release pipeline."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import plistlib
import re
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MACH_MAGICS = {b'\xce\xfa\xed\xfe': '<', b'\xcf\xfa\xed\xfe': '<',
               b'\xfe\xed\xfa\xce': '>', b'\xfe\xed\xfa\xcf': '>'}
FAT_MAGICS = {b'\xca\xfe\xba\xbe': ('>', False), b'\xbe\xba\xfe\xca': ('<', False),
              b'\xca\xfe\xba\xbf': ('>', True), b'\xbf\xba\xfe\xca': ('<', True)}
RESOURCE_NAMES = {'runtime', 'analyzer', 'wheelhouse', 'notices', 'distribution.json',
                  'analyzer.lock.txt', 'desktop.lock.txt', 'core-dependency.json',
                  'bundled-addons.json', 'Workbench.icns', 'desktop-launcher',
                  'build-info.json', 'wheel-hashes.json'}
PRIVATE_NAMES = {'.git', '.aws', '.codex', '.venv', 'config.local.json',
                 'config.json', 'case-manifest.json', 'investigation.jsonl', 'iocs.csv'}
PRIVATE_SUFFIXES = {'.raw', '.mem', '.vmem', '.dmp', '.lime', '.dd', '.p12', '.pfx'}


def run(argv, **kwargs):
    return subprocess.run([str(x) for x in argv], check=True, shell=False, **kwargs)


def sha256(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def macho_types(path):
    """Return actual Mach-O file types, including each universal-binary slice."""
    with path.open('rb') as stream:
        magic = stream.read(4)
        if magic in MACH_MAGICS:
            stream.seek(12)
            return {struct.unpack(MACH_MAGICS[magic] + 'I', stream.read(4))[0]}
        if magic not in FAT_MAGICS:
            return set()
        endian, wide = FAT_MAGICS[magic]
        count = struct.unpack(endian + 'I', stream.read(4))[0]
        if not 1 <= count <= 32:
            raise ValueError('Invalid universal Mach-O architecture count: ' + str(path))
        slices = []
        for _ in range(count):
            entry = stream.read(32 if wide else 20)
            fields = struct.unpack(endian + ('IIQQII' if wide else 'IIIII'), entry)
            slices.append((fields[2], fields[3]))
        result = set()
        for offset, size in slices:
            if size < 16 or offset < 8 + count * (32 if wide else 20) or offset + size > path.stat().st_size:
                raise ValueError('Invalid universal Mach-O slice: ' + str(path))
            stream.seek(offset)
            inner = stream.read(4)
            if inner not in MACH_MAGICS:
                raise ValueError('Invalid universal Mach-O header: ' + str(path))
            stream.seek(offset + 12)
            result.add(struct.unpack(MACH_MAGICS[inner] + 'I', stream.read(4))[0])
        return result


def validate_links(app):
    for path in app.rglob('*'):
        if path.is_symlink() and (not path.exists() or not path.resolve().is_relative_to(app.resolve())):
            raise ValueError('Broken or external symlink: ' + str(path.relative_to(app)))


def native_files(app):
    result = []
    for path in sorted(app.rglob('*')):
        if path.is_file() and not path.is_symlink():
            types = macho_types(path)
            if types:
                result.append((path, types))
    return result


def identity(value):
    if value == '-':
        return value
    identities = run(['/usr/bin/security', 'find-identity', '-v', '-p', 'codesigning'],
                     capture_output=True, text=True).stdout
    for certificate, name in re.findall(r'\b([A-Fa-f0-9]{40}) "([^"]+)"', identities):
        if (value == name or value.lower() == certificate.lower()) and name.startswith('Developer ID Application: '):
            return certificate
    raise ValueError('No valid Developer ID Application identity matches; install its certificate and private key in Keychain')


def sign(app, signing_identity, *, nested):
    """No --deep signing. Libraries receive no executable entitlements/options."""
    validate_links(app)
    certificate = identity(signing_identity)
    metadata = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
    targets = native_files(app) if nested else [(app, {2})]
    commands = []
    for path, types in targets:
        argv = ['/usr/bin/codesign', '--force', '--sign', certificate]
        if certificate != '-':
            argv += ['--timestamp']
            if 2 in types:  # MH_EXECUTE, not MH_DYLIB or MH_BUNDLE
                argv += ['--options', 'runtime']
        if path != app:
            # A stable identifier for non-bundled interpreters, helpers and libraries.
            relative = str(path.relative_to(app))
            argv += ['--identifier', metadata['CFBundleIdentifier'] + '.' + hashlib.sha256(relative.encode()).hexdigest()[:20]]
        argv.append(path)
        run(argv)
        commands.append(str(path.relative_to(app)) if path != app else '.')
    return commands


def audit(app):
    """Structural/provenance checks, not a claim of exhaustive secret detection."""
    validate_links(app)
    resources = app / 'Contents/Resources'
    info = json.loads((resources / 'build-info.json').read_text())
    manifest = json.loads((resources / 'distribution.json').read_text())
    failures = []
    if manifest != json.loads((ROOT / 'packaging/distribution.json').read_text()):
        failures.append('Embedded distribution profile differs from the reviewed checkout')
    if info.get('source_dirty') is not False:
        failures.append('Release source is dirty or unspecified')
    if not re.fullmatch(r'[0-9a-f]{40}', info.get('workbench_commit', '')):
        failures.append('Missing full source commit')
    if set(p.name for p in app.iterdir()) != {'Contents'}:
        failures.append('Unexpected application-root content')
    if set(p.name for p in (app / 'Contents').iterdir()) - {'Info.plist', 'MacOS', 'Resources', '_CodeSignature'}:
        failures.append('Unexpected Contents entries')
    if set(p.name for p in (app / 'Contents/MacOS').iterdir()) != {'Volatility Workbench'}:
        failures.append('Unexpected main executable entries')
    if set(p.name for p in resources.iterdir()) != RESOURCE_NAMES:
        failures.append('Resource layout differs from the reviewed distribution profile')
    metadata = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
    if metadata.get('CFBundleIdentifier') != manifest['application']['bundle_id'] or info.get('bundle_id') != metadata.get('CFBundleIdentifier'):
        failures.append('Bundle identifiers disagree')
    receipts = json.loads((resources / 'bundled-addons.json').read_text())
    if {s['repository'] for s in receipts['sources']} != set(manifest['community']['bundled_sources']):
        failures.append('Bundled community receipts differ from the distribution allowlist')
    if receipts['pypykatz'] != manifest['pypykatz_plugin']:
        failures.append('pypykatz receipt differs from its distribution pin')
    profile = json.loads((resources / 'runtime/lib/python3.12/site-packages/volatility_mcp/resources/addons.json').read_text())
    plugins = resources / 'analyzer/lib/python3.12/site-packages/volatility3/framework/plugins'
    if receipts['sources'] != [s for s in profile['sources'] if s['repository'] in manifest['community']['bundled_sources']]:
        failures.append('Bundled sources differ from the pinned core profile')
    for source in profile['sources']:
        for item in source['files']:
            if source['repository'] not in manifest['community']['bundled_sources'] and (plugins / item['target']).exists():
                failures.append('Excluded community plugin is present: ' + item['target'])
    for required in ('notices/workbench-LICENSE', 'notices/workbench-THIRD_PARTY_NOTICES.md', 'notices/LICENSING.md',
                     'notices/dependencies/MIT.txt', 'notices/dependencies/LicenseRef-Volatility-Software-License-1.0.txt',
                     'notices/core/LICENSE', 'notices/core/LICENSING.md', 'notices/core/THIRD_PARTY_NOTICES.md',
                     'notices/core/licenses/MIT.txt', 'notices/core/licenses/LicenseRef-Volatility-Software-License-1.0.txt',
                     'notices/SOURCE_CODE.json',
                     'notices/python-standalone/licenses', 'notices/pypykatz-LICENSE'):
        if not (resources / required).exists():
            failures.append('Missing notice: ' + required)
    source_path = resources / 'notices/SOURCE_CODE.json'
    if source_path.is_file():
        sources = json.loads(source_path.read_text())
        if (sources.get('workbench', {}).get('revision') != info.get('workbench_commit')
                or sources.get('core', {}).get('revision') != info.get('core_commit')
                or sources.get('public_source_required_for_distribution') is not True):
            failures.append('Source notice differs from build revisions or omits public-source requirement')
    inventory = []
    for path in sorted(app.rglob('*')):
        relative = str(path.relative_to(app))
        if path.is_symlink():
            if not path.resolve().is_relative_to(app.resolve()) or not path.exists():
                failures.append('Broken or external symlink: ' + relative)
            continue
        if path.name in PRIVATE_NAMES or path.name.startswith('.env') or path.suffix.lower() in PRIVATE_SUFFIXES:
            failures.append('Possible private material: ' + relative)
        if path.is_file():
            inventory.append({'path': relative, 'bytes': path.stat().st_size, 'sha256': sha256(path)})
    if failures:
        raise ValueError('; '.join(failures))
    return {'status': 'passed', 'scope': 'layout, selected private filenames, symlinks, addon allowlist, notices, file hashes; manual content/license review still required',
            'build': info, 'inventory': inventory}


def verify_developer_id(app):
    run(['/usr/bin/codesign', '--verify', '--deep', '--strict', app], capture_output=True, text=True)
    team = None
    for path, types in [(app, {2}), *native_files(app)]:
        # codesign diagnostics are intentionally on stderr.
        detail = run(['/usr/bin/codesign', '--display', '--verbose=4', path], capture_output=True, text=True).stderr
        directory = re.search(r'^CodeDirectory .*flags=0x([0-9a-fA-F]+)', detail, re.M)
        runtime = bool(directory and int(directory[1], 16) & 0x10000)
        if (not re.search(r'^Authority=Developer ID Application: .+', detail, re.M)
                or not re.search(r'^Timestamp=.+', detail, re.M) or 2 in types and not runtime):
            raise ValueError('Missing Developer ID/timestamp/hardened runtime: ' + str(path.relative_to(app)))
        if 2 in types:
            entitlements = run(['/usr/bin/codesign', '--display', '--entitlements', ':-', path], capture_output=True, text=True).stdout
            if entitlements.strip() and plistlib.loads(entitlements.encode()).get('com.apple.security.get-task-allow'):
                raise ValueError('Distribution executable permits debugger attachment')
        current = re.search(r'^TeamIdentifier=(\S+)$', detail, re.M)
        if not current or current[1] == 'not set' or team and current[1] != team:
            raise ValueError('Missing or inconsistent signing team')
        team = current[1]
    return team


def notarize(app, output, profile, *, dry_run=False):
    if output.exists() or output.resolve().is_relative_to(app.resolve()):
        raise ValueError('Choose a new output directory outside the source app; releases are never overwritten')
    inspection = audit(app)
    plan = {'input_unchanged': True, 'upload': 'staged application ZIP only; never cases or evidence',
            'steps': ['verify Developer ID signatures/timestamps/hardened runtime', 'copy app',
                      'submit ZIP with notarytool --wait', 'require Accepted; save submission log',
                      'staple and validate app ticket', 'assess Gatekeeper', 'create final ZIP and SHA-256 receipt'],
            'build_signing': inspection['build'].get('signing'), 'dry_run': dry_run}
    if dry_run:
        return plan
    if inspection['build'].get('signing') != 'developer-id':
        raise ValueError('Rebuild with --sign-identity using a Developer ID Application identity before notarizing')
    if not profile or profile.startswith('-'):
        raise ValueError('Supply an existing notarytool Keychain profile; do not pass passwords to this script')
    if sys.platform != 'darwin':
        raise ValueError('Notarization requires Apple command-line tools on macOS')
    team = verify_developer_id(app)
    output.mkdir(parents=True, exist_ok=False)
    state = {'schema_version': 1, 'status': 'incomplete', 'step': 'copy', 'team_id': team,
             'started_at': datetime.now(timezone.utc).isoformat(), 'build': inspection['build']}
    def command(argv, name, timeout=300):
        state['step'] = name
        write_json(output / 'release-status.json', state)
        try:
            result = subprocess.run([str(x) for x in argv], shell=False, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as error:
            for channel in ('stdout', 'stderr'):
                value = getattr(error, channel) or ''
                if isinstance(value, bytes):
                    value = value.decode('utf-8', errors='replace')
                (output / (name + '.' + channel + '.txt')).write_text(value)
            raise
        (output / (name + '.stdout.txt')).write_text(result.stdout)
        (output / (name + '.stderr.txt')).write_text(result.stderr)
        if result.returncode:
            raise RuntimeError(f'{name} failed (exit {result.returncode}); see saved release logs')
        return result
    try:
        staged = output / app.name
        command(['/usr/bin/ditto', app, staged], 'copy')
        state['step'] = 'audit-staged'
        write_json(output / 'release-status.json', state)
        audit(staged)
        if verify_developer_id(staged) != team:
            raise ValueError('Staged signing team differs from the source app')
        upload = output / 'submission.zip'
        command(['/usr/bin/ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', staged, upload], 'package-submission')
        result = command(['xcrun', 'notarytool', 'submit', upload, '--keychain-profile', profile,
                          '--wait', '--timeout', '30m', '--output-format', 'json'], 'notary-submit', 1900)
        submission = json.loads(result.stdout)
        state['submission'] = submission
        if submission.get('id'):
            command(['xcrun', 'notarytool', 'log', submission['id'], '--keychain-profile', profile,
                     output / 'notary-log.json'], 'notary-log')
        if submission.get('status') != 'Accepted':
            raise RuntimeError('Apple did not accept the submission; see notary-log.json and submission output')
        command(['xcrun', 'stapler', 'staple', staged], 'staple')
        command(['xcrun', 'stapler', 'validate', staged], 'validate-ticket')
        command(['/usr/bin/codesign', '--verify', '--deep', '--strict', staged], 'verify-signature')
        command(['/usr/sbin/spctl', '--assess', '--type', 'execute', '--verbose=4', staged], 'gatekeeper')
        archive = output / 'Volatility-Workbench-macos-arm64-notarized.zip'
        command(['/usr/bin/ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', staged, archive], 'package-final')
        write_json(output / 'bundle-inventory.json', audit(staged))
        state.update(status='complete', step='complete', notarized=True,
                     finished_at=datetime.now(timezone.utc).isoformat(),
                     artifact={'file': archive.name, 'bytes': archive.stat().st_size, 'sha256': sha256(archive)})
        write_json(output / 'release-status.json', state)
        return state
    except BaseException as error:
        state.update(status='incomplete', error=type(error).__name__ + ': ' + str(error))
        write_json(output / 'release-status.json', state)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='operation', required=True)
    check = sub.add_parser('identity', help='Check a local identity without building or uploading')
    check.add_argument('--identity', required=True)
    for name in ('sign-nested', 'seal'):
        signing = sub.add_parser(name, help='Build-internal signing step')
        signing.add_argument('app', type=Path)
        signing.add_argument('--identity', required=True)
    inspect = sub.add_parser('audit', help='Read-only layout, provenance and selected privacy checks')
    inspect.add_argument('app', type=Path)
    release = sub.add_parser('notarize', help='Copy, submit, staple, verify and archive; explicit upload')
    release.add_argument('app', type=Path)
    release.add_argument('--output', type=Path, required=True)
    release.add_argument('--keychain-profile')
    release.add_argument('--dry-run', action='store_true', help='Read-only audit/plan; no signing, upload or writes')
    args = parser.parse_args()
    try:
        if args.operation == 'identity':
            result = {'identity': identity(args.identity)}
        elif args.operation in ('sign-nested', 'seal'):
            result = {'signed': sign(args.app.resolve(), args.identity, nested=args.operation == 'sign-nested')}
        elif args.operation == 'audit':
            result = audit(args.app.resolve())
            result = {k: v for k, v in result.items() if k != 'inventory'} | {'files_checked': len(result['inventory'])}
        else:
            result = notarize(args.app.resolve(), args.output.expanduser().absolute(), args.keychain_profile, dry_run=args.dry_run)
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, KeyError, struct.error, subprocess.SubprocessError, RuntimeError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
