# Juno Mindmap Study — 프로젝트 개요, 개발 과정 및 GitHub 등록 가이드

> **문서 목적:** `mindmapping_study`의 기획 배경, 아키텍처, 기능, 개발 이력, 시행착오, 실행 방법, GitHub 최초 등록 및 이후 운영 절차를 한국어로 정리한다.  
> **대상 버전:** v7 (Language Policy & Report Quality Audit)  
> **GitHub:** https://github.com/junomoon-creator/textbook_mindmap_study  
> **로컬 개발 환경:** WSL Ubuntu / `~/projects/mindmapping_study`  
> **작성 기준:** 기존 프로젝트 v7 소스 및 README와 개발 대화에서 확인된 사항. 실제 Claude API·GCS End-to-End 동작은 별도 검증이 필요하다.

---

## 1. 프로젝트 개요

### 1.1 개발 배경

반도체 소자, Circuit Design, EDA, 제어공학 등의 Technical Textbook이나 Research Paper는 다음 이유로 학습에 많은 시간이 든다.

- 개념, 수식, 실험 결과가 여러 Chapter와 Section에 분산되어 있다.
- 전문 Terminology를 이해하지 못하면 본문을 따라가기 어렵다.
- Figure, Block Diagram, Circuit Architecture를 본문과 연결해 이해해야 한다.
- 한 번 읽은 내용을 다시 학습할 때 같은 PDF 페이지를 처음부터 찾아야 한다.
- AI 분석을 반복 호출하면 비용이 누적되므로 재사용 가능한 캐시가 필요하다.

**Mindmapping Study**는 이러한 문제를 해결하기 위해 PDF를 작은 학습 단위(Chunk)로 분석하고, **Interactive Mindmap**으로 개념을 단계적으로 탐색한 뒤 **Integrated HTML Study Report**로 전체 내용을 통합하는 개인 학습용 Python/Streamlit 애플리케이션이다.

### 1.2 핵심 목표

1. **Step-by-step 학습:** 큰 Chapter를 Chunk와 Concept 단위로 분할한다.
2. **개념 간 연결:** Hierarchy, Focus Graph, Full Graph를 통해 관계를 탐색한다.
3. **통합 산출물:** 개별 Note의 나열이 아닌 하나의 일관된 HTML 보고서를 만든다.
4. **Technical Terminology 보존:** 설명은 한국어로 작성하되, 표준 기술 용어는 영어로 유지한다.
5. **학습 재개:** 과거 분석 결과를 History에서 다시 불러온다.
6. **비용 관리:** Claude API 호출별 Token Usage와 Estimated Cost를 기록한다.
7. **클라우드 저장:** PDF 및 분석 산출물을 GCS에 저장하고 캐시를 재사용한다.

### 1.3 전체 학습 흐름

```text
Technical Textbook / Research Paper (PDF)
                │
                ▼
       PDF 등록 및 텍스트 추출
                │
                ▼
   Chapter / Section / Page Range 선택
                │
                ▼
    Chunk-based Claude Analysis
       (기본 약 5페이지 단위)
                │
                ├──── Chunk별 GCS Cache
                ▼
      Concept / Relationship 통합
                │
                ▼
     Interactive Mindmap + Study Notes
                │
                ▼
   Integrated Report Planning & Writing
                │
                ├──── Terminology Glossary
                ├──── Concept Diagram (SVG)
                ├──── Source PDF Page Preview
                └──── PDF Page References
                ▼
      Interactive HTML Study Report
                │
                ├──── GCS 저장 / HTML 다운로드
                ├──── Study History 재학습
                └──── API Cost Tracking
```

---

## 2. 기술 스택과 프로젝트 구조

### 2.1 Technology Stack

