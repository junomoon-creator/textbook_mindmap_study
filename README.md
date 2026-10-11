# mindmapping_study

Independent Streamlit + Anthropic Claude + Google Cloud Storage project for studying textbook PDFs using interactive mindmaps and detailed Korean Markdown notes. **Does not depend on `circuit-rag`, RAG embeddings, or OpenAI.**

## Quick start (WSL Ubuntu)

```bash
cd ~/projects
# Unzip mindmapping_study_project.zip here; it creates ./mindmapping_study
cd mindmapping_study
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e '.[test]'
cp .env.example .env
nano .env
```

Set `ANTHROPIC_API_KEY` and confirm `CLAUDE_MODEL` is available to your Anthropic account. Model names and pricing change; check the Anthropic Console. The sample `.env` includes your existing GCS Bucket.

Google Cloud authentication in WSL (if already completed, skip):

```bash
gcloud config set project mindmapping-study
gcloud auth application-default login
gcloud auth application-default set-quota-project mindmapping-study
gcloud storage ls gs://mindmapping-study-data-juno2026/mindmapping_study/raw/textbooks/ --recursive
```

Run:

```bash
streamlit run app.py
```

Open the local URL shown by Streamlit (usually http://localhost:8501). In the left sidebar choose **GCS에 직접 업로드한 PDF 등록** → select a PDF → **선택 PDF 등록**. This registers the PDF for analysis; you do not need to upload it again. Select textbook and PDF bookmark chapter (or page range), then click **Claude 분석 생성**. Once generated, results are read from GCS without Claude API calls. Explicit **재생성** calls the API again.

## GCS structure

```
gs://mindmapping-study-data-juno2026/mindmapping_study/
  raw/textbooks/...pdf               # user-uploaded source PDFs (read-only by this app)
  documents/<sha256>/original.pdf    # registered PDF copy
  documents/<sha256>/pages.json      # extracted PDF text by physical page
  documents/<sha256>/metadata.json   # TOC and source metadata
  learning/<sha256>/p<start>-<end>/<prompt-version>-<model-hash>/
    mindmap.json
    notes/<concept-id>.md
    generation_metadata.json
    result.json                      # cache completion marker
```

## Tests

```bash
pytest -q
```

## Known limitations and security

- Registration currently downloads the entire PDF into the Streamlit process and stores a second copy in `documents/`; large PDFs may require memory and incur additional storage. Original `raw/` PDF is preserved.
- Claude input uses **extracted PDF text**, not images. Complex equations, figures, diagrams, and scanned pages may be omitted or mangled. Page preview shows the actual source page; **AI-generated references are not independently verified**.
- Claude generation is currently one JSON call, limited to 100,000 source characters; select smaller page ranges if needed. Long outputs may exceed the configured token budget.
- Bookmarks are PDF metadata; PDFs without bookmarks require manual page range selection. Physical PDF page numbers may differ from printed book page numbers.
- No authentication, user separation, background jobs, or billing guardrails. Run locally and keep the GCS Bucket private. Never commit `.env`, API keys, or Google credentials.
- GCS API permissions must allow object list/read/create. Google Application Default Credentials are used; no service-account JSON is required for local development.
- `CLAUDE_MODEL` is configurable. If a model is unavailable or renamed, choose a valid model ID from your Anthropic Console.

## Chapter / Section selection (new)

Registered PDFs with PDF bookmarks expose Chapter and Section selectors by default. The selected entry is converted to an inclusive 1-based PDF page range, with the end computed from the next bookmark of the same or higher level. Selecting `전체 Chapter` covers all child sections. For PDFs without bookmarks, choose a manual range or inspect suggested headings from the already extracted page text. Heading suggestions are heuristic and must be confirmed by the user.

The normalized bookmark index is cached as `documents/<sha256>/chapter_index_v1.json` in GCS. Existing `metadata.json` and uploaded PDFs are not changed. Learning-result cache keys continue to use `artifact_base(document_id, start, end, model)`; choosing a chapter that resolves to an existing page range reuses its previously generated result without an API call. Large chapters may exceed the existing 100,000-character extraction limit; select a smaller section if this occurs.

## v4: 긴 문서 분석, 추정 목차, Hybrid Graph

- **분할 분석:** 사이드바에서 1~10페이지 청크 크기 지정(기본 5). 선택 범위 전체를 나누어 Claude로 분석합니다. 출력이 잘리거나 입력 길이 제한을 초과한 구간은 더 작은 구간으로 분할하여 재시도합니다. 성공한 구간은 `learning/<sha>/p<start>-<end>/v4-chunked-<modelhash>/`에 저장되어 다음 실행 시 재사용됩니다. JSON/스키마 실패나 API 인증 오류는 무한 재시도하지 않습니다.
- **통합:** 개별 구간을 그룹으로 묶고, 구간 내부 계층과 연관 관계를 보존합니다. **서로 다른 구간 사이의 의미적 중복 제거 및 관계 추론은 수행하지 않습니다.** 따라서 통합 Mindmap은 구간별 하위 그래프의 합집합에 가까우며, 추후 별도의 검증된 의미 통합 단계가 필요합니다.
- **목차:** PDF Bookmark가 있으면 이를 사용합니다. 없으면 텍스트 제목 패턴으로 추정하고 `documents/<sha>/inferred_outline_v2.json`에 캐시합니다. 추정 경계는 부정확할 수 있으므로 페이지를 확인하세요. 이미지 전용 PDF는 OCR을 지원하지 않습니다.
- **뷰어:** 계층형(부모-자식만), Focus Graph(선택 개념 인접 관계), 전체 관계형(관련 관계 포함). 노드 클릭으로 선택 개념을 변경하고 오른쪽에서 Markdown/PDF 근거를 확인합니다.
- **기존 데이터:** 기존 `documents/`, `learning/` 데이터는 삭제하거나 덮어쓰지 않습니다. v4 분석은 새 캐시 버전을 사용하므로 이전 v3 결과를 자동으로 합치거나 재사용하지 않습니다.
- **API 비용:** 청크마다 Claude 호출이 발생하고, 실패 후 더 작은 구간으로 재시도하면 추가 비용이 발생할 수 있습니다. 최종 통합 파일은 모든 청크가 성공한 뒤에만 기록합니다.
- **토큰 제한:** `.env`의 `CLAUDE_MAX_TOKENS`는 모델이 허용하는 범위 내에서 설정해야 합니다. 처음에는 8192~16384와 3~5페이지 청크를 권장합니다. 그림·수식의 정확한 해석을 위해서는 향후 PDF 페이지 이미지 기반 분석이 필요합니다.

### WSL 업데이트

```bash
cd ~/projects
cp -a mindmapping_study mindmapping_study_backup_$(date +%Y%m%d_%H%M%S)
# 새 ZIP을 임시 디렉터리에 압축 해제한 다음 app.py와 mindmapping_study/*.py를 복사
cd ~/projects/mindmapping_study
source .venv/bin/activate
pip install -e '.[test]'
pytest -q
streamlit run app.py
```

`.env`, `.venv`, 기존 `data/` 및 GCS 객체는 덮어쓰지 마세요.

## v5: Integrated HTML Study Report

- **Mindmap**: choose Chapter/Section or manual page range, run chunked Claude analysis, explore hierarchy/focus/full graph.
- **Integrated HTML Study Report** tab: click **Integrated Report 생성** to produce a report plan, English technical terminology glossary and section-by-section Korean technical explanations. Each completed section is cached independently in GCS.
- Click **HTML 준비 / 원본 페이지 이미지 포함**, then download the **Interactive HTML Report**. HTML embeds its CSS, glossary interaction, concept overview SVG and up to four **full original PDF page previews** as base64 images. It works offline. The PDF previews are **not cropped figures**, and the automatically generated SVG is **not a reproduction of a source circuit diagram**.
- The HTML is based on existing text-extracted study notes. **PDF image content is not analyzed by Claude in this release**, so do not assume that Figure/Table descriptions have been verified visually. Confirm against the source PDF.
- English technical terminology is enforced for **new Claude analysis**. Previously cached v4 results are still readable (and can be used to generate a report), but their original Korean node labels and text are not retroactively rewritten. Run a fresh analysis with v5 if you want the new terminology policy throughout.
- Offline HTML displays LaTeX as source text; high-quality mathematical typesetting (MathJax/KaTeX) is not yet bundled. Printing to PDF is available through the browser's Print dialog.
- Report caches are keyed to the exact source `LearningResult`, report version and model-associated learning path. To force a fresh report after prompt changes, increment `REPORT_VERSION` in `mindmapping_study/report.py`.

Optional `.env` settings:

```dotenv
REPORT_MAX_TOKENS=4096
REPORT_SECTION_CONCEPTS=5
```

Report objects are stored under `<learning-cache>/integrated/integrated-v1-<result-hash>/`. The last-written `complete.json` marks a finished report. No existing GCS documents or v4 learning results are deleted.

## v6: Study History and per-call cost tracking

- **Study History & API Cost** tab shows prior completed analyses and allows reopening a specific saved PDF/page range/model without an API call. Legacy v4/v5 results are discoverable through `learning/**/result.json` even without v6 logs.
- Every new Claude `messages.create` invocation is recorded as a separate immutable JSON object under `history/events/YYYY-MM-DD/<uuid>.json`, including retry calls and failed API requests. Each entry includes timestamp (UTC), document ID, page range, model, task, request ID, token usage, status, and a price snapshot.
- Set `CLAUDE_INPUT_USD_PER_MTOK` and `CLAUDE_OUTPUT_USD_PER_MTOK` to the current **USD per 1 million tokens** rates applicable to your selected model. Without rates, costs display as **unknown** rather than misleading zero. Values are estimates, not billing data. Different pricing tiers, caching, batches, taxes, or currency conversion may differ from the estimate.
- Existing v4/v5 usage metadata is not a per-call history; earlier requests and costs cannot be reconstructed exactly. Cached loads cost no Claude tokens. New requests will be logged automatically.
- Logs are append-only, not deduplicated, and may include failed or truncated model responses that still incurred usage. Do not put raw prompts or API keys in history records.


## v7 — Language Policy & Report Quality Audit

- Technical terminology is English; narrative explanations and glossary definitions are Korean.
- New mindmaps use prompt `v7-english-terms-strict` to avoid silently reusing older-language cache.
- Integrated reports use `integrated-v2-language-audit` cache namespace, preserving prior reports.
- `quality_audit.json` records heuristic flags for translated terms, glossary completeness, and citation page validity.
- The audit does **not** prove technical correctness, figure interpretation, abbreviation accuracy, or completeness. Review source PDF.
- Existing cached v6 reports remain unchanged; generate a new v7 report for new policy.
- Diagram is a concept outline, not a validated circuit diagram. Source page previews are not figure-level AI analysis.


## v8 — Document Flow (reading order)

The Interactive Mindmap now includes **Document Flow**, in addition to Hierarchy, Focus Graph and Full Graph. It lists concepts in the order of their **earliest cited PDF page**, grouping them by page. Select a concept in the reading-order list to open its existing Study Note and PDF page preview.

- Reuses v7 `LearningResult` and GCS caches: **no Claude API re-analysis required**.
- Omits synthetic `chapter_root` and `partN_group` nodes from the reading sequence.
- When multiple concepts cite the same earliest page, their saved concept order is used as a stable tie-breaker. **This does not prove their exact order in the original text.**
- Planned next step: extract PDF Text Block anchors for within-page reading order and use Section/Chapter anchors where available.
- Added `mindmapping_study/document_flow.py` and `tests/test_document_flow.py`.

To install/update: `python -m pip install -e '.[test]'`; run `python -m pytest -q`, then `streamlit run app.py`.
