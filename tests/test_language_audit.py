from mindmapping_study.report import ReportPlan, audit_report, LANGUAGE_POLICY
from mindmapping_study.pipeline import Concept, LearningResult, PROMPT_VERSION


def sample():
    result = LearningResult(chapter_title='Ring Oscillator', concepts=[
        Concept(id='inv', title_ko='Ring Oscillator', title_en='Ring Oscillator',
                source_pages=[3], note_md='Ring Oscillator를 분석합니다. [PDF p.3]')])
    plan = ReportPlan(title='Ring Oscillator', overview_ko='설명', terms=[
        {'term':'Propagation Delay', 'definition_ko':'Stage를 지나는 신호 전달에 필요한 시간입니다.'}])
    return result, plan


def test_language_policy_contains_required_contract():
    for token in ['Lithography', 'Threshold Voltage', 'Parasitic Capacitance',
                  'Propagation Delay', 'Process Variation', 'equation symbols',
                  'cell names', 'Terminology Glossary']:
        assert token in LANGUAGE_POLICY
    assert PROMPT_VERSION == 'v7-english-terms-strict'


def test_audit_catches_translated_term_and_invalid_citation():
    result, plan = sample()
    audit = audit_report('노광 때문에 발생. [PDF p.99]', plan, result)
    types = {item['type'] for item in audit['issues']}
    assert 'translated_technical_term' in types
    assert 'unverified_page_reference' in types
    assert not audit['passed']


def test_audit_accepts_english_terms_with_grounded_page():
    result, plan = sample()
    audit = audit_report('Lithography와 Propagation Delay를 설명합니다. [PDF p.3]', plan, result)
    assert audit['passed']


def test_audit_flags_missing_glossary_and_references():
    result, _ = sample()
    plan = ReportPlan(title='Test', overview_ko='설명', terms=[])
    issues = {i['type'] for i in audit_report('기술 설명', plan, result)['issues']}
    assert {'missing_glossary', 'missing_pdf_references'} <= issues