| 구분 | 기술 | 역할 |
|---|---|---|
| Language | Python 3.10+ | 애플리케이션 및 분석 Pipeline |
| UI | Streamlit | PDF 선택, 분석, Mindmap, Report, History 화면 |
| AI | Anthropic Claude API | Concept 추출, Note 및 Report 생성 |
| PDF | PyMuPDF | 텍스트 추출, PDF 페이지 이미지 |
| Graph | `streamlit-agraph` | Mindmap 시각화 |
| Data Validation | Pydantic | AI 응답의 구조 검증 |
| Markdown/HTML | Mistune, HTML, SVG | Report 렌더링 |
| Storage | Google Cloud Storage (GCS) | PDF, Cache, History, Report 저장 |
| Configuration | `python-dotenv` | `.env` 설정 로드 |
| Testing | Pytest | 단위 테스트 |

### 2.2 주요 소스 파일

v7 ZIP에서 확인되는 주요 파일은 다음과 같다.

```text
mindmapping_study/
├── app.py
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── mindmapping_study/
│   ├── __init__.py
│   ├── catalog.py
│   ├── chapters.py
│   ├── pipeline.py
│   ├── incremental.py
│   ├── report.py
│   ├── history.py
│   └── storage.py
└── tests/
    ├── test_pipeline.py
    ├── test_chapters.py
    ├── test_incremental.py
    ├── test_report.py
    ├── test_history.py
    └── test_language_audit.py
```

| 파일 | 담당 기능 |
|---|---|
| `app.py` | Streamlit UI 및 기능 연결 |
| `catalog.py` | PDF 문서 등록/목록 관리 |
| `chapters.py` | Bookmark와 Heading 후보를 이용한 Chapter/Section 선택 |
| `pipeline.py` | Claude 분석, JSON Parsing, Concept/Note 생성 |
| `incremental.py` | Chunk 분할, 중간 결과 캐싱 및 통합 |
| `report.py` | Integrated Report 생성, HTML 렌더링, Quality Audit |
| `history.py` | 과거 분석 검색 및 API 호출/비용 기록 |
| `storage.py` | Local/GCS 저장소 추상화 |

---

## 3. 개발 과정 및 버전별 발전 이력

> 아래 내용은 개발 과정에서 논의하고 구현한 **기능의 발전 흐름**이다. Git Commit History를 실제로 조회한 기록이 아니므로 날짜별 Commit Log와 동일한 것으로 해석하지 않는다.

### Phase 1. 독립형 PDF 학습 도구 기획 및 MVP

**요구사항**

- 기존의 다른 RAG 프로젝트와 독립적으로 운영할 것.
- PDF의 특정 페이지를 선택하여 Claude로 분석할 것.
- Concept 중심의 Mindmap과 한국어 Study Note를 생성할 것.
- 원본 PDF 페이지 번호를 유지할 것.
- GCS에 결과를 저장하고 동일 요청 시 재사용할 것.

**초기 설계**

- PDF에서 텍스트를 추출한다.
- Claude에 구조화된 JSON 형식으로 Concept와 Note를 요청한다.
- Concept ID, Parent ID, Related IDs, Source Pages를 기반으로 Graph를 구성한다.
- PDF SHA-256, Page Range, Model, Prompt Version 등을 Cache Key에 반영한다.

**초기 한계**

- 긴 Page Range를 한 번의 Claude 요청으로 처리하면 출력이 길어진다.
- JSON 응답이 불완전하거나 `max_tokens`로 잘릴 수 있다.
- 많은 노드와 관계선을 동시에 표시하면 Mindmap 가독성이 낮아진다.

### Phase 2. JSON 안정성 개선 및 Chapter/Section 선택

**발생한 문제**

1. Claude API 호출에서 잘못된 Model ID 설정으로 `404` 오류가 발생했다.
2. 응답이 JSON 형식을 만족하지 않아 Parsing에 실패했다.
3. 일부 PDF에는 Bookmark 목차가 없어 Chapter를 선택하기 어려웠다.

**대응**

