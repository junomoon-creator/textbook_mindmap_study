"""Streamlit entrypoint: streamlit run app.py"""
import json
import os
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
from streamlit_agraph import agraph, Node, Edge, Config
from mindmapping_study.storage import Storage
from mindmapping_study.catalog import discover_pdfs, register_pdf, registered_documents
from mindmapping_study.pipeline import artifact_base, get_cached, save_result
from mindmapping_study.incremental import generate_chunked
from mindmapping_study.document_flow import reading_sequence, page_groups
from mindmapping_study.report import (report_base, generate_integrated_report, load_integrated_report, render_html, audit_report)
from mindmapping_study.history import TrackedClient, list_events, list_studies, totals
from mindmapping_study.chapters import load_outline, chapter_sections, section_candidates, load_inferred_outline

st.set_page_config(page_title='Mindmapping Study', page_icon='📚', layout='wide')
st.title('📚 Mindmapping Study')
st.caption('GCS 교재 라이브러리 · Claude 기반 Mindmap · Korean explanation + English technical terminology · Integrated HTML Report')

@st.cache_resource
def get_storage():
    return Storage()

try:
    storage = get_storage()
except Exception as exc:
    st.error(f'저장소 연결 실패: {exc}')
    st.stop()

with st.sidebar:
    st.header('📁 Textbook Library')
    st.caption('GCS: gs://%s/%s/' % (os.getenv('GCS_BUCKET', '(local)'), os.getenv('GCS_PREFIX', 'mindmapping_study')))
    with st.expander('GCS에 직접 업로드한 PDF 등록', expanded=True):
        try:
            raw_pdfs = discover_pdfs(storage)
        except Exception as exc:
            st.error(f'GCS 목록 조회 실패: {exc}')
            raw_pdfs = []
        if raw_pdfs:
            raw_choice = st.selectbox('등록할 PDF', raw_pdfs, format_func=lambda x: x.removeprefix('raw/textbooks/'))
            if st.button('선택 PDF 등록', type='primary'):
                try:
                    with st.spinner('PDF 텍스트/목차 추출 중...'):
                        doc_id, _ = register_pdf(storage, raw_key=raw_choice)
                    st.success(f'등록 완료: {doc_id[:12]}')
                    st.rerun()
                except Exception as exc:
                    st.error(f'등록 실패: {exc}')
        else:
            st.info('raw/textbooks/ 아래에 PDF가 없습니다.')
    with st.expander('브라우저에서 PDF 추가'):
        uploaded = st.file_uploader('PDF 선택', type=['pdf'])
        if uploaded and st.button('업로드 및 등록'):
            try:
                with st.spinner('업로드 중...'):
                    register_pdf(storage, pdf_bytes=uploaded.getvalue(), filename=uploaded.name)
                st.success('등록 완료')
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    try:
        docs = registered_documents(storage)
    except Exception as exc:
        st.error(f'등록 문서 조회 실패: {exc}')
        st.stop()
    if not docs:
        st.info('먼저 GCS PDF를 등록하세요.')
        st.stop()
    history_target = st.session_state.get('history_target')
    doc_options = list(docs)
    default_doc = history_target['document_id'] if history_target and history_target['document_id'] in docs else doc_options[0]
    selected = st.selectbox('Textbook / Paper', doc_options, index=doc_options.index(default_doc), format_func=lambda x: docs[x]['name'])
    info = docs[selected]
    st.caption(f"PDF {info['pages']} pages · SHA256 {selected[:12]}...")
    outline = load_outline(storage, selected, info)
    page_data = None
    if not outline:
        raw_pages = storage.get(f'documents/{selected}/pages.json')
        if raw_pages:
            page_data = json.loads(raw_pages)
            outline = load_inferred_outline(storage, selected, page_data, int(info['pages']))
    chapters = chapter_sections(outline)
    mode_options = ['Chapter / Section 선택', '수동 페이지 범위'] if chapters else ['수동 페이지 범위', '제목 후보에서 범위 지정']
    if chapters and not info.get('toc'):
        st.warning('이 PDF에는 Bookmark가 없습니다. 아래 Chapter/Section은 텍스트에서 추정한 후보이며 경계를 확인해야 합니다.')
    mode = st.radio('영역 선택 방식', mode_options, horizontal=False, key=f'mode_{selected}')
    if mode == 'Chapter / Section 선택':
        chapter_ids = [x['id'] for x in chapters]
        chapter_id = st.selectbox('Chapter', chapter_ids,
            format_func=lambda k: next(f"{c['title']} (PDF p.{c['start']}–{c['end']})" for c in chapters if c['id'] == k),
            key=f'chapter_{selected}')
        chapter = next(c for c in chapters if c['id'] == chapter_id)
        section_options = ['__all__'] + [x['id'] for x in chapter['sections']]
        section_id = st.selectbox('Section', section_options,
            format_func=lambda k: '전체 Chapter' if k == '__all__' else next(
                f"{'  ' * max(0, x['level'] - chapter['level'] - 1)}{x['title']} (p.{x['start']}–{x['end']})"
                for x in chapter['sections'] if x['id'] == k),
            key=f'section_{selected}_{chapter_id}')
        region = chapter if section_id == '__all__' else next(x for x in chapter['sections'] if x['id'] == section_id)
        start, end = region['start'], region['end']
        st.info(f"선택한 범위: PDF p.{start}–{end} ({end-start+1}페이지)")
    elif mode == '제목 후보에서 범위 지정':
        st.warning('PDF Bookmark가 없습니다. 아래 제목 후보는 자동 추정이므로 페이지 범위를 확인하세요.')
        page_data = page_data or json.loads(storage.get(f'documents/{selected}/pages.json'))
        candidates = section_candidates(page_data)
        if candidates:
            options = list(range(len(candidates)))
            pick = st.selectbox('시작 제목 후보', options,
                format_func=lambda i: f"p.{candidates[i]['page']}: {candidates[i]['title']}", key=f'candidate_{selected}')
            start_default = candidates[pick]['page']
            end_default = min(info['pages'], next((x['page']-1 for x in candidates[pick+1:]
                                                    if x['page'] > start_default), info['pages']))
        else:
            st.info('제목 후보를 찾지 못했습니다. 페이지를 직접 지정하세요.')
            start_default, end_default = 1, min(10, info['pages'])
        start = st.number_input('시작 PDF 페이지', 1, info['pages'], value=start_default, key=f'candidate_start_{selected}_{start_default}')
        end = st.number_input('끝 PDF 페이지', 1, info['pages'], value=end_default, key=f'candidate_end_{selected}_{start_default}')
    else:
        if not chapters:
            st.caption('이 PDF에는 Bookmark 목차가 없습니다. 수동 범위 또는 제목 후보를 이용하세요.')
        start = st.number_input('시작 PDF 페이지', 1, info['pages'], value=1, key=f'manual_start_{selected}')
        end = st.number_input('끝 PDF 페이지', 1, info['pages'], value=min(10, info['pages']), key=f'manual_end_{selected}')
    st.caption('페이지는 책에 인쇄된 번호가 아닌 PDF의 실제 페이지 순서입니다.')
    chunk_size = st.slider('분석 구간 크기 (페이지)', 1, 10, 5, key='chunk_size')

