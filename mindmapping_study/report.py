"""Integrated, resumable study report with offline HTML glossary and source-page illustrations."""
import base64
import hashlib
import html
import json
import os
import re
from datetime import datetime, timezone

import fitz
import mistune
from pydantic import BaseModel, Field

REPORT_VERSION = 'integrated-v2-language-audit'
LANGUAGE_POLICY = (
    'Language Policy (MANDATORY): Write explanations in Korean. Preserve standard technical terminology '
    'in English. Do not translate established semiconductor, circuit design, EDA, or engineering terms '
    'into Korean. For example use Lithography (not 노광), Threshold Voltage (not 문턱 전압), '
    'Parasitic Capacitance (not 기생 커패시턴스), Propagation Delay (not 전파 지연), '
    'Process Variation (not 공정 변동성), Ring Oscillator (not 링 오실레이터). '
    'On first occurrence, provide the full English term and its abbreviation when applicable. '
    'Explain unfamiliar technical terms in Korean through the Terminology Glossary. '
    'Preserve original variable names, equation symbols, cell names, and process names. '
    'Do not invent terminology or abbreviations. '
    'Do not claim to interpret a source figure unless its visual content was supplied. '
    'Distinguish PDF-supported facts from Engineering Insight (추론). '
    'Never invent measurements, figures, equations, or PDF citations.'
)

# Conservative, auditable language checks: this is NOT a substitute for expert review.
TERMINOLOGY_REPLACEMENTS = {
    '노광': 'Lithography',
    '문턱 전압': 'Threshold Voltage',
    '기생 커패시턴스': 'Parasitic Capacitance',
    '전파 지연': 'Propagation Delay',
    '공정 변동성': 'Process Variation',
    '링 오실레이터': 'Ring Oscillator',
}

def audit_report(report_md, plan, result):
    """Report reproducible quality flags; never silently rewrite source-grounded text."""
    issues = []
    for korean, english in TERMINOLOGY_REPLACEMENTS.items():
        for match in re.finditer(re.escape(korean), report_md, re.IGNORECASE):
            line = report_md.count('\n', 0, match.start()) + 1
            issues.append({'type': 'translated_technical_term', 'severity': 'warning',
                           'line': line, 'text': korean, 'suggested': english})
    if not plan.terms:
        issues.append({'type': 'missing_glossary', 'severity': 'warning'})
    for term in plan.terms:
        if not re.search(r'[A-Za-z]', term.term):
            issues.append({'type': 'non_english_glossary_term', 'severity': 'warning', 'text': term.term})
        if len(term.definition_ko.strip()) < 8:
            issues.append({'type': 'short_definition', 'severity': 'warning', 'text': term.term})
    valid_pages = {p for c in result.concepts for p in c.source_pages}
    for m in re.finditer(r'\[PDF p\.(\d+)\]', report_md):
        if int(m.group(1)) not in valid_pages:
            issues.append({'type': 'unverified_page_reference', 'severity': 'warning',
                           'line': report_md.count('\n', 0, m.start()) + 1, 'text': m.group(0)})
    if not re.search(r'\[PDF p\.\d+\]', report_md):
        issues.append({'type': 'missing_pdf_references', 'severity': 'warning'})
    return {'passed': len(issues) == 0, 'issues': issues, 'checked_concepts': len(result.concepts),
            'glossary_terms': len(plan.terms), 'scope': 'heuristic language and citation checks only'}


class Term(BaseModel):
    term: str = Field(min_length=2)
    definition_ko: str = Field(min_length=8)


class ReportPlan(BaseModel):
    title: str
    overview_ko: str
    terms: list[Term] = Field(default_factory=list)


def report_base(learning_base: str, result) -> str:
    digest = hashlib.sha256(result.model_dump_json().encode('utf-8')).hexdigest()[:16]
    return f'{learning_base}/integrated/{REPORT_VERSION}-{digest}'


def _json_object(raw):
    raw = raw.strip()
    if raw.startswith('```'):
        raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        begin = raw.find('{')
        if begin < 0:
            raise
        obj, _ = json.JSONDecoder().raw_decode(raw[begin:])
        return obj