- `.env`의 `CLAUDE_MODEL`에는 `CLAUDE_MODEL=` 접두사를 포함하지 않은 **실제 Model ID만** 입력하도록 안내했다.
- JSON Parsing 및 Schema Validation 실패 시 재시도하는 처리를 추가했다.
- Bookmark 기반 Chapter/Section 선택을 도입했다.
- Bookmark가 없는 PDF는 Heading 후보 또는 수동 Page Range를 사용할 수 있도록 했다.

**교훈**

> PDF마다 문서 구조가 다르므로 Bookmark만으로 Chapter 탐색을 구현하면 부족하다. 또한 AI 응답은 항상 유효한 JSON이라고 가정해서는 안 된다.

### Phase 3. v4 — Chunk-based Analysis & Hybrid Mindmap

**직접적인 계기**

Berkeley의 Ring Oscillator 관련 논문에서 PDF **p.26–44**(19페이지)를 분석하는 과정에 Claude 출력이 `max_tokens`에 도달해 JSON이 잘리는 오류가 발생했다.

**구현 방향**

- 긴 범위를 기본 약 5페이지 단위 Chunk로 분할한다.
- 길이 제한으로 실패한 Chunk는 더 작은 범위로 재분할해 재시도한다.
- 성공한 Chunk는 즉시 GCS에 저장하여 이후 실행에서 재사용한다.
- Chunk 결과를 통합하여 하나의 Concept Graph로 표현한다.
- Mindmap을 다음 세 가지 보기 방식으로 분리한다.
  - **Hierarchy:** Parent–Child 구조
  - **Focus Graph:** 선택한 Concept 중심
  - **Full Graph:** 전체 Concept와 관계

**남아 있는 한계**

Chunk 통합은 기존 관계를 보존하지만, 모든 Chunk 간 의미적 중복을 완벽하게 제거하거나 새로운 Cross-chunk 관계를 추론하지는 않는다.

### Phase 4. v5 — Integrated HTML Study Report

**새로운 요구사항**

Mindmap은 Concept를 Chunking하여 Step-by-step으로 학습하기 좋지만, 학습 완료 후 **전체 지식을 하나로 정리한 최종 산출물**이 필요했다.

**구현 방향**

- 저장된 분석 결과를 바탕으로 Report Plan을 작성한다.
- Section별로 Claude가 내용을 생성하여 출력 길이 문제를 완화한다.
- 개별 Study Note를 단순 연결하지 않고, Overview와 Technical Explanation으로 정리한다.
- Interactive Terminology Glossary를 제공한다.
- Concept 관계를 설명하는 SVG Diagram을 생성한다.
- 원본 PDF의 선택된 페이지 이미지를 포함한다.
- 브라우저에서 열 수 있는 HTML을 다운로드하고 GCS에 저장한다.

**주의할 범위**

- SVG는 **Concept Diagram**이며 실제 Circuit Schematic의 검증된 복제가 아니다.
- PDF 이미지는 **페이지 Preview**이며 Figure를 자동 식별·정밀 Crop한 결과가 아니다.
- 현재 PDF 분석은 텍스트 중심이다. Claude가 원본 Figure를 직접 Vision 분석하는 기능은 포함되지 않는다.
- Offline HTML에 MathJax/KaTeX가 완전히 포함되어 있지 않아 일부 LaTeX 수식이 원문 형태로 보일 수 있다.

### Phase 5. v6 — Study History & API Cost Tracking

**새로운 요구사항**

- 이전에 요청한 분석 기록을 찾아 다시 학습하고 싶다.
- 각 Claude API 호출의 비용을 추적하고 싶다.

**구현 방향**

- 저장된 분석을 History에서 찾아 해당 Page Range와 Model의 결과를 다시 연다.
- Cache Hit 시 Claude를 다시 호출하지 않는다.
- API 호출별로 Timestamp, Model, Task, Token Usage, Status, Request ID 등을 기록한다.
- Retry와 실패한 호출도 가능한 범위에서 개별 이벤트로 기록한다.
- 사용자가 입력한 Model 단가를 기반으로 USD Estimated Cost를 계산한다.

