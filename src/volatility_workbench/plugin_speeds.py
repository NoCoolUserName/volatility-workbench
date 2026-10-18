"""Bounded runtime estimates from completed, saved physical plugin runs."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re

MAX_SAMPLES = 10
MAX_MANIFESTS = 3000
MAX_MANIFEST_BYTES = 128 * 1024
PLUGIN = re.compile(r'^[A-Za-z][\w]*(?:\.[A-Za-z][\w]*)+$')


def valid_history(value):
    if not isinstance(value, dict):
        return {}
    clean = {}
    for name, samples in value.items():
        if not isinstance(name, str) or len(name) > 256 or not PLUGIN.fullmatch(name) or not isinstance(samples, list):
            continue
        accepted = []
        for item in samples[:MAX_SAMPLES]:
            if not isinstance(item, dict):
                continue
            seconds = item.get('duration_seconds')
            if (not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or not math.isfinite(seconds)
                    or not 0 < seconds <= 24 * 3600 or not instant(item.get('finished_at'))):
                continue
            if not all(isinstance(item.get(key), str) and 0 < len(item[key]) <= 256
                       for key in ('case_id', 'run_id')):
                continue
            accepted.append({key:item[key] for key in ('case_id','run_id','finished_at','duration_seconds')})
        if accepted:
            clean[name] = accepted
    return clean


def instant(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else None


def saved_runs(case_root, case_id, after_mtime_ns=0):
    """Read only small run manifests in the case's own analysis directory."""
    root = Path(case_root) / 'analysis'
    paths = []
    for image in root.iterdir() if root.exists() else ():
        runs = image / 'runs'
        if image.is_symlink() or not image.is_dir() or runs.is_symlink() or not runs.is_dir():
            continue
        for folder in runs.iterdir():
            path = folder / 'manifest.json'
            if folder.is_symlink() or not folder.is_dir() or path.is_symlink():
                continue
            try:
                details = path.stat()
                if 0 < details.st_size <= MAX_MANIFEST_BYTES and details.st_mtime_ns > after_mtime_ns:
                    paths.append((details.st_mtime_ns, path))
            except OSError:
                continue
    results = []
    for mtime_ns, path in sorted(paths, reverse=True)[:MAX_MANIFESTS]:
        try:
            record = json.loads(path.read_text())
        except (OSError, UnicodeError, ValueError):
            continue
        if not isinstance(record, dict) or record.get('status') != 'success' or record.get('run_id') != path.parent.name:
            continue
        plugin = record.get('plugin')
        start, finish = instant(record.get('started_at')), instant(record.get('completed_at'))
        if not isinstance(plugin, str) or len(plugin) > 256 or not PLUGIN.fullmatch(plugin) or not start or not finish:
            continue
        seconds = (finish - start).total_seconds()
        if not 0 < seconds <= 24 * 3600:
            continue
        results.append({'plugin':plugin, 'run_id':record['run_id'], 'case_id':case_id,
                        'source_mtime_ns':mtime_ns,
                        'finished_at':finish.isoformat(), 'duration_seconds':seconds})
    return results


def merge(history, runs):
    """Keep the ten newest successful executions per plugin, deduplicated by run."""
    updated = {name:list(samples) for name, samples in history.items()}
    for run in runs:
        name = run['plugin']
        samples = updated.setdefault(name, [])
        key = (run['case_id'], run['run_id'])
        if not any((item['case_id'], item['run_id']) == key for item in samples):
            samples.append({k:run[k] for k in ('case_id','run_id','finished_at','duration_seconds')})
            samples.sort(key=lambda item:(item['finished_at'],item['case_id'],item['run_id']), reverse=True)
            del samples[MAX_SAMPLES:]
    return updated


def summary(history):
    return {name:{'samples':len(samples),
                  'average_seconds':sum(item['duration_seconds'] for item in samples) / len(samples)}
            for name, samples in history.items() if samples}