if st.session_state.get('history_target') and st.session_state['history_target']['document_id'] == selected:
    saved = st.session_state['history_target']
    start, end = saved['page_start'], saved['page_end']
    st.sidebar.info(f'History에서 로드한 범위: PDF p.{start}–{end}')
    if st.sidebar.button('History 선택 해제'):
        del st.session_state['history_target']
        st.rerun()

if start > end:
    st.warning('시작 페이지는 끝 페이지보다 작거나 같아야 합니다.')
    st.stop()

model = (st.session_state.get('history_target') or {}).get('model') or os.getenv('CLAUDE_MODEL', '').strip()
base = (st.session_state.get('history_target') or {}).get('artifact_key') or artifact_base(selected, int(start), int(end), model or 'unconfigured')
try:
    result = get_cached(storage, base)
    source_base = base
    if result is None:
        import hashlib
        model_hash = hashlib.sha256((model or 'unconfigured').encode()).hexdigest()[:12]
        for legacy_version in ('v4-chunked', 'v3-json-retry'):
            legacy_base = f'learning/{selected}/p{int(start)}-{int(end)}/{legacy_version}-{model_hash}'
            legacy = get_cached(storage, legacy_base)
            if legacy is not None:
                result = legacy
                source_base = legacy_base
                break
except Exception as exc:
    st.error(f'저장된 결과 로드 실패: {exc}')
    st.stop()