def _ask(client, model, system, prompt, max_tokens):
    message = client.messages.create(model=model, system=system, max_tokens=max_tokens,
                                     messages=[{'role': 'user', 'content': prompt}])
    if getattr(message, 'stop_reason', None) == 'max_tokens':
        raise ValueError('Report response reached max_tokens; lower REPORT_SECTION_CONCEPTS or increase REPORT_MAX_TOKENS')
    return ''.join(x.text for x in message.content if getattr(x, 'type', '') == 'text'), {
        'input_tokens': getattr(message.usage, 'input_tokens', 0) or 0,
        'output_tokens': getattr(message.usage, 'output_tokens', 0) or 0,
    }


def _groups(result, max_concepts=5):
    """Split long chapter reports into independently resumable sections."""
    meaningful = [c for c in result.concepts if c.id != 'chapter_root' and not c.id.endswith('_group')]
    return [meaningful[i:i + max_concepts] for i in range(0, len(meaningful), max_concepts)]


def _source_digest(concepts):
    return [{'id': c.id, 'title': c.title_en or c.title_ko, 'pages': c.source_pages,
             'note': c.note_md[:3200]} for c in concepts]


def _usage_add(total, added):
    for k in total:
        total[k] += added.get(k, 0)


def generate_integrated_report(storage, base, result, model, client=None, progress=None):
    """Write report sections separately; persist each completed section before next API call."""
    if client is None:
        from anthropic import Anthropic
        client = Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])
    max_tokens = int(os.getenv('REPORT_MAX_TOKENS', '4096'))
    per_group = max(1, min(int(os.getenv('REPORT_SECTION_CONCEPTS', '5')), 12))
    groups = _groups(result, per_group)
    if not groups:
        raise ValueError('No study concepts to integrate')
    usage = {'input_tokens': 0, 'output_tokens': 0}
    plan_key = f'{base}/plan.json'
    plan_raw = storage.get(plan_key)
    if plan_raw:
        plan = ReportPlan.model_validate_json(plan_raw)
    else:
        digest = [{'title': c.title_en or c.title_ko, 'pages': c.source_pages} for c in result.concepts if c.id != 'chapter_root']
        raw, cost = _ask(client, model,
            'You are an expert engineering tutor. ' + LANGUAGE_POLICY + ' Return ONLY valid JSON.',
            'Create an integrated study report plan based only on these extracted concepts. '
            'Use original English technical terms for title and all glossary term values. Return JSON {"title": string, "overview_ko": string, '
            '"terms": [{"term": English technical term, "definition_ko": Korean explanation}]}. '
            'Keep glossary to at most 25 useful terms. No unsupported facts.\n' +
            json.dumps({'chapter': result.chapter_title, 'concepts': digest}, ensure_ascii=False),
            max_tokens)
        plan = ReportPlan.model_validate(_json_object(raw))
        storage.put(plan_key, plan.model_dump_json().encode(), 'application/json')
        _usage_add(usage, cost)
    sections = []
    for idx, concepts in enumerate(groups):
        key = f'{base}/sections/section_{idx+1:03d}.md'
        data = storage.get(key)
        if data is None:
            prompt = (
                f'Create PART {idx+1}/{len(groups)} of a coherent integrated engineering study report titled {plan.title}. '
                'Follow the Language Policy exactly: Korean explanations and original English technical terms, never Korean translations of technical terms. '
                'Write Markdown with a descriptive H2 heading. Explain the concepts as one connected narrative, '
                'not a concatenation of notes. Include terminology explanations, mechanisms, equations and variable definitions '
                'when supported by the supplied notes, design implications, and exact PDF page references as [PDF p.N]. '
                'Avoid repeating the overview and avoid unsupported figure numbers. '
                'Do not invent content from unseen pages. Label any engineering inference as "Engineering Insight (추론)". '
                'Write ONLY Markdown.\n\n' + json.dumps(_source_digest(concepts), ensure_ascii=False)
            )
            body, cost = _ask(client, model, LANGUAGE_POLICY, prompt, max_tokens)
            if len(body.strip()) < 60:
                raise ValueError(f'Generated section {idx+1} was unexpectedly short')
            storage.put(key, body.encode('utf-8'), 'text/markdown; charset=utf-8')
            _usage_add(usage, cost)
        else:
            body = data.decode('utf-8')
        sections.append(body)
        if progress:
            progress(idx + 1, len(groups))
    report_md = (f'# {plan.title}\n\n## Overview\n\n{plan.overview_ko}\n\n' +
                 '\n\n'.join(sections) + '\n\n## Terminology Glossary\n\n' +
                 '\n'.join(f'- **{t.term}**: {t.definition_ko}' for t in plan.terms) + '\n')
    storage.put(f'{base}/report.md', report_md.encode(), 'text/markdown; charset=utf-8')
    storage.put(f'{base}/glossary.json', json.dumps([t.model_dump() for t in plan.terms], ensure_ascii=False).encode(), 'application/json')
    audit = audit_report(report_md, plan, result)
    storage.put(f'{base}/quality_audit.json', json.dumps(audit, ensure_ascii=False, indent=2).encode(), 'application/json')
    storage.put(f'{base}/metadata.json', json.dumps({'version': REPORT_VERSION, 'model': model,
        'generated_at': datetime.now(timezone.utc).isoformat(), 'usage_this_run': usage,
        'sections': len(sections)}, ensure_ascii=False).encode(), 'application/json')
    # The final marker is written after all report artifacts exist.
    storage.put(f'{base}/complete.json', b'{"complete":true}', 'application/json')
    return report_md, plan, usage


