#!/usr/bin/env python3
"""Private local SAST: pinned CE engine/rules, complete scans, reviewed exceptions."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SUFFIXES = {'.py', '.js', '.cjs', '.mjs', '.jsx', '.ts', '.tsx'}
IMPACTS = {'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_files(root):
    files = []
    for folder in ('src', 'scripts'):
        directory = root / folder
        if root.is_symlink() or directory.is_symlink() or not directory.is_dir():
            raise ValueError('Source scan roots must be real directories, not symlinks')
        for path in directory.rglob('*'):
            # rglob yields directory links without descending them. Reject links
            # before checking type/suffix so whole packages cannot disappear.
            if path.is_symlink():
                raise ValueError('Source scan entries must not be symlinks: ' + str(path))
            if path.is_file() and path.suffix in SOURCE_SUFFIXES:
                files.append(path)
    paths = sorted(str(path.relative_to(root)) for path in files)
    if not any(path.endswith('.py') for path in paths) or not any(path.endswith('.js') for path in paths):
        raise ValueError('Expected both Python and JavaScript source files')
    return paths


def prepare_rules(archive, lock, work):
    """Select upstream security rules without executing or extracting archive paths."""
    if sha256(archive) != lock['archive_sha256']:
        raise ValueError('Rule archive SHA-256 does not match the reviewed pin')
    from ruamel.yaml import YAML
    yaml = YAML(typ='safe')
    rules = []
    manifest = {}
    prefix = 'semgrep-rules-' + lock['commit']
    with tarfile.open(archive) as source:
        license_file = source.extractfile(prefix + '/LICENSE')
        license_text = license_file.read().decode('utf-8')
        if 'Semgrep Rules License v1.0' not in license_text:
            raise ValueError('Review the changed upstream rule license before updating')
        (work / 'RULES-LICENSE.txt').write_text(license_text)
        for member in source.getmembers():
            parts = PurePosixPath(member.name).parts
            if (not member.isfile() or len(parts) < 3 or parts[0] != prefix
                    or parts[1] not in lock['rule_folders'] or not member.name.endswith(('.yml','.yaml'))):
                continue
            document = yaml.load(source.extractfile(member).read())
            for rule in document.get('rules', []):
                metadata = rule.get('metadata', {})
                if metadata.get('category') != lock['category']:
                    continue
                ident = '.'.join(parts[1:-1]) + '.' + rule['id']
                if ident in manifest or metadata.get('impact') not in IMPACTS:
                    raise ValueError('Duplicate rule or unclassified security impact: ' + ident)
                # Prefix IDs to retain upstream folder identity in one local config.
                # Patterns, metadata, notices and severities remain unchanged.
                rule['id'] = ident
                rules.append(rule)
                manifest[ident] = {'impact':metadata['impact'], 'languages':rule['languages']}
    if len(rules) != lock['rule_count']:
        raise ValueError('Rule inventory changed; review and update the immutable rule pin')
    (work / 'RULES-MODIFICATIONS.txt').write_text(
        'Internal scan copy only. Selected security-category rules from Python/JavaScript/TypeScript '
        'folders and prefixed rule IDs with upstream directory paths. No pattern changes. '
        'Upstream: https://github.com/semgrep/semgrep-rules/tree/' + lock['commit'] + '\n')
    path = work / 'rules.json'
    path.write_text(json.dumps({'rules':rules}))
    return path, manifest


def evaluate(report, manifest, expected, exceptions, root, engine_version):
    """An absent/partial/failed scan is never a clean result; no baseline hiding."""
    if not isinstance(report, dict) or report.get('version') != engine_version:
        raise ValueError('Missing report or unexpected scanner version')
    if report.get('errors') != []:
        raise ValueError('Scanner reported errors or partial parsing: ' + json.dumps(report.get('errors')))
    scanned = report.get('paths', {}).get('scanned')
    if not isinstance(scanned, list) or set(expected) - set(scanned):
        raise ValueError('Scan omitted expected source files: ' + ', '.join(sorted(set(expected) - set(scanned or []))))
    if not isinstance(report.get('results'), list):
        raise ValueError('Scanner findings are missing')
    allowed = {}
    for item in exceptions:
        key = (item['rule_id'], item['path'], item['line'])
        if (key in allowed or item['rule_id'] not in manifest or item['path'] not in expected
                or not item.get('reason', '').strip() or not re.fullmatch('[0-9a-f]{64}',item['source_sha256'])):
            raise ValueError('Invalid or duplicate reviewed exception')
        if sha256(root / item['path']) != item['source_sha256']:
            raise ValueError('Reviewed exception is stale; re-review ' + item['path'])
        allowed[key] = item
    blocked, reviewed, used = [], [], set()
    for finding in report['results']:
        rule = manifest.get(finding['check_id'])
        if rule is None:
            raise ValueError('Scanner returned an unknown rule')
        if rule['impact'] not in ('HIGH','CRITICAL'):
            continue
        key = (finding['check_id'], finding['path'], finding['start']['line'])
        if key in allowed:
            reviewed.append({**finding, 'review_reason':allowed[key]['reason']})
            used.add(key)
        else:
            blocked.append(finding)
    if set(allowed) - used:
        raise ValueError('Unused exceptions must be removed or re-reviewed: ' + str(sorted(set(allowed) - used)))
    return {'scanned_source_files':len(expected), 'rules':len(manifest),
            'findings':len(report['results']), 'blocking':blocked, 'reviewed':reviewed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--rules-archive', type=Path, help='Already downloaded archive; digest is still verified')
    args = parser.parse_args()
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    lock = json.loads((ROOT / '.github/security-rules.json').read_text())
    if importlib.metadata.version('semgrep') != lock['engine_version']:
        raise ValueError('Install the exact Semgrep engine version from security-rules.json')
    archive = args.rules_archive or work / 'rules.tar.gz'
    if not args.rules_archive:
        url = 'https://codeload.github.com/' + lock['repository'] + '/tar.gz/' + lock['commit']
        with urllib.request.urlopen(url, timeout=60) as response:
            content = response.read(32_000_001)
        if len(content) > 32_000_000:
            raise ValueError('Rule archive exceeds download limit')
        archive.write_bytes(content)
    rules, manifest = prepare_rules(archive, lock, work)
    targets = source_files(ROOT)
    (work / 'inventory.json').write_text(json.dumps({'lock':lock,'rules':manifest,'targets':targets},indent=2))
    # Dedicated settings/log locations and an allowlist prevent inherited login,
    # token, registry, proxy or tracing settings from enabling hosted features.
    env = {key:value for key,value in os.environ.items() if key in
           ('PATH','TMPDIR','LANG','LC_ALL','LC_CTYPE','SYSTEMROOT','WINDIR','SSL_CERT_FILE')}
    env.update(SEMGREP_SEND_METRICS='off', SEMGREP_ENABLE_VERSION_CHECK='0',
               SEMGREP_SETTINGS_FILE=str(work / 'settings.yml'), SEMGREP_LOG_FILE=str(work / 'semgrep.log'))
    import certifi
    env.setdefault('SSL_CERT_FILE', certifi.where())
    (work / 'settings.yml').write_text('anonymous_user_id: ' + str(uuid.uuid4()) + '\nhas_shown_metrics_notification: true\n')
    report_path = work / 'findings.json'
    report_path.unlink(missing_ok=True)
    executable = Path(sys.executable).with_name('semgrep')
    command = [str(executable),'scan','--config',str(rules),'--metrics','off','--disable-version-check',
               '--oss-only','--strict','--disable-nosem','--no-git-ignore','--no-rewrite-rule-ids',
               '--max-target-bytes','0','--timeout','30','--json','--output',str(report_path),*targets]
    result = subprocess.run(command, cwd=ROOT, env=env, shell=False, timeout=600)
    if result.returncode:
        raise ValueError('Scanner failed or reported incomplete parsing (exit ' + str(result.returncode) + ')')
    report = json.loads(report_path.read_text())
    exceptions = json.loads((ROOT / '.github/security-exceptions.json').read_text())['exceptions']
    summary = evaluate(report,manifest,targets,exceptions,ROOT,lock['engine_version'])
    (work / 'gate.json').write_text(json.dumps(summary,indent=2))
    print('Security scan: ' + str(summary['scanned_source_files']) + ' source files, ' + str(summary['rules'])
          + ' rules, ' + str(summary['findings']) + ' findings, ' + str(len(summary['reviewed']))
          + ' exact reviewed exceptions, ' + str(len(summary['blocking'])) + ' blocking high/critical-impact findings.')
    for finding in summary['blocking']:
        print(finding['path'] + ':' + str(finding['start']['line']) + ': ' + finding['check_id'])
    return 1 if summary['blocking'] else 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print('Security gate failed: ' + str(error),file=sys.stderr)
        raise SystemExit(2)