**비용 계산식**

\[
\text{Estimated Cost (USD)}
=
\frac{
T_{\mathrm{input}} P_{\mathrm{input}}
+
T_{\mathrm{output}} P_{\mathrm{output}}
}{1{,}000{,}000}
\]

- `T_input`, `T_output`: 입력/출력 Token 수
- `P_input`, `P_output`: 100만 Token당 USD 단가

단가가 비어 있다면 비용을 **0이 아닌 Unknown**으로 표시한다. 실제 청구액은 Prompt Caching, 가격 정책, 과금 조건 등에 따라 다를 수 있다. v6 이전의 개별 API 호출 내역은 정확하게 역산할 수 없다.

### Phase 6. v7 — English Technical Terminology & Quality Audit

**새로운 요구사항**

사용자가 기술 용어를 한국어로 번역한 표현보다 **원래의 English Technical Terminology**로 공부하기를 원했다.

예시:

| 지양할 표현 | 권장 표현 |
|---|---|
| 노광 | Lithography |
| 문턱 전압 | Threshold Voltage (Vth) |
| 기생 커패시턴스 | Parasitic Capacitance |
| 전파 지연 | Propagation Delay |
| 공정 변동성 | Process Variation |
| 링 오실레이터 | Ring Oscillator (RO) |

**Language Policy**

```text
- Write explanations in Korean.
- Preserve standard technical terminology in English.
- Do not translate established semiconductor,
  circuit design, EDA, or engineering terms into Korean.
- On first occurrence, provide the full English term
  and its abbreviation when applicable.
- Explain unfamiliar technical terms in Korean
  through the Terminology Glossary.
- Preserve original variable names, equation symbols,
  cell names, and process names.
- Do not invent terminology or abbreviations.
```

**구현 및 검증 방향**

- 새로운 Mindmap/Report Prompt에 정책을 반영한다.
- 번역된 Technical Term, Glossary 누락, PDF Page Reference 이상을 검사한다.
- 검증 결과를 `quality_audit.json`으로 저장한다.
- Prompt/Report Version을 변경해 과거 Cache와 신규 결과를 구분한다.

**검증의 한계**

Quality Audit는 Rule/Pattern 기반의 **Heuristic Audit**다. 실제 기술적 정확성, 원문과의 의미 일치, Figure 해석 정확성을 보증하지 않는다.

### Phase 7. 배포 준비 및 Dependency 오류 대응

**문제**

v7 실행 시 다음 오류가 발생했다.

```text
ModuleNotFoundError: No module named 'mistune'
```

**원인 및 조치**

- `report.py`는 `mistune`을 import한다.
- 확인한 v7 `pyproject.toml`에는 이미 `mistune>=3.0`이 선언되어 있다.
- 따라서 실행 중인 `.venv`에 최신 Dependency가 설치되지 않았을 가능성이 높다.

```bash
cd ~/projects/mindmapping_study
source .venv/bin/activate

python -m pip install -e '.[test]'
python -m pip check
python -m pytest -q
```

**교훈**

> 소스 업데이트 후에는 `app.py`만 교체하지 말고 `pyproject.toml`도 반영하고, 프로젝트 Dependency를 다시 설치해야 한다.

### Phase 8. GitHub 공개 준비

- GitHub Repository 이름을 `textbook_mindmap_study`로 정했다.
- README를 영어로 정리하여 외부 개발자도 기능을 이해할 수 있도록 했다.
- `.gitignore`로 API Key, PDF, Cache, 가상환경을 제외하도록 했다.
- `git remote add origin` 실행 시 `fatal: not a git repository` 오류가 발생했다.
- 원인은 해당 폴더에서 아직 `git init`을 실행하지 않은 것이었다.
- 해결 절차는 **Git 초기화 → Remote 연결 → 파일 검토 → Commit → Push** 순서다.

