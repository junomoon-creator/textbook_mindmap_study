import json
from mindmapping_study.incremental import split_ranges, merge_results, generate_chunked
from mindmapping_study.pipeline import LearningResult, artifact_base, get_cached
from mindmapping_study.chapters import inferred_outline, chapter_sections
from mindmapping_study.storage import Storage


def sample(page):
    return LearningResult.model_validate({'chapter_title': f'Part {page}', 'concepts': [
        {'id': 'topic', 'title_ko': f'주제 {page}', 'source_pages': [page],
         'note_md': '주제에 대한 상세 학습 설명입니다. 충분한 설명.'}]})


def test_split_ranges():
    assert split_ranges(26, 44, 5) == [(26,30), (31,35), (36,40), (41,44)]


def test_merge_preserves_ids_and_sources():
    merged = merge_results([sample(1), sample(2)], 1, 2)
    assert len(merged.concepts) == 5
    assert merged.concepts[2].id == 'part1_topic'
    assert merged.concepts[4].id == 'part2_topic'


def test_chunk_cache_resume(tmp_path, monkeypatch):
    import mindmapping_study.incremental as inc
    calls = []
    def fake(pages, start, end, model, client=None):
        calls.append((start, end))
        return sample(start), {'input_tokens': 10, 'output_tokens': 5}
    monkeypatch.setattr(inc, 'generate_learning', fake)
    storage = Storage(backend='local', prefix='test', local_dir=tmp_path)
    pages = [{'page': i, 'text': 'text'} for i in range(1, 7)]
    result, usage = generate_chunked(storage, pages, 'doc', 1, 6, 'model', chunk_size=3)
    assert calls == [(1,3), (4,6)]
    assert usage['input_tokens'] == 20
    result2, usage2 = generate_chunked(storage, pages, 'doc', 1, 6, 'model', chunk_size=3)
    assert len(calls) == 2
    assert usage2['input_tokens'] == 0
    assert result2 == result


def test_bookmarkless_outline():
    pages = [{'page': 1, 'text': 'I. INTRODUCTION\nHello'},
             {'page': 2, 'text': 'II. EXPERIMENTAL RESULTS\nHello'},
             {'page': 3, 'text': 'Conclusions'}]
    outline = inferred_outline(pages, 3)
    assert len(outline) == 2
    assert outline[0]['end'] == 1
    assert outline[1]['end'] == 3
    assert len(chapter_sections(outline)) == 2
