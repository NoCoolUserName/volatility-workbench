#!/usr/bin/env python3
"""Install/verify the exact locked core revision, including same-version upgrades."""
import json
from importlib.metadata import distribution, PackageNotFoundError
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'NoCoolUserName/volatility-mcp'
URL = 'https://github.com/' + REPOSITORY + '.git'


def installed_commit():
    try:
        raw = distribution('volatility-mcp').read_text('direct_url.json')
        data = json.loads(raw) if raw else {}
    except (PackageNotFoundError, ValueError):
        return None
    return data.get('vcs_info', {}).get('commit_id') if data.get('url') == URL else None


def install(root=ROOT, python=sys.executable):
    record = json.loads((root / 'core-dependency.json').read_text())
    commit = record['commit']
    if record['repository'] != REPOSITORY or not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('Expected an immutable core revision in the configured repository')
    if installed_commit() != commit:
        subprocess.run([python, '-I', '-m', 'pip', 'install', '--no-deps', '--force-reinstall',
                        'volatility-mcp @ git+' + URL + '@' + commit], shell=False, check=True)
    if installed_commit() != commit:
        raise RuntimeError('Installed core provenance does not match the requested pin')
    return commit


if __name__ == '__main__':
    print('Verified core commit: ' + install())