---

## 4. 현재 주요 기능 요약

| 기능 | 상태 | 설명 |
|---|---|---|
| PDF 등록 및 선택 | 구현 | GCS PDF 등록 및 선택 |
| Chapter/Section 후보 | 구현 | Bookmark 또는 Heading 후보, 수동 범위 |
| Chunk-based Claude Analysis | 구현 | 긴 문서 분할, 중간 Cache |
| Hybrid Mindmap | 구현 | Hierarchy / Focus / Full Graph |
| Concept Study Notes | 구현 | Concept별 한국어 설명과 PDF 페이지 |
| Integrated HTML Report | 구현 | Section별 보고서 및 HTML Export |
| Terminology Glossary | 구현 | English Term + Korean Explanation |
| Concept SVG Diagram | 구현 | 개념 관계 시각화 |
| Source PDF Preview | 구현 | 일부 원본 페이지 이미지 포함 |
| Study History | 구현 | 기존 분석 결과 재사용 |
| API Cost Tracking | 구현 | 호출별 Token 및 추정 비용 |
| Language & Reference Audit | 구현 | Heuristic Warning |
| Figure Vision Analysis | 미구현 | 원본 Figure의 시각적 의미 자동 분석 |
| Circuit Schematic 자동 재구성 | 미구현 | 원본 회로도 정확한 복원 |
| Cross-chunk 의미 통합 고도화 | 제한적 | 완전한 중복 제거/관계 추론 미지원 |
| 완전한 Offline 수식 조판 | 미구현 | MathJax/KaTeX 번들 미포함 |

---

## 5. GCS 기반 데이터 관리

### 5.1 사용 환경

개발 과정에서 사용한 GCS Bucket은 개인 개발 환경에 설정되어 있으며, **공개 GitHub Repository에는 실제 Bucket 정보나 Credential을 코드에 고정하지 않는 것**을 원칙으로 한다.

```dotenv
STORAGE_BACKEND=gcs
GCS_BUCKET=<your-private-gcs-bucket>
GCS_PREFIX=mindmapping_study
```

### 5.2 데이터 구조

아래는 이해를 돕기 위한 **단순화된 구조**다. 실제 세부 경로는 Cache Version과 Model Key에 따라 달라질 수 있다.

```text
<gcs-prefix>/
├── raw/textbooks/
│   └── *.pdf
├── documents/<document-sha256>/
│   ├── original.pdf
│   ├── metadata.json
│   ├── pages.json
│   └── chapter_index_v1.json
├── learning/<document-sha256>/
│   └── p<start>-<end>/
│       └── <version-and-model-key>/
│           ├── result.json
│           ├── mindmap.json
│           ├── notes/
│           └── integrated/
│               ├── report artifacts
│               └── quality_audit.json
└── history/events/YYYY-MM-DD/
    └── <event-id>.json
```

### 5.3 Cache 설계 원칙

- 동일 문서라도 분석 Page Range가 다르면 별도 Cache로 관리한다.
- Prompt Version이나 Model이 바뀌면 결과를 구분한다.
- 완료된 Chunk를 재사용하여 반복 호출을 줄인다.
- 새 버전의 보고서를 생성해도 이전 보고서/분석 결과는 유지한다.
- **Cache 재사용은 비용을 줄이지만, 새 Prompt로 재생성하면 추가 API 비용이 발생할 수 있다.**

---

## 6. WSL 환경 설치 및 실행

### 6.1 개발 환경

```text
OS           : WSL Ubuntu
Project Path : /home/juno_moon/projects/mindmapping_study
Runtime      : Python 3.10+
Virtual Env  : .venv
Web UI       : Streamlit
Default URL  : http://localhost:8501
```

### 6.2 Dependency 설치