def load_integrated_report(storage, base):
    if not storage.get(f'{base}/complete.json'):
        return None
    raw = storage.get(f'{base}/report.md')
    plan = storage.get(f'{base}/plan.json')
    if raw is None or plan is None:
        return None
    return raw.decode('utf-8'), ReportPlan.model_validate_json(plan)


def diagram_svg(result):
    """Deterministic concept overview; never claims to reproduce a source circuit figure."""
    concepts = [c for c in result.concepts if c.id != 'chapter_root' and not c.id.endswith('_group')][:12]
    if not concepts:
        return ''
    width = 860
    row_h = 66
    height = 65 + row_h * len(concepts)
    labels = []
    for i, c in enumerate(concepts):
        label = html.escape((c.title_en or c.title_ko)[:75])
        y = 30 + i * row_h
        labels.append(f'<rect x="24" y="{y}" width="800" height="48" rx="9" fill="#eaf2ff" stroke="#8cb0e6"/>'
                      f'<text x="43" y="{y+29}" font-family="Arial,sans-serif" font-size="17" fill="#1c3555">{label}</text>')
        if i:
            labels.append(f'<path d="M424 {y-18} V{y}" stroke="#6585a7" stroke-width="2" fill="none"/>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="Concept overview diagram">' + ''.join(labels) + '</svg>'


def _page_images(pdf_bytes, result, max_pages=4):
    if not pdf_bytes:
        return []
    counts = {}
    for c in result.concepts:
        for page in c.source_pages:
            counts[page] = counts.get(page, 0) + 1
    images = []
    with fitz.open(stream=pdf_bytes, filetype='pdf') as doc:
        for p in sorted(counts, key=lambda x: (-counts[x], x))[:max_pages]:
            if 1 <= p <= len(doc):
                pix = doc[p-1].get_pixmap(matrix=fitz.Matrix(0.85, 0.85), alpha=False)
                data = base64.b64encode(pix.tobytes('png')).decode('ascii')
                images.append((p, data))
    return images


def render_html(report_md, plan, result, pdf_bytes=None):
    """Self-contained HTML: inline CSS/JS/SVG/images, offline glossary and navigation."""
    renderer = mistune.create_markdown(escape=True, plugins=['table', 'strikethrough'])
    content = renderer(report_md)
    # Glossary cards use native details elements and remain usable without JavaScript.
    glossary = ''.join('<details class="term" id="term-%s"><summary>%s</summary><p>%s</p></details>' % (
        hashlib.sha256(t.term.encode()).hexdigest()[:10], html.escape(t.term), html.escape(t.definition_ko))
        for t in plan.terms)
    refs = ''.join('<figure><img alt="Original PDF page %d" src="data:image/png;base64,%s"><figcaption>Original PDF p.%d — source page preview (not AI-generated)</figcaption></figure>' % (p, b64, p)
                   for p, b64 in _page_images(pdf_bytes, result))
    svg = diagram_svg(result)
    audit = audit_report(report_md, plan, result)
    audit_note = ('Automated checks: PASS' if audit['passed'] else
                  f"Automated checks: {len(audit['issues'])} warning(s); review the source PDF.")
    title = html.escape(plan.title)
    return f'''<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} | Mindmapping Study</title>
<style>
:root{{color-scheme:light;--ink:#1b2b43;--muted:#56677d;--line:#dbe4ee;--blue:#2468b5}}
*{{box-sizing:border-box}}body{{margin:0;background:#f5f8fc;color:var(--ink);font:16px/1.8 system-ui,'Noto Sans KR',sans-serif}}
header{{background:#102b4c;color:white;padding:24px max(22px,calc((100vw - 1140px)/2))}}header p{{opacity:.78;margin:0}}
.layout{{display:grid;grid-template-columns:230px minmax(0,1fr);gap:24px;max-width:1200px;margin:24px auto;padding:0 16px}}
nav{{position:sticky;top:20px;align-self:start;background:white;border:1px solid var(--line);border-radius:12px;padding:18px;max-height:90vh;overflow:auto}}
nav a{{display:block;color:var(--blue);text-decoration:none;padding:5px 0;font-size:14px}}
main{{min-width:0}}section{{background:white;border:1px solid var(--line);border-radius:12px;padding:24px;margin-bottom:20px}}
h1,h2,h3{{line-height:1.35}}h2{{border-bottom:1px solid var(--line);padding-bottom:9px}}p,li{{overflow-wrap:anywhere}}
article img,figure img,svg{{max-width:100%;height:auto}}figure{{margin:15px 0}}figcaption{{color:var(--muted);font-size:13px}}
pre{{overflow-x:auto;background:#f2f6fc;padding:14px;border-radius:8px}}code{{font-size:.9em}}
.term{{border-bottom:1px solid var(--line);padding:9px 0}}summary{{cursor:pointer;color:var(--blue);font-weight:600}}
.note{{color:var(--muted);font-size:13px}}table{{border-collapse:collapse;max-width:100%;display:block;overflow-x:auto}}
td,th{{border:1px solid var(--line);padding:6px 12px}}.toolbar{{display:flex;gap:12px;flex-wrap:wrap}}
button{{cursor:pointer;padding:8px 12px;border:1px solid var(--line);border-radius:8px;background:white}}
@media(max-width:780px){{.layout{{display:block}}nav{{position:static;margin-bottom:20px}}section{{padding:16px}}}}
@media print{{body{{background:white}}nav,.toolbar{{display:none}}section{{border:none;break-inside:avoid}}}}
</style></head><body><header><h1>{title}</h1><p>Integrated Technical Study Report · Korean explanation / English technical terminology</p></header>
<div class="layout"><nav><strong>Contents</strong><a href="#report">Integrated Report</a><a href="#diagram">Concept Overview</a><a href="#glossary">Terminology</a><a href="#source">Source PDF Pages</a><hr><div class="toolbar"><button onclick="window.print()">Print / Save PDF</button></div></nav>
<main><section id="report"><article>{content}</article></section>
<section id="diagram"><h2>Concept Overview Diagram</h2><p class="note">Automatically generated concept outline; not a reproduction of a source circuit or measurement figure.</p>{svg}</section>
<section id="glossary"><h2>Interactive Terminology</h2><p class="note">Click each English term to read its Korean explanation.</p>{glossary}</section>
<section id="source"><h2>Original PDF Page Previews</h2><p class="note">These are original page images for cross-checking. A page preview is not a cropped or interpreted Figure.</p>{refs or '<p>No source page previews available.</p>'}</section>
<footer class="note">{html.escape(audit_note)} · Source references [PDF p.N] indicate physical PDF pages. Verify all technical claims against the original document.</footer></main></div></body></html>'''
