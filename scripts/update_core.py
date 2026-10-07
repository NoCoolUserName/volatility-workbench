#!/usr/bin/env python3
"""Propose a compatible immutable core pin; never install or merge anything."""
import argparse
import json
import re
from pathlib import Path
import tomllib
import urllib.request

REPO = 'NoCoolUserName/volatility-mcp'
PREFIX = 'volatility-mcp @ git+https://github.com/' + REPO + '.git@'


def version(tag):
    match = re.fullmatch(r'v(\d+)\.(\d+)\.(\d+)', tag)
    return tuple(map(int, match.groups())) if match else None


def select_release(releases, current, series):
    current_version = version('v' + current)
    eligible = [r for r in releases if not r.get('draft') and not r.get('prerelease')
                and (v := version(r.get('tag_name', ''))) is not None
                and '.'.join(map(str, v[:2])) == series and v > current_version]
    return max(eligible, key=lambda r: version(r['tag_name']), default=None)


def get_json(path):
    request = urllib.request.Request('https://api.github.com/repos/' + REPO + '/' + path,
                                     headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'volatility-workbench-updater'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def content(path, sha):
    import base64
    data = get_json('contents/' + path + '?ref=' + sha)
    return base64.b64decode(data['content']).decode()


def update(root, release, sha, lock, metadata, dry_run=False):
    if not re.fullmatch('[0-9a-f]{40}', sha): raise ValueError('Core commit must be a full SHA')
    new_version = release['tag_name'][1:]
    package = tomllib.loads(metadata)['project']
    if package['name'] != 'volatility-mcp' or package['version'] != new_version:
        raise ValueError('Release version disagrees with core package metadata')
    pins = [line.strip() for line in lock.splitlines() if line.strip() and not line.startswith('#')]
    if not all(re.fullmatch(r'[A-Za-z0-9_.-]+==[A-Za-z0-9_.+!-]+', p) for p in pins):
        raise ValueError('Core lock must contain exact package versions only')
    record_path = root/'core-dependency.json'
    record = json.loads(record_path.read_text())
    if select_release([release], record['version'], record['eligible_series']) is None:
        raise ValueError('Release is not a newer eligible core version')
    pyproject = (root/'pyproject.toml').read_text()
    old = PREFIX + record['commit']
    if pyproject.count(old) != 1: raise ValueError('Core pin does not match metadata')
    record.update(version=new_version, commit=sha)
    changes = {'pyproject.toml': pyproject.replace(old, PREFIX+sha),
               'requirements.lock.txt': '\n'.join(pins) + '\n' + PREFIX + sha + '\n',
               'core-dependency.json': json.dumps(record, indent=2)+'\n'}
    if not dry_run:
        for name, data in changes.items(): (root/name).write_text(data)
    return {'version': new_version, 'commit': sha, 'files': list(changes), 'dry_run': dry_run}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--fixture', type=Path, help='Offline fixture data, for testing selection/generation')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    record = json.loads((args.root/'core-dependency.json').read_text())
    fixture = json.loads(args.fixture.read_text()) if args.fixture else None
    releases = fixture['releases'] if fixture else get_json('releases?per_page=100')
    release = select_release(releases, record['version'], record['eligible_series'])
    if release is None:
        print('No newer eligible core release.'); return
    sha = fixture['commit'] if fixture else get_json('commits/'+release['tag_name'])['sha']
    lock = fixture['lock'] if fixture else content('requirements.lock.txt', sha)
    metadata = fixture['metadata'] if fixture else content('pyproject.toml', sha)
    print(json.dumps(update(args.root, release, sha, lock, metadata, args.dry_run), indent=2))


if __name__ == '__main__': main()