```bash
cd ~/projects/mindmapping_study

# 가상환경이 없다면 최초 1회 생성
python3 -m venv .venv

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[test]'
```

`pyproject.toml`이 Dependency의 기준이다. 별도의 `requirements.txt`가 없어도 `pip install -e '.[test]'`로 설치할 수 있다.

### 6.3 `.env` 설정

```bash
cp .env.example .env
```

예시:

```dotenv
STORAGE_BACKEND=gcs
GCS_BUCKET=<your-private-gcs-bucket>
GCS_PREFIX=mindmapping_study

ANTHROPIC_API_KEY=<your-anthropic-api-key>
CLAUDE_MODEL=<available-model-id>
CLAUDE_MAX_TOKENS=8192

REPORT_MAX_TOKENS=4096
REPORT_SECTION_CONCEPTS=5

CLAUDE_INPUT_USD_PER_MTOK=
CLAUDE_OUTPUT_USD_PER_MTOK=
```

> `CLAUDE_MODEL`에는 실제 계정에서 사용 가능한 **Model ID만** 입력한다. `CLAUDE_MODEL=CLAUDE_MODEL=...`처럼 접두사가 중복되지 않도록 주의한다.

### 6.4 GCS 인증

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project <your-google-cloud-project-id>
```

인증 계정에 해당 Bucket의 필요한 Object Read/Write 권한이 있어야 한다.

### 6.5 실행 및 테스트

```bash
cd ~/projects/mindmapping_study
source .venv/bin/activate

python -m pip check
python -m pytest -q

streamlit run app.py
```

---

## 7. GitHub Repository 최초 등록 과정

### 7.1 Repository 정보

| 항목 | 값 |
|---|---|
| GitHub Owner | `junomoon-creator` |
| Repository | `textbook_mindmap_study` |
| Remote URL | `https://github.com/junomoon-creator/textbook_mindmap_study.git` |
| Local Project | `~/projects/mindmapping_study` |
| Branch | `main` |

**중요:** GitHub Repository 이름과 로컬 디렉터리 이름이 달라도 문제없다.

### 7.2 공개 전 보안 점검

Public Repository에 다음 항목이 포함되지 않도록 한다.

- `.env` 및 Anthropic API Key
- Google Cloud ADC Credential, Service Account JSON, Private Key
- 원본 PDF 및 저작권/비공개 자료
- 회사 내부 코드와 데이터
- `.venv`, `__pycache__`, `.pytest_cache`
- 개인용 Local Cache, 임시 결과물

기존 `.gitignore`가 있으면 **덮어쓰지 말고 확인 후 보완**한다.

```bash
cd ~/projects/mindmapping_study
cat .gitignore
```

권장 추가 규칙 예시:

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.mypy_cache/

# Environments
.venv/
venv/
.env
.env.*
!.env.example

# Credentials
*.pem
*.key
*service-account*.json
*credentials*.json

# Local documents / output
data/
local_data/
outputs/
reports/
*.pdf
*.log

# IDE
.vscode/
.idea/
```

> `*.pdf`는 프로젝트에서 PDF 샘플을 Git으로 관리할 필요가 없다는 전제의 정책이다. 공개 가능한 샘플 PDF를 관리하려면 예외 규칙을 별도로 작성한다.

### 7.3 Git 초기화

실제로 발생했던 오류:

```text
fatal: not a git repository (or any of the parent directories): .git
```

`git remote add`를 실행하기 전에 **`git init`이 필요하다**는 뜻이다.

```bash
cd ~/projects/mindmapping_study

git init
git branch -M main
```

`git init`은 `.git/`을 생성할 뿐 기존 Python 코드나 `.env`를 삭제하지 않는다.

### 7.4 GitHub Remote 연결

```bash
git remote -v
```

`origin`이 없다면:

```bash
git remote add origin \
  https://github.com/junomoon-creator/textbook_mindmap_study.git
