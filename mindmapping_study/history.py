"""Durable, append-only per-API-call audit and study history stored in GCS/local Storage."""
import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal


def _now():
    return datetime.now(timezone.utc).isoformat()


def _rate(model, direction):
    # Explicit configuration is required: model pricing varies over time and by tier.
    env = 'CLAUDE_INPUT_USD_PER_MTOK' if direction == 'input' else 'CLAUDE_OUTPUT_USD_PER_MTOK'
    value = os.getenv(env, '').strip()
    if not value:
        return None
    rate = Decimal(value)
    if rate < 0:
        raise ValueError(env + ' must be non-negative')
    return rate


def estimate_cost(model, input_tokens, output_tokens):
    ir, out = _rate(model, 'input'), _rate(model, 'output')
    if ir is None or out is None:
        return {'estimated_cost_usd': None, 'input_usd_per_mtok': str(ir) if ir is not None else None,
                'output_usd_per_mtok': str(out) if out is not None else None, 'pricing_status': 'unconfigured'}
    cost = (Decimal(input_tokens) * ir + Decimal(output_tokens) * out) / Decimal(1000000)
    return {'estimated_cost_usd': float(cost), 'input_usd_per_mtok': str(ir),
            'output_usd_per_mtok': str(out), 'pricing_status': 'configured_estimate'}


def write_event(storage, *, event_type, document_id, page_start, page_end, model, status,
                input_tokens=0, output_tokens=0, artifact_key='', request_id='', error='', extra=None):
    timestamp = _now()
    event = {'event_id': uuid.uuid4().hex, 'timestamp': timestamp, 'event_type': event_type,
             'document_id': document_id, 'page_start': int(page_start), 'page_end': int(page_end),
             'model': model, 'status': status, 'input_tokens': int(input_tokens),
             'output_tokens': int(output_tokens), 'artifact_key': artifact_key,
             'request_id': request_id, 'error': str(error)[:1000],
             **estimate_cost(model, input_tokens, output_tokens)}
    if extra:
        event['extra'] = extra
    # One object per event; no shared JSON index and no concurrent overwrite.
    key = f"history/events/{timestamp[:10]}/{event['event_id']}.json"
    storage.put(key, json.dumps(event, ensure_ascii=False, indent=2).encode(), 'application/json')
    return event


class _Messages:
    def __init__(self, owner, wrapped):
        self.owner, self.wrapped = owner, wrapped

    def create(self, **kwargs):
        try:
            message = self.wrapped.create(**kwargs)
        except Exception as exc:
            self.owner.log(status='api_error', model=kwargs.get('model', ''), error=exc)
            raise
        usage = getattr(message, 'usage', None)
        self.owner.log(status='completed', model=kwargs.get('model', ''),
                       input_tokens=getattr(usage, 'input_tokens', 0) or 0,
                       output_tokens=getattr(usage, 'output_tokens', 0) or 0,
                       request_id=getattr(message, 'id', '') or '',
                       extra={'stop_reason': getattr(message, 'stop_reason', None),
                              'cache_creation_input_tokens': getattr(usage, 'cache_creation_input_tokens', 0) or 0,
                              'cache_read_input_tokens': getattr(usage, 'cache_read_input_tokens', 0) or 0})
        return message


class TrackedClient:
    """Wrap Anthropic client without changing the existing pipeline or retry behavior."""
    def __init__(self, client, storage, event_type, document_id, start, end, artifact_key):
        self.client, self.storage = client, storage
        self.context = dict(event_type=event_type, document_id=document_id,
                            page_start=start, page_end=end, artifact_key=artifact_key)
        self.messages = _Messages(self, client.messages)

    def log(self, **kwargs):
        return write_event(self.storage, **self.context, **kwargs)


def list_events(storage, document_id=None):
    events = []
    for key in storage.list('history/events/'):
        if not key.endswith('.json'):
            continue
        try:
            event = json.loads(storage.get(key))
            if document_id is None or event.get('document_id') == document_id:
                events.append(event)
        except (ValueError, TypeError, UnicodeDecodeError):
            continue
    return sorted(events, key=lambda e: e.get('timestamp', ''), reverse=True)


def list_studies(storage, document_id=None):
    """Include completed legacy artifacts that predate history tracking."""
    studies = {}
    for key in storage.list('learning/'):
        if not key.endswith('/result.json'):
            continue
        base = key[:-len('/result.json')]
        parts = base.split('/')
        if len(parts) < 4 or (document_id and parts[1] != document_id):
            continue
        try:
            metadata = storage.get(base + '/generation_metadata.json')
            meta = json.loads(metadata) if metadata else {}
            studies[base] = {'artifact_key': base, 'document_id': parts[1],
                             'page_start': meta.get('page_start'), 'page_end': meta.get('page_end'),
                             'model': meta.get('model', ''), 'generated_at': meta.get('generated_at', ''),
                             'usage': meta.get('usage', {}), 'has_report': False}
        except (ValueError, TypeError, UnicodeDecodeError):
            continue
    for key in storage.list('learning/'):
        if key.endswith('/integrated/') or not key.endswith('/complete.json'):
            continue
        parent = key.split('/integrated/')[0]
        if parent in studies:
            studies[parent]['has_report'] = True
    return sorted(studies.values(), key=lambda s: s['generated_at'], reverse=True)


def totals(events):
    return {'calls': len(events), 'input_tokens': sum(e.get('input_tokens', 0) for e in events),
            'output_tokens': sum(e.get('output_tokens', 0) for e in events),
            'estimated_cost_usd': sum(e['estimated_cost_usd'] for e in events if e.get('estimated_cost_usd') is not None),
            'unpriced_calls': sum(e.get('estimated_cost_usd') is None for e in events)}
