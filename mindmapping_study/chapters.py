"""Bookmark-based chapter/section selection with safe fallback for bookmarkless PDFs."""
import json
import re

CATALOG_VERSION = 1


def build_outline(toc, total_pages):
    """Normalize bookmarks and compute inclusive page spans.

    A node ends before the next bookmark at the same or shallower depth.
    A parent with children remains selectable as an entire chapter.
    """
    valid = []
    for item in toc or []:
        try:
            level, page = int(item['level']), int(item['page'])
            title = str(item['title']).strip()
        except (KeyError, ValueError, TypeError):
            continue
        if level < 1 or not title or not 1 <= page <= total_pages:
            continue
        valid.append({'level': level, 'title': title, 'start': page})
    # Bookmark ordering is authoritative; ignore backward page jumps for safe ranges.
    result = []
    for i, item in enumerate(valid):
        next_page = next((n['start'] for n in valid[i+1:]
                          if n['level'] <= item['level'] and n['start'] > item['start']), total_pages + 1)
        end = min(total_pages, next_page - 1)
        if end < item['start']:
            continue
        result.append({**item, 'end': end, 'id': f'bm-{i}-{item["start"]}'})
    return result


def chapter_sections(outline):
    """Group direct descendants under top-level bookmark entries."""
    if not outline:
        return []
    root_level = min(x['level'] for x in outline)
    chapters = []
    for index, node in enumerate(outline):
        if node['level'] == root_level:
            chapters.append({**node, 'sections': []})
        elif chapters:
            chapter = chapters[-1]
            # Only direct children of chapter; grandchildren are selectable too via flat listing.
            chapter['sections'].append(node)
    return chapters


def section_candidates(pages):
    """Suggest possible section headings from text when PDF has no bookmarks.

    These are suggestions, NOT verified chapter boundaries; user must confirm.
    """
    suggestions = []
    seen = set()
    heading = re.compile(r'^\s*(?:chapter\s+\d+|(?:\d+\.){1,3}\d*\s+\S.{2,85}|(?:[IVX]+\.)\s+\S.{2,85})\s*$', re.I)
    for page in pages:
        for line in page.get('text', '').splitlines()[:30]:
            line = line.strip()
            if heading.match(line) and (page['page'], line) not in seen:
                suggestions.append({'page': page['page'], 'title': line})
                seen.add((page['page'], line))
                break
    return suggestions[:150]


def load_outline(storage, doc_id, meta):
    """Cache derived bookmark outline in GCS; never overwrite registered PDF metadata."""
    key = f'documents/{doc_id}/chapter_index_v{CATALOG_VERSION}.json'
    cached = storage.get(key)
    if cached:
        try:
            payload = json.loads(cached)
            if payload.get('total_pages') == meta['pages']:
                return payload['outline']
        except (ValueError, KeyError, TypeError):
            pass
    outline = build_outline(meta.get('toc', []), int(meta['pages']))
    storage.put(key, json.dumps({'total_pages': meta['pages'], 'outline': outline}, ensure_ascii=False).encode('utf-8'), 'application/json')
    return outline


def inferred_outline(pages, total_pages):
    """Heuristic headings for PDFs without bookmarks. Boundaries are estimates."""
    pattern = re.compile(
        r'^\s*(?:(?:chapter|chap\.?|section)\s+\d+(?:\.\d+)*[\s.:\-]+\S.{2,90}'
        r'|\d+(?:\.\d+){0,3}[.\s]+[A-Za-z가-힣][^\n]{3,90}'
        r'|(?:[IVX]{1,5})[.\s]+[A-Z][^\n]{3,90})\s*$', re.I)
    raw = []
    seen = set()
    for p in pages:
        for line in p.get('text', '').splitlines()[:45]:
            line = ' '.join(line.strip().split())
            if not pattern.match(line) or len(line) > 105:
                continue
            # Avoid multiple occurrences of the same heading in page headers.
            key = line.casefold()
            if key not in seen:
                seen.add(key)
                m = re.match(r'^(?:chapter|chap\.?|section)\s+(\d+(?:\.\d+)*)|^(\d+(?:\.\d+)*)', line, re.I)
                numbering = (m.group(1) or m.group(2)) if m else None
                level = numbering.count('.') + 1 if numbering else 1
                raw.append({'level': level, 'title': line, 'page': int(p['page'])})
            break
    return build_outline(raw[:200], total_pages)


def load_inferred_outline(storage, doc_id, pages, total_pages):
    """Save a separate derived index; leave the original PDF and bookmark cache intact."""
    key = f'documents/{doc_id}/inferred_outline_v2.json'
    cached = storage.get(key)
    if cached:
        try:
            payload = json.loads(cached)
            if payload.get('total_pages') == total_pages:
                return payload['outline']
        except (ValueError, TypeError, KeyError):
            pass
    outline = inferred_outline(pages, total_pages)
    storage.put(key, json.dumps({'total_pages': total_pages, 'outline': outline}, ensure_ascii=False).encode(), 'application/json')
    return outline