```

이미 `origin`이 있는데 URL이 다르면:

```bash
git remote set-url origin \
  https://github.com/junomoon-creator/textbook_mindmap_study.git
```

확인:

```bash
git remote -v
```

### 7.5 Commit 전 검토

```bash
git add .

# Stage된 파일 이름 검토
git diff --cached --name-only

# 변경 요약
git diff --cached --stat

# 현재 상태
git status
```

**중요:** `.gitignore`를 뒤늦게 작성했거나 민감한 파일이 이미 Stage되었다면, `git add .` 후에도 반드시 목록을 검토한다. 불필요한 파일을 Stage에서 제외하려면 다음과 같이 한다.

```bash
git restore --staged <file-path>
```

Git 초기화 직후의 첫 Commit처럼 `git restore --staged`가 동작하지 않는 경우에는 다음 명령으로 Index에서만 제거할 수 있다.

```bash
git rm --cached -- <file-path>
```

위 명령은 `--cached` 옵션 때문에 작업 디렉터리의 원본 파일을 삭제하지 않는다.

**이미 과거 Commit에 Secret이 포함되었다면 `.gitignore`만 추가해도 Git History에서 사라지지 않는다.** Push 전에 History 정리와 Secret 교체가 필요하다.

### 7.6 최초 Commit

```bash
git commit -m "feat: initial release of textbook mindmap study"
```

Git 사용자 정보가 설정되지 않았다면:

```bash
git config --global user.name "Your GitHub Name"
git config --global user.email "your-email@example.com"
```

### 7.7 최초 Push

```bash
git push -u origin main
```

HTTPS 인증 시 GitHub 비밀번호 대신 Git Credential Manager, Browser Authentication 또는 Personal Access Token(PAT)이 필요할 수 있다. Token을 소스 코드나 문서에 저장하지 않는다.

정상적으로 완료되면 `main`이 `origin/main`을 추적한다.

### 7.8 GitHub에서 README 확인

브라우저에서 다음 주소를 열어 파일 목록과 README가 정상적으로 표시되는지 확인한다.

https://github.com/junomoon-creator/textbook_mindmap_study

예상 주요 파일:

```text
README.md
.gitignore
.env.example
pyproject.toml
app.py
mindmapping_study/
tests/
```

### 7.9 Push 오류 대응

**오류 A: `fatal: not a git repository`**

```bash
git init
git branch -M main
```

**오류 B: `remote origin already exists`**

```bash
git remote -v
git remote set-url origin \
  https://github.com/junomoon-creator/textbook_mindmap_study.git
```

**오류 C: `src refspec main does not match any`**

최초 Commit이 없거나 `main` 브랜치가 없는 경우가 많다.

```bash
git status
git branch -M main
git add .
git commit -m "Initial commit"
git push -u origin main
```

**오류 D: Push rejected (`non-fast-forward`)**

원격 Repository에 README 등의 기존 Commit이 있을 수 있다.

```bash
git fetch origin
git log --oneline --graph --decorate --all -10
```

로컬/원격 History 관계를 확인한 후 통합한다. 동일한 History를 공유한다면 다음을 사용할 수 있다.

```bash
git pull --rebase origin main
git push -u origin main
```

독립적으로 시작한 두 History라면 별도의 Merge 전략이 필요하다. **무조건 `--force`로 덮어쓰지 않는다.**

---

## 8. 이후 개발 시 Git 운영 방법

### 8.1 일반적인 수정 → Commit → Push

```bash
cd ~/projects/mindmapping_study

git status
git add .
git diff --cached --stat
git commit -m "feat: improve integrated HTML report"
git push
```

### 8.2 Commit Message 예시

```text
feat: add interactive terminology glossary
feat: support study history reload
feat: track Claude API usage costs
fix: handle truncated Claude JSON responses
fix: install missing report dependencies
docs: update Korean project overview
test: add language policy audit tests
refactor: separate report rendering pipeline
```

### 8.3 새 PC에서 프로젝트 Clone

```bash
cd ~/projects

