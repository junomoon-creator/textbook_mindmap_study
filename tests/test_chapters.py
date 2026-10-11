import json
from mindmapping_study.chapters import build_outline, chapter_sections, load_outline, section_candidates
from mindmapping_study.pipeline import artifact_base
from mindmapping_study.storage import Storage

TOC = [
    {'level': 1, 'title': 'Chapter 1', 'page': 1},
    {'level': 2, 'title': '1.1 Intro', 'page': 2},
    {'level': 3, 'title': '1.1.1 Details', 'page': 4},
    {'level': 2, 'title': '1.2 Methods', 'page': 7},
    {'level': 1, 'title': 'Chapter 2', 'page': 11},
    {'level': 2, 'title': '2.1 Results', 'page': 12},
]

def test_nested_ranges():
    outline = build_outline(TOC, 20)
    assert [(x['start'], x['end']) for x in outline] == [(1,10),(2,6),(4,6),(7,10),(11,20),(12,20)]
    chapters = chapter_sections(outline)
    assert len(chapters) == 2
    assert [x['title'] for x in chapters[0]['sections']] == ['1.1 Intro','1.1.1 Details','1.2 Methods']

def test_bad_and_empty_bookmarks():
    assert build_outline([], 10) == []
    assert build_outline([{'level': 1, 'title': 'Invalid', 'page': 100}], 10) == []

def test_outline_gcs_compatible_cache(tmp_path):
    store = Storage(backend='local', prefix='test', local_dir=tmp_path)
    meta = {'pages': 20, 'toc': TOC}
    outline = load_outline(store, 'hash123', meta)
    assert len(outline) == 6
    assert store.get('documents/hash123/chapter_index_v1.json')
    assert load_outline(store, 'hash123', {'pages':20, 'toc': []}) == outline
    assert artifact_base('hash123', 1, 10, 'sonnet') == artifact_base('hash123', outline[0]['start'], outline[0]['end'], 'sonnet')

def test_fallback_candidates():
    pages = [{'page':1,'text':'1. Introduction\nSome text'}, {'page':3,'text':'2. Methods\nOther text'}]
    assert [x['page'] for x in section_candidates(pages)] == [1,3]
