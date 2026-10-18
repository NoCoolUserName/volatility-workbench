"""Report-turn provenance from adapter events, never inferred from report prose."""
from __future__ import annotations

import re


TOKEN_FIELDS = ('totalTokens', 'inputTokens', 'cachedInputTokens', 'outputTokens',
                'reasoningOutputTokens', 'cacheWriteInputTokens')


def token_counts(value):
    if not isinstance(value, dict) or type(value.get('totalTokens')) is not int:
        return None
    counts = {key: value[key] for key in TOKEN_FIELDS if key in value}
    if any(type(n) is not int or n < 0 for n in counts.values()):
        return None
    return counts


def label(value):
    # Provider metadata is untrusted text; keep it out of Markdown syntax.
    return value if isinstance(value, str) and re.fullmatch(r'[\w./:+-]{1,200}', value) else None


def begin(provider, settings):
    model = label(settings.get('model'))
    return {'schema': 'report-generation/1', 'provider': provider, 'status': 'in_progress',
            'model': model, 'models': [model] if model else [],
            'model_source': 'thread_response' if provider == 'codex' else 'configured_request',
            'reasoning_effort': label(settings.get('reasoningEffort') if provider == 'codex' else settings.get('reasoning_effort')),
            'reasoning_effort_source': 'thread_response' if provider == 'codex' else 'configured_request',
            'token_usage': {'status': 'unavailable', 'scope': 'report_generation_turn',
                'total_tokens': None, 'reason': 'No usable provider usage received.'}}


def usage(generation, total, baseline):
    """Difference cumulative thread counters, never sum duplicate/last events."""
    total = token_counts(total)
    if total is None:
        return
    record = {'status': 'unavailable', 'scope': 'report_generation_turn', 'total_tokens': None,
              'thread_total_tokens': total['totalTokens'], 'thread_breakdown': total,
              'reason': 'No pre-turn counter recorded; thread total is not report-only usage.'}
    if baseline is not None:
        keys = set(total) & set(baseline)
        if 'totalTokens' in keys and all(total[k] >= baseline[k] for k in keys):
            delta = {k: total[k] - baseline[k] for k in keys}
            record.update(status='recorded', total_tokens=delta['totalTokens'], breakdown=delta,
                          reason='Provider cumulative counters minus the recorded pre-turn counters.')
        else:
            record['reason'] = 'Provider counters reset or decreased; report-only usage is unknown.'
    generation['token_usage'] = record


def summary(generation):
    if not generation:
        return 'Model, reasoning effort and token usage were not recorded for this report.'
    models = [label(m) for m in generation.get('models', []) if label(m)]
    model = ', '.join('`' + m + '`' for m in models) or 'an unrecorded model'
    if generation.get('model_source') == 'configured_request':
        model += ' (configured model; effective model not reported)'
    effort = label(generation.get('reasoning_effort'))
    text = 'with ' + model + ' (reasoning effort: ' + ('`' + effort + '`' if effort else 'not reported') + ')'
    if effort and generation.get('reasoning_effort_source') == 'configured_request':
        text += ' (requested effort; effective effort not reported)'
    counts = generation.get('token_usage', {})
    total = counts.get('total_tokens')
    if counts.get('status') == 'recorded' and type(total) is int:
        text += f' and {total:,} tokens (report-generation turn'
        text += '; final provider count).' if generation.get('status') == 'completed' else '; provisional count).'
    elif type(counts.get('thread_total_tokens')) is int:
        text += f"; {counts['thread_total_tokens']:,} tokens for the case thread through this turn; report-only usage unavailable."
    else:
        text += '; token usage not reported.'
    return text


def markdown(text, generation):
    """Add portable provenance in the preamble; regenerate only our own line."""
    lines = text.splitlines()
    end = next((i for i, line in enumerate(lines) if line.startswith('## ')), len(lines))
    preamble = [line for line in lines[:end] if not line.startswith('AI generation: ')]
    while preamble and not preamble[-1].strip():
        preamble.pop()
    return '\n'.join(preamble + ['', 'AI generation: ' + summary(generation), ''] + lines[end:]) + '\n'
