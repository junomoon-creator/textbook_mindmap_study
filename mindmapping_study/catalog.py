"""Discover uploaded PDFs and register them without re-uploading to GCS."""
import json
from pathlib import PurePosixPath
from .pipeline import document_id, extract_pages

RAW_PREFIX = 'raw/textbooks/'


def discover_pdfs(storage):
    return sorted(p for p in storage.list(RAW_PREFIX) if p.lower().endswith('.pdf'))


def registered_documents(storage):
    keys = storage.list('documents/')
    ids = sorted({k.split('/')[1] for k in keys if len(k.split('/')) == 3 and k.endswith('/metadata.json')})
    result = {}
    for doc_id in ids:
        data = storage.get(f'documents/{doc_id}/metadata.json')
        if data:
            result[doc_id] = json.loads(data)
    return result


def register_pdf(storage, raw_key=None, pdf_bytes=None, filename=None):
    """Import a PDF from an existing GCS object or a browser upload."""
    if raw_key is not None:
        if raw_key not in discover_pdfs(storage):
            raise ValueError('PDF is not in the approved textbook prefix')
        pdf_bytes = storage.get(raw_key)
        filename = PurePosixPath(raw_key).name
    if not pdf_bytes or not filename:
        raise ValueError('PDF and filename are required')
    if not pdf_bytes.startswith(b'%PDF-'):
        raise ValueError('Not a valid PDF header')
    doc_id = document_id(pdf_bytes)
    existing = storage.get(f'documents/{doc_id}/metadata.json')
    if existing:
        return doc_id, json.loads(existing)
    pages = extract_pages(pdf_bytes)
    if not pages:
        raise ValueError('PDF has no pages')
    from .pipeline import extract_toc
    toc = extract_toc(pdf_bytes)
    meta = {'name': filename, 'pages': len(pages), 'sha256': doc_id, 'source_key': raw_key, 'toc': toc}
    storage.put(f'documents/{doc_id}/original.pdf', pdf_bytes, 'application/pdf')
    storage.put(f'documents/{doc_id}/pages.json', json.dumps(pages, ensure_ascii=False).encode(), 'application/json')
    storage.put(f'documents/{doc_id}/metadata.json', json.dumps(meta, ensure_ascii=False).encode(), 'application/json')
    return doc_id, meta
