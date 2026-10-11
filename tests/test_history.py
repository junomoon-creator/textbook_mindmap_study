import json
from types import SimpleNamespace
from mindmapping_study.history import TrackedClient, estimate_cost, list_events, list_studies, totals
from mindmapping_study.storage import Storage


def test_cost_unknown(monkeypatch):
    monkeypatch.delenv('CLAUDE_INPUT_USD_PER_MTOK', raising=False)
    monkeypatch.delenv('CLAUDE_OUTPUT_USD_PER_MTOK', raising=False)
    assert estimate_cost('any', 100, 200)['estimated_cost_usd'] is None


def test_tracking_and_study_restore(tmp_path, monkeypatch):
    monkeypatch.setenv('CLAUDE_INPUT_USD_PER_MTOK', '3')
    monkeypatch.setenv('CLAUDE_OUTPUT_USD_PER_MTOK', '15')
    storage = Storage(backend='local', prefix='test', local_dir=str(tmp_path))
    class FakeMessages:
        def create(self, **kwargs):
            return SimpleNamespace(id='msg_1', usage=SimpleNamespace(input_tokens=1000, output_tokens=200), stop_reason='end_turn')
    tracked = TrackedClient(SimpleNamespace(messages=FakeMessages()), storage, 'mindmap', 'doc', 1, 5, 'learning/doc/p1-5/v6')
    tracked.messages.create(model='model', messages=[])
    events = list_events(storage)
    assert len(events) == 1
    assert events[0]['estimated_cost_usd'] == 0.006
    assert totals(events)['calls'] == 1
    base = 'learning/doc/p1-5/v6'
    storage.put(base + '/result.json', b'{}')
    storage.put(base + '/generation_metadata.json', json.dumps({'page_start': 1, 'page_end': 5, 'model': 'model'}).encode())
    assert list_studies(storage)[0]['artifact_key'] == base


def test_api_error_is_recorded(tmp_path):
    storage = Storage(backend='local', prefix='test', local_dir=str(tmp_path))
    class BadMessages:
        def create(self, **kwargs):
            raise RuntimeError('network unavailable')
    tracked = TrackedClient(SimpleNamespace(messages=BadMessages()), storage, 'report', 'doc', 1, 2, 'key')
    try:
        tracked.messages.create(model='model')
    except RuntimeError:
        pass
    assert list_events(storage)[0]['status'] == 'api_error'
