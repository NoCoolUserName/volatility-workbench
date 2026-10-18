"""Model picker metadata; provider capabilities remain authoritative."""
from __future__ import annotations

import re

DEFAULT_MODEL = 'gpt-6-astra'
DEFAULT_EFFORT = 'high'


def model_name(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 200 or any(ord(c) < 32 for c in value):
        raise ValueError('A model identifier of at most 200 characters is required')
    return value.strip()


def reasoning_effort(value):
    if value in (None, ''):
        return None
    if not isinstance(value, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,31}', value):
        raise ValueError('Invalid reasoning effort')
    return value


def codex_models(entries):
    """Keep catalog order and each model's advertised effort order."""
    if not isinstance(entries, list):
        raise ValueError('Codex model catalog is invalid')
    result, seen = [], set()
    for entry in entries:
        if not isinstance(entry, dict) or entry.get('hidden'):
            continue
        try:
            model = model_name(entry.get('model'))
            efforts = [reasoning_effort(item.get('reasoningEffort'))
                       for item in entry.get('supportedReasoningEfforts', []) if isinstance(item, dict)]
            efforts = list(dict.fromkeys(e for e in efforts if e))
            default = reasoning_effort(entry.get('defaultReasoningEffort'))
        except (ValueError, TypeError):
            continue
        if model in seen:
            continue
        seen.add(model)
        result.append({'model': model, 'label': str(entry.get('displayName') or model)[:200],
                       'efforts': efforts, 'default_effort': default if default in efforts else next(iter(efforts), None)})
    return result


def same_model_settings(left, right):
    return all(left.get(key) == right.get(key) for key in
               ('provider', 'endpoint', 'model', 'reasoning_effort', 'codex_executable'))
