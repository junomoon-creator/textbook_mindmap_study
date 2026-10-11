import json
import pytest
from mindmapping_study.pipeline import LearningResult, artifact_base, document_id, parse_json_response, save_result, get_cached, validate_pages
from mindmapping_study.storage import Storage

SAMPLE = {"chapter_title": "MOSFET", "concepts": [
    {"id": "mos", "title_ko": "MOSFET", "source_pages": [1], "note_md": "# MOSFET\n기본 구조와 동작 원리를 설명합니다."},
    {"id": "gm", "title_ko": "트랜스컨덕턴스", "parent_id": "mos", "source_pages": [2], "note_md": "# gm\n소신호 드레인 전류 변화량을 설명합니다."}
]}

def test_roundtrip(tmp_path):
    s = Storage(backend="local", prefix="test", local_dir=tmp_path)
    result = LearningResult.model_validate(SAMPLE)
    base = artifact_base(document_id(b"pdf"), 1, 2, "claude")
    save_result(s, base, result, {"input_tokens": 5, "output_tokens": 10}, document_id(b"pdf"), 1, 2, "claude")
    assert get_cached(s, base) == result
    assert s.get(base + "/notes/gm.md").startswith(b"# gm")
    assert len(json.loads(s.get(base + "/mindmap.json"))["edges"]) == 1

def test_bad_pages():
    with pytest.raises(ValueError):
        validate_pages(LearningResult.model_validate(SAMPLE), 3, 4)

def test_cycle_rejected():
    bad = json.loads(json.dumps(SAMPLE))
    bad["concepts"][0]["parent_id"] = "gm"
    with pytest.raises(ValueError):
        LearningResult.model_validate(bad)

def test_markdown_fence():
    assert parse_json_response("```json\n" + json.dumps(SAMPLE) + "\n```").chapter_title == "MOSFET"

def test_traversal_rejected(tmp_path):
    s = Storage(backend="local", local_dir=tmp_path)
    with pytest.raises(ValueError):
        s.put("../secrets", b"no")


def test_discover_and_register(tmp_path):
    import fitz
    from mindmapping_study.catalog import discover_pdfs, register_pdf, registered_documents
    s = Storage(backend='local', prefix='test', local_dir=tmp_path)
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), 'Chapter 1: Test content')
    doc.set_toc([[1, 'Chapter 1', 1]])
    pdf = doc.tobytes()
    doc.close()
    s.put('raw/textbooks/technical-book.pdf', pdf, 'application/pdf')
    assert discover_pdfs(s) == ['raw/textbooks/technical-book.pdf']
    doc_id, meta = register_pdf(s, raw_key='raw/textbooks/technical-book.pdf')
    assert meta['toc'][0]['title'] == 'Chapter 1'
    assert registered_documents(s)[doc_id]['pages'] == 1
    doc_id_again, _ = register_pdf(s, raw_key='raw/textbooks/technical-book.pdf')
    assert doc_id == doc_id_again


def test_registration_rejects_outside_prefix(tmp_path):
    from mindmapping_study.catalog import register_pdf
    s = Storage(backend='local', prefix='test', local_dir=tmp_path)
    with pytest.raises(ValueError):
        register_pdf(s, raw_key='documents/a/original.pdf')