st.subheader(f"{info['name']} · PDF p.{start}–{end}")
c1, c2 = st.columns([1, 3])
with c1:
    st.write('상태:', '✅ 기존 분석 있음' if result else '분석 전')
    if not model:
        st.warning('.env에서 CLAUDE_MODEL을 설정하세요.')
    if result:
        st.caption('재생성은 Claude API를 다시 호출하며 비용이 발생합니다.')
    generate = st.button('♻️ 재생성 (API 호출)' if result else '✨ Claude 분석 생성', disabled=not bool(model))
with c2:
    st.info('이미 생성된 결과는 GCS에서 바로 불러옵니다. 생성 버튼을 누를 때만 Claude API를 호출합니다.')

if generate:
    try:
        with st.spinner('Claude 분석 중...'):
            raw = storage.get(f'documents/{selected}/pages.json')
            if not raw:
                raise ValueError('등록된 PDF 텍스트가 없습니다.')
            pages = json.loads(raw)
            bar = st.progress(0, text='구간별 분석 진행 중...')
            def on_progress(done, total):
                bar.progress((done - int(start) + 1) / (total - int(start) + 1), text=f'PDF p.{done}까지 분석 완료')
            from anthropic import Anthropic
            tracked = TrackedClient(Anthropic(api_key=os.environ['ANTHROPIC_API_KEY']), storage, 'mindmap', selected, int(start), int(end), base)
            new_result, usage = generate_chunked(storage, pages, selected, int(start), int(end), model, client=tracked,
                                                  chunk_size=chunk_size, progress=on_progress)
            save_result(storage, base, new_result, usage, selected, int(start), int(end), model)
        st.success(f"완료 · 입력 {usage['input_tokens']:,} / 출력 {usage['output_tokens']:,} tokens")
        st.rerun()
    except Exception as exc:
        st.error(f'분석 실패: {exc}')

if result is None:
    st.info('먼저 분석을 생성하거나, 기존 기록을 History에서 불러오세요.')
    # The history browser is also available before the first analysis.
    from mindmapping_study.history import list_studies
    studies = list_studies(storage)
    if studies:
        choices = [x for x in studies if x['document_id'] in docs and isinstance(x['page_start'], int) and isinstance(x['page_end'], int)]
        if choices:
            choice = st.selectbox('📚 저장된 학습 기록 불러오기', range(len(choices)),
                format_func=lambda i: f"{docs[choices[i]['document_id']]['name']} · p.{choices[i]['page_start']}–{choices[i]['page_end']}")
            if st.button('선택한 학습 기록 열기'):
                st.session_state['history_target'] = choices[choice]
                st.rerun()
    st.subheader('🧾 API 호출 비용 History')
    events = list_events(storage)
    stats = totals(events)
    st.write(f"총 {stats['calls']}회 · Input {stats['input_tokens']:,} / Output {stats['output_tokens']:,} tokens")
    if events:
        st.dataframe([{k: e.get(k) for k in ('timestamp', 'event_type', 'status', 'model', 'input_tokens', 'output_tokens', 'estimated_cost_usd')} for e in events], use_container_width=True)
    st.stop()

