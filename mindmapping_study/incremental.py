"""Bounded chunk analysis with resumable GCS checkpoints and safe deterministic merge."""
import hashlib
import json
import os
from .pipeline import Concept, LearningResult, artifact_base, generate_learning, get_cached, save_result


def split_ranges(start, end, chunk_size=5):
    if not 1 <= start <= end or chunk_size < 1:
        raise ValueError('Invalid chunk range or size')
    return [(i, min(end, i + chunk_size - 1)) for i in range(start, end + 1, chunk_size)]


def merge_results(results, start, end):
    """Preserve all concepts and links; create a root, not fabricated cross-chunk edges."""
    if not results:
        raise ValueError('No chunks to merge')
    if len(results) == 1:
        return results[0]
    concepts = [Concept(id='chapter_root', title_ko=f'PDF p.{start}–{end} 통합 개요',
                        source_pages=[start], note_md=f'# 통합 개요\n\nPDF p.{start}–{end}의 구간별 분석 결과입니다. 각 하위 그룹을 선택해 학습하세요.')]
    for idx, result in enumerate(results):
        prefix = f'part{idx+1}_'
        ids = {c.id: prefix + c.id for c in result.concepts}
        group_id = f'part{idx+1}_group'
        pages = sorted({p for c in result.concepts for p in c.source_pages})
        concepts.append(Concept(id=group_id, title_ko=result.chapter_title,
                                parent_id='chapter_root', source_pages=pages[:1] or [start],
                                note_md=f'# {result.chapter_title}\n\n구간별 분석 그룹입니다.'))
        for c in result.concepts:
            payload = c.model_dump()
            payload['id'] = ids[c.id]
            payload['parent_id'] = ids[c.parent_id] if c.parent_id else group_id
            payload['related_ids'] = [ids[r] for r in c.related_ids]
            concepts.append(Concept.model_validate(payload))
    return LearningResult(chapter_title=f'PDF p.{start}–{end} 통합 학습', concepts=concepts)


def generate_chunked(storage, pages, doc_id, start, end, model, chunk_size=5,
                     client=None, progress=None):
    """Cache successful subranges; recursively split a failed subrange if needed."""
    if not 1 <= start <= end <= len(pages):
        raise ValueError('Invalid page range')
    if not 1 <= chunk_size <= 20:
        raise ValueError('chunk_size must be 1..20')
    total_usage = {'input_tokens': 0, 'output_tokens': 0}
    completed = []
    def run_range(a, b):
        base = artifact_base(doc_id, a, b, model)
        cached = get_cached(storage, base)
        if cached is not None:
            return [cached]
        try:
            result, usage = generate_learning(pages, a, b, model, client=client)
            save_result(storage, base, result, usage, doc_id, a, b, model)
            for key in total_usage:
                total_usage[key] += usage.get(key, 0)
            return [result]
        except (ValueError, RuntimeError) as exc:
            # Only retry smaller chunks for length/truncation problems; don't
            # conceal credential, API, or semantic validation failures.
            reason = str(exc).lower()
            if a == b or not any(s in reason for s in ('max_tokens', 'truncat', '100,000', '100000', 'token limit')):
                raise
            mid = (a + b) // 2
            return run_range(a, mid) + run_range(mid + 1, b)
    for a, b in split_ranges(start, end, chunk_size):
        completed.extend(run_range(a, b))
        if progress:
            progress(min(b, end), end)
    return merge_results(completed, start, end), total_usage
