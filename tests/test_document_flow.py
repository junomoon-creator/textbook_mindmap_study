from mindmapping_study.pipeline import LearningResult
from mindmapping_study.document_flow import reading_sequence, page_groups


def test_document_flow_page_order_and_stable_ties():
    result = LearningResult.model_validate({'chapter_title': 'Test', 'concepts': [
        {'id': 'late', 'title_ko': 'Later', 'source_pages': [9], 'note_md': 'long enough study note content'},
        {'id': 'same1', 'title_ko': 'First', 'source_pages': [2], 'note_md': 'long enough study note content'},
        {'id': 'same2', 'title_ko': 'Second', 'source_pages': [2, 4], 'note_md': 'long enough study note content'},
    ]})
    assert [c.id for c in reading_sequence(result)] == ['same1', 'same2', 'late']
    assert [p for p, _ in page_groups(result)] == [2, 9]


def test_document_flow_excludes_chunk_structural_nodes():
    result = LearningResult.model_validate({'chapter_title': 'Test', 'concepts': [
        {'id': 'chapter_root', 'title_ko': 'Root', 'source_pages': [1], 'note_md': 'long enough study note content'},
        {'id': 'part1_group', 'title_ko': 'Group', 'source_pages': [1], 'parent_id': 'chapter_root', 'note_md': 'long enough study note content'},
        {'id': 'part1_topic', 'title_ko': 'Topic', 'source_pages': [3], 'parent_id': 'part1_group', 'note_md': 'long enough study note content'},
    ]})
    assert [c.id for c in reading_sequence(result)] == ['part1_topic']