# Independent integrated report cache, keyed to the exact current analysis result.
report_key = report_base(source_base, result)
report_tabs = st.tabs(['🧠 Interactive Mindmap', '📖 Integrated HTML Study Report', '🕘 Study History & API Cost'])
with report_tabs[1]:
    st.subheader('Integrated Study Report')
    st.caption('Technical terms stay in English; definitions are explained in Korean. Report sections are cached separately in GCS.')
    existing_report = load_integrated_report(storage, report_key)
    if existing_report:
        report_md, report_plan = existing_report
        st.success('GCS에 저장된 통합 보고서를 불러왔습니다. Claude API 호출 없음.')
        if st.button('♻️ 보고서 다시 생성', key='regenerate_report'):
            # A new version is created by changing the report prompt version; do not overwrite
            # cached sections silently. Use an explicit reset in a future admin workflow.
            st.info('기존 보고서를 보호하기 위해 현재 버전에서는 자동 덮어쓰기를 지원하지 않습니다.')
    else:
        report_md = report_plan = None
        if st.button('✨ Integrated Report 생성 (Claude API)', key='generate_report'):
            try:
                from anthropic import Anthropic
                client = Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])
                prog = st.progress(0, text='통합 보고서 작성 준비 중...')
                count = max(1, (len(result.concepts) + 4) // 5)
                def report_progress(done, total):
                    prog.progress(done / total, text=f'보고서 Section {done}/{total} 완료')
                with st.spinner('Glossary, 보고서 Section을 생성하고 GCS에 저장하는 중...'):
                    tracked = TrackedClient(client, storage, 'integrated_report', selected, int(start), int(end), report_key)
                    report_md, report_plan, cost = generate_integrated_report(
                        storage, report_key, result, model, client=tracked, progress=report_progress)
                st.success(f"보고서 생성 완료 · 입력 {cost['input_tokens']:,} / 출력 {cost['output_tokens']:,} tokens")
                st.rerun()
            except Exception as exc:
                st.error(f'보고서 생성 실패: {exc}')
    if report_md is not None:
        audit = audit_report(report_md, report_plan, result)
        if audit['passed']:
            st.success('Language & Reference Audit: 자동 점검 통과 (기술적 정확성의 보증은 아닙니다).')
        else:
            st.warning(f"Language & Reference Audit: {len(audit['issues'])}건의 확인 항목이 있습니다.")
            with st.expander('검증 상세 결과', expanded=False):
                st.json(audit)
        st.download_button('⬇️ 검증 결과 JSON', json.dumps(audit, ensure_ascii=False, indent=2), file_name='quality_audit.json', mime='application/json')
        st.markdown(report_md)
        st.download_button('⬇️ 통합 보고서 Markdown', report_md,
                           file_name='integrated_study_report.md', mime='text/markdown')
        if st.button('HTML 준비 / 원본 페이지 이미지 포함', key='render_report_html'):
            with st.spinner('독립 실행 HTML 생성 중...'):
                pdf_data = storage.get(f'documents/{selected}/original.pdf')
                html_data = render_html(report_md, report_plan, result, pdf_data)
                storage.put(report_key + '/report.html', html_data.encode('utf-8'), 'text/html; charset=utf-8')
                st.session_state['report_html_' + report_key] = html_data
        cached_html = st.session_state.get('report_html_' + report_key)
        if not cached_html:
            stored_html = storage.get(report_key + '/report.html')
            cached_html = stored_html.decode('utf-8') if stored_html else None
        if cached_html:
            st.download_button('⬇️ Interactive HTML Report', cached_html,
                               file_name='integrated_study_report.html', mime='text/html')
            with st.expander('HTML 미리보기', expanded=False):
                import streamlit.components.v1 as components
                components.html(cached_html, height=650, scrolling=True)

with report_tabs[0]:
    # Four complementary views: document reading order, outline, focused neighbors, and full graph.
    view = st.radio('Mindmap 보기', ['Document Flow', '계층형', 'Focus Graph', '전체 관계형'], horizontal=True)
    concepts = {c.id: c for c in result.concepts}
    ids = list(concepts)
    selected_key = f'concept_{selected}'
    preferred = st.session_state.pop(f'{selected_key}_pending', st.session_state.get(selected_key, ids[0]))
    if preferred not in concepts:
        preferred = ids[0]
    with st.container():
        focus_widget_key = f'focus_{selected}_{start}_{end}'
        if st.session_state.get(focus_widget_key) != preferred and f'{selected_key}_sync' in st.session_state:
            st.session_state[focus_widget_key] = preferred
        focus_id = st.selectbox('중심 개념', ids, index=ids.index(preferred),
                                format_func=lambda x: concepts[x].title_en or concepts[x].title_ko, key=focus_widget_key)
        st.session_state[selected_key] = focus_id

    if view == 'Document Flow':
        sequence = reading_sequence(result)
        st.caption('원본 PDF의 첫 인용 페이지 순서입니다. 같은 페이지에서는 저장된 Concept 순서를 사용하며 정확한 문단 순서를 보장하지 않습니다.')
        if sequence:
            order_ids = [c.id for c in sequence]
            current_index = order_ids.index(focus_id) if focus_id in order_ids else 0
            flow_id = st.selectbox('Reading Order · 학습할 Concept', order_ids, index=current_index,
                format_func=lambda cid: f"{order_ids.index(cid) + 1}. p.{min(concepts[cid].source_pages)} · {concepts[cid].title_en or concepts[cid].title_ko}",
                key=f'flow_select_{selected}_{start}_{end}_{focus_id}')
            if flow_id != focus_id:
                st.session_state[f'{selected_key}_pending'] = flow_id
                st.session_state[f'{selected_key}_sync'] = True
                st.rerun()
        else:
            st.info('Reading Order로 표시할 Concept가 없습니다.')

    left, right = st.columns([3, 2])
    with left:
        st.subheader(result.chapter_title)
        if view == 'Document Flow':
            sequence = reading_sequence(result)
            positions = {c.id: i + 1 for i, c in enumerate(sequence)}
            for page_number, items in page_groups(result):
                st.markdown(f'#### PDF p.{page_number}')
                for item in items:
                    title = item.title_en or item.title_ko
                    marker = '▶ ' if item.id == focus_id else ''
                    if st.button(f'{marker}{positions[item.id]:02d}. {title}',
                                 key=f'flow_item_{selected}_{start}_{end}_{item.id}',
                                 use_container_width=True):
                        st.session_state[f'{selected_key}_pending'] = item.id
                        st.session_state[f'{selected_key}_sync'] = True
                        st.rerun()
            st.caption('Page 내부의 실제 문장 순서는 PDF Text Block Anchor를 추가한 이후 정밀화할 수 있습니다.')
        else:
            if view == 'Focus Graph':
                focus = concepts[focus_id]
                visible = {focus_id, *focus.related_ids}
                if focus.parent_id:
                    visible.add(focus.parent_id)
                visible.update(c.id for c in result.concepts if c.parent_id == focus_id or focus_id in c.related_ids)
            else:
                visible = set(ids)
            nodes = [Node(id=c.id, label=((c.title_en or c.title_ko)[:24] + '…' if len(c.title_en or c.title_ko) > 24 else (c.title_en or c.title_ko)),
                          size=20 if c.id != focus_id else 30,
                          shape='box', color='#c8e0ff' if c.id != focus_id else '#81b3ff',
                          font={'size': 15, 'face': 'Arial'})
                     for c in result.concepts if c.id in visible]
            edges = [Edge(source=c.parent_id, target=c.id, color='#7895b5')
                     for c in result.concepts if c.parent_id and c.id in visible and c.parent_id in visible]
            if view != '계층형':
                seen_edges = set()
                for c in result.concepts:
                    for other in c.related_ids:
                        pair = tuple(sorted((c.id, other)))
                        if c.id in visible and other in visible and pair not in seen_edges:
                            seen_edges.add(pair)
                            edges.append(Edge(source=c.id, target=other, dashes=True, color='#d6a066'))
            config = Config(width='100%', height=650, directed=True, physics=False,
                            hierarchical=(view == '계층형'),
                            interaction={'hover': True, 'navigationButtons': True, 'zoomView': True})
            clicked = agraph(nodes=nodes, edges=edges, config=config)
            if clicked in concepts and clicked != focus_id:
                st.session_state[f'{selected_key}_pending'] = clicked
                st.session_state[f'{selected_key}_sync'] = True
                st.rerun()
            st.caption('실선: 상하위 관계 · 점선: 연관 관계. Focus Graph는 선택 개념 주변만 표시합니다.')

    with right:
        concept = concepts[focus_id]
        st.subheader(concept.title_en or concept.title_ko)
        st.markdown(concept.note_md)
        st.caption('근거 PDF 페이지: ' + ', '.join(str(x) for x in concept.source_pages))
        st.download_button('⬇️ Study Note (.md)', concept.note_md, file_name=f'{concept.id}.md', mime='text/markdown')
        pdf = storage.get(f'documents/{selected}/original.pdf')
        if pdf:
            st.download_button('⬇️ 원본 PDF', pdf, file_name=info['name'], mime='application/pdf')
            page = st.selectbox('PDF 페이지 미리보기', concept.source_pages)
            try:
                import fitz
                with fitz.open(stream=pdf, filetype='pdf') as doc:
                    pix = doc[int(page) - 1].get_pixmap(matrix=fitz.Matrix(1.25, 1.25))
                    st.image(pix.tobytes('png'), caption=f'PDF p.{page}', use_container_width=True)
            except Exception as exc:
                st.warning(f'페이지 미리보기 실패: {exc}')

with report_tabs[2]:
    st.subheader('Study History & API Cost')
    st.caption('과거 분석 결과를 선택하면 Claude 호출 없이 Mindmap과 Integrated Report를 다시 공부할 수 있습니다.')
    scope = st.radio('History 범위', ['현재 문서', '모든 문서'], horizontal=True)
    doc_filter = selected if scope == '현재 문서' else None
    if st.button('🔄 History 새로고침'):
        st.rerun()
    try:
        studies = list_studies(storage, doc_filter)
        if studies:
            choices = list(range(len(studies)))
            chosen = st.selectbox('저장된 학습 기록', choices, format_func=lambda i:
                f"{docs.get(studies[i]['document_id'], {}).get('name', studies[i]['document_id'][:12])} · "
                f"p.{studies[i]['page_start']}–{studies[i]['page_end']} · "
                f"{studies[i]['generated_at'][:16]} · {studies[i]['model']}" +
                (' · HTML Report' if studies[i]['has_report'] else ''))
            study = studies[chosen]
            if st.button('📖 선택 기록 불러와 다시 공부하기', type='primary'):
                if study['document_id'] not in docs:
                    st.error('원본 PDF가 현재 Library에 등록되어 있지 않습니다.')
                elif not isinstance(study['page_start'], int) or not isinstance(study['page_end'], int):
                    st.error('과거 기록에 페이지 범위가 없어 불러올 수 없습니다.')
                else:
                    st.session_state['history_target'] = study
                    st.rerun()
        else:
            st.info('저장된 분석 결과가 없습니다.')
        events = list_events(storage, doc_filter)
        stats = totals(events)
        a, b, c, d = st.columns(4)
        a.metric('API 호출', f"{stats['calls']:,}")
        b.metric('Input tokens', f"{stats['input_tokens']:,}")
        c.metric('Output tokens', f"{stats['output_tokens']:,}")
        d.metric('추정 비용 (USD)', f"${stats['estimated_cost_usd']:.6f}" if not stats['unpriced_calls'] else '미설정 / 일부 미산정')
        st.caption('비용은 설정된 단가에 따른 추정치입니다. 실제 청구액과 다를 수 있습니다. v6 이전 호출은 로그가 없어 집계되지 않습니다.')
        if events:
            st.dataframe([{k: e.get(k) for k in ('timestamp', 'event_type', 'status', 'model', 'page_start', 'page_end', 'input_tokens', 'output_tokens', 'estimated_cost_usd', 'pricing_status')} for e in events], use_container_width=True)
            st.download_button('⬇️ API 호출 내역 JSON', json.dumps(events, ensure_ascii=False, indent=2),
                               file_name='api_call_history.json', mime='application/json')
        else:
            st.info('v6 이후 Claude API를 호출하면 호출별 token과 비용 추정치가 이곳에 기록됩니다.')
    except Exception as exc:
        st.error(f'History 조회 실패: {exc}')
