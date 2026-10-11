import json
import fitz
from mindmapping_study.storage import Storage
from mindmapping_study.pipeline import Concept, LearningResult
from mindmapping_study.report import (ReportPlan, report_base, generate_integrated_report,
                                      load_integrated_report, render_html, _groups)


def sample():
    return LearningResult(chapter_title='RO', concepts=[
        Concept(id='a', title_ko='Ring Oscillator', title_en='Ring Oscillator', source_pages=[1],
                note_md='Ring Oscillator frequency depends on Stage delay. [PDF p.1]'),
        Concept(id='b', title_ko='Propagation Delay', title_en='Propagation Delay', source_pages=[2],
                parent_id='a', note_md='Propagation Delay impacts oscillation frequency. [PDF p.2]')])


class MockClient:
    def __init__(self):
        self.calls = 0
        self.messages = self

    def create(self, **kwargs):
        self.calls += 1
        if 'Return ONLY valid JSON' in kwargs['system']:
            text = json.dumps({'title': 'Ring Oscillator Analysis', 'overview_ko': 'Stage 구조 분석',
                'terms': [{'term': 'Propagation Delay', 'definition_ko': '신호 전달에 걸리는 시간입니다.'}]})
        else:
            text = '## Ring Oscillator Mechanism\n\nPropagation Delay와 Frequency의 관계를 설명합니다. [PDF p.1] [PDF p.2]'
        class Obj: pass
        out = Obj(); out.text = text; out.type = 'text'
        msg = Obj(); msg.content = [out]; msg.stop_reason = 'end_turn'
        msg.usage = Obj(); msg.usage.input_tokens = 12; msg.usage.output_tokens = 20
        return msg


def test_report_generate_and_cache(tmp_path):
    storage = Storage(backend='local', prefix='mindmapping_study', local_dir=str(tmp_path))
    result = sample(); base = report_base('learning/doc/p1-2/v5', result)
    client = MockClient()
    report, plan, usage = generate_integrated_report(storage, base, result, 'test-model', client=client)
    assert client.calls == 2
    assert 'Propagation Delay' in report
    assert load_integrated_report(storage, base)[0] == report
    assert usage['input_tokens'] == 24
    # Deleting only the final marker simulates interrupted finalization.
    (tmp_path/'mindmapping_study'/base/'complete.json').unlink()
    generate_integrated_report(storage, base, result, 'test-model', client=client)
    assert client.calls == 2


def test_html_embeds_source_and_escapes_glossary():
    result = sample()
    doc = fitz.open(); doc.new_page(); doc.new_page(); pdf = doc.tobytes(); doc.close()
    plan = ReportPlan(title='RO <script>alert(1)</script>', overview_ko='설명', terms=[
        {'term':'Threshold Voltage', 'definition_ko':'전압에 대한 <script>설명</script>'}])
    out = render_html('# Test\n\n[PDF p.1]', plan, result, pdf)
    assert '<meta charset="UTF-8">' in out
    assert 'data:image/png;base64,' in out
    assert '<script>' not in out
    assert '<details' in out
    assert 'Concept Overview Diagram' in out


def test_report_base_changes_when_result_changes():
    a = sample(); b = sample(); b.concepts[0].note_md += ' Changed.'
    assert report_base('base', a) != report_base('base', b)


def test_grouping():
    assert len(_groups(sample(), 1)) == 2
