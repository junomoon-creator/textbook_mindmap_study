"""Approximate reading order using earliest cited PDF page; cache compatible."""
from collections import defaultdict


def is_structural(concept):
    return concept.id == "chapter_root" or concept.id.endswith("_group")


def reading_sequence(result):
    """Stable page-first order. Within-page sequence is not author-verified."""
    indexed = [(i, c) for i, c in enumerate(result.concepts) if not is_structural(c)]
    return [c for _, c in sorted(indexed, key=lambda pair: (min(pair[1].source_pages), pair[0]))]


def page_groups(result):
    grouped = defaultdict(list)
    for concept in reading_sequence(result):
        grouped[min(concept.source_pages)].append(concept)
    return [(page, grouped[page]) for page in sorted(grouped)]