git clone \
  https://github.com/junomoon-creator/textbook_mindmap_study.git

cd textbook_mindmap_study
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
cp .env.example .env
```

`.env`의 API Key와 GCS 설정은 별도로 입력한다. Credential은 GitHub에서 내려받는 방식으로 관리하지 않는다.

### 8.4 다른 기기에서 변경한 후 동기화

```bash
git pull --rebase origin main
```

Local 수정이 남아 있다면 먼저 Commit하거나 Stash하여 충돌을 방지한다.

---

## 9. 주요 문제 해결 기록

| 문제 | 원인/상황 | 해결 방향 |
|---|---|---|
| Claude 404 | 잘못된 Model ID 또는 `.env` 값 형식 | 실제 Model ID 확인 |
| JSON Parsing 실패 | 모델 응답 형식 불일치 | 재시도 및 Schema Validation |
| `max_tokens` Truncation | 긴 PDF 범위에 대한 과도한 단일 응답 | Chunk-based Analysis |
| PDF Bookmark 없음 | PDF에 내장 목차 부재 | Heading 후보 및 수동 Page Range |
| Mindmap 가독성 저하 | 많은 Node/Edge 중첩 | Hierarchy/Focus/Full Graph |
| Note가 분절됨 | Chunk별 정보가 통합되지 않음 | Integrated HTML Report |
| 기술 용어 번역 문제 | 표준 영어 Terminology의 한국어 번역 | Language Policy + Audit |
| API 비용 추적 불가 | 호출별 기록 부재 | v6 History/Cost Logging |
| `ModuleNotFoundError: mistune` | 가상환경에 Dependency 미설치 | `pip install -e '.[test]'` |
| Git Remote 등록 실패 | `git init` 이전에 `git remote add` | Git 초기화 후 Remote 연결 |

---

## 10. 향후 개선 방향

다음은 **현재 구현 완료 항목이 아니라 추가 개발 후보**다.

1. **Figure-aware Analysis:** PDF Figure를 Vision으로 분석하고 설명에 연결
2. **Equation Rendering:** Offline HTML에 MathJax/KaTeX 자산을 포함하거나 사전 렌더링
3. **Semantic Integration:** Chunk 간 중복 개념 정리 및 Cross-chunk Relationship 추론
4. **Verified Architecture Diagram:** 원문 근거와 연결된 Circuit/Block Diagram 생성 및 검토
5. **Source Navigation:** HTML의 Citation 클릭 시 PDF 해당 페이지로 이동
6. **Learning Progress:** 사용자가 공부한 Concept, Bookmark, Review Status 저장
7. **Cost Dashboard:** 날짜·문서·Model별 사용량과 비용 집계
8. **Release Automation:** Pytest 및 Secret Scan을 포함한 GitHub Actions CI

---

## 11. 최종 정리

이 프로젝트는 단순한 PDF Summarizer가 아니라 **Technical Knowledge를 분할·탐색·통합·재학습하는 개인 연구 도구**로 발전했다.

- **Input:** Textbook / Research Paper PDF
- **Analysis:** Claude 기반 Chunk Analysis
- **Exploration:** Interactive Mindmap 및 Concept Study Notes
- **Integration:** Terminology와 Concept Diagram을 포함한 HTML Report
- **Persistence:** GCS Cache와 Study History
- **Governance:** API Cost Tracking, Language Policy, Quality Audit
- **Collaboration/Versioning:** GitHub Repository와 Git 기반 변경 관리

**권장 운영 원칙:** AI가 생성한 기술적 설명은 원본 PDF와 대조하고, GCS/Anthropic Credential과 비공개 자료는 GitHub에 포함하지 않으며, 기능 변경 시 Test와 README를 함께 갱신한다.
