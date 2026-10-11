# Textbook Mindmap Study

**An AI-powered workspace for exploring technical PDFs, building concept maps, and creating reusable study reports.**

Textbook Mindmap Study is a standalone Python/Streamlit application that uses **Anthropic Claude** to analyze textbooks and research papers. It turns selected PDF pages into interactive mind maps, concept-level study notes, and integrated HTML reports. **Google Cloud Storage (GCS)** stores documents and generated artifacts so you can revisit past study sessions without rerunning the same analysis.

The application is particularly suited to technical subjects such as semiconductor devices, circuit design, EDA, and engineering. Explanations are written in **Korean**, while established **technical terminology remains in English**.

> **Project status:** Personal learning/research tool. AI-generated explanations, equations, references, and inferred document structure should be checked against the original PDF.

## Features

### PDF ingestion and chapter selection
- Register PDFs already uploaded to a configured GCS bucket.
- Select PDF bookmark chapters/sections, a manual page range, or inferred heading candidates when bookmarks are absent.
- Inspect source PDF pages alongside generated explanations.
- Use physical PDF page numbers for analysis and citations; printed page numbering may differ.

### Chunk-based Claude analysis
- Split long page ranges into smaller chunks (default: five pages).
- Retry certain oversized/truncated chunks using smaller ranges.
- Cache completed chunks for reuse if a later chunk fails.
- Merge chunk outputs into a navigable concept map while retaining source-page references.

**Important:** Chunk aggregation preserves existing relationships but does **not** perform comprehensive semantic deduplication or infer new relationships across chunks.

### Interactive mind maps and study notes
- Switch between **Hierarchy**, **Focus Graph**, and **Full Graph** views.
- Select concepts to read associated Korean study notes and source-page references.
- Preserve technical terms, symbols, variable names, cell names, and process names in English where appropriate.

### Integrated HTML study reports
- Generate a report plan, glossary, and section-by-section technical explanations from saved analysis results.
- Include an interactive **Terminology Glossary** with Korean explanations of English technical terms.
- Embed a conceptual SVG diagram and up to four source **PDF page previews**.
- Export a self-contained HTML report for offline reading and browser printing.
- Cache completed report sections and final report artifacts.

**Scope:** The generated SVG is a **concept diagram**, not a verified reproduction of a source circuit schematic. Source images are **page previews**, not automatically identified or cropped figures. The current Claude pipeline is based on **extracted PDF text**; it does not visually analyze source figures. Offline HTML does not bundle MathJax/KaTeX, so LaTeX may appear as source text.

### Language policy and report quality audit
- Write narrative explanations in Korean.
- Keep standard semiconductor, circuit-design, EDA, and engineering terminology in English.
- Introduce full English terms and abbreviations on first use when applicable.
- Explain unfamiliar terms in Korean through the glossary.
- Preserve original equations, symbols, variable names, and technical identifiers.
- Flag selected translated terms, glossary issues, and citation-page inconsistencies in `quality_audit.json`.

The audit is **heuristic**: it does not guarantee factual correctness or verify a citation against the actual source passage.

### Study history and API cost tracking
- Find completed analyses and reopen saved page ranges, mind maps, notes, and reports.
- Reuse cached artifacts without additional Claude API requests.
- Log each new Claude request, including retries and failed requests, with token usage and request metadata when available.
- Estimate USD cost using **user-configured per-million-token prices**; unset prices are reported as unknown, not zero.

Cost estimates are **not invoices** and may differ from actual billing because of caching, pricing tiers, taxes, and other pricing rules. Detailed per-call history cannot be reconstructed for requests made before logging was introduced.

## Workflow

```text
Technical PDF
    |
    v
Choose Chapter / Section / Page Range
    |
    v
Chunked Claude Analysis --> Cached Chunk Results
    |
    v
Interactive Mindmap + Concept Study Notes
    |
    v
Integrated Report Planning + Section Generation
    |
    v
Interactive HTML Study Report
    |
    +--> Study History (reload previous results)
    +--> API Usage & Estimated Cost Logs
```

## Technology stack

| Component | Technology |
| --- | --- |
| Application | Python 3.10+, Streamlit |
| AI analysis | Anthropic Claude API |
| PDF extraction and page previews | PyMuPDF |
| Concept visualization | `streamlit-agraph` |
| HTML/Markdown processing | Mistune, SVG |
| Structured data validation | Pydantic |
| Storage | Google Cloud Storage (or configured local backend) |
| Tests | Pytest |

## Getting started

### Prerequisites

- Python **3.10 or newer** (WSL Ubuntu is a supported development setup).
- An **Anthropic API key** and access to a supported Claude model.
- A Google Cloud project, a private GCS bucket, and **Application Default Credentials (ADC)** if using GCS.

### Installation

```bash
git clone https://github.com/junomoon-creator/textbook_mindmap_study.git
cd textbook_mindmap_study

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[test]'

cp .env.example .env
```

Edit `.env` with your own credentials and storage settings. The application reads configuration from `.env`; **never commit this file**.

### Configuration

```dotenv
# Storage
STORAGE_BACKEND=gcs
GCS_BUCKET=<your-private-gcs-bucket>
GCS_PREFIX=mindmapping_study

# Claude
ANTHROPIC_API_KEY=<your-anthropic-api-key>
CLAUDE_MODEL=<model-id-available-to-your-account>
CLAUDE_MAX_TOKENS=8192
CLAUDE_JSON_RETRIES=1

# Integrated report
REPORT_MAX_TOKENS=4096
REPORT_SECTION_CONCEPTS=5

# Optional: current model prices in USD per 1 million tokens
# Leave blank to show cost as unknown.
CLAUDE_INPUT_USD_PER_MTOK=
CLAUDE_OUTPUT_USD_PER_MTOK=
```

Use an actual model ID and the pricing that applies to your Anthropic account. The values above are **configuration examples**, not a guarantee that a particular model or price is available.

For GCS authentication in WSL:

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project <your-google-cloud-project-id>
```

The account must have the required object listing, reading, and writing permissions for your bucket. Do not commit service-account keys.

### Run the app

```bash
source .venv/bin/activate
streamlit run app.py
```

Open the URL printed by Streamlit (typically `http://localhost:8501`).

### Study a document

1. Register a PDF already present under the configured GCS `raw/textbooks/` prefix.
2. Choose a chapter/section or a manual PDF page range.
3. Run Claude analysis and explore the **Mindmap** and concept notes.
4. Open **Integrated HTML Study Report**, generate the report, and prepare/download the HTML file.
5. Use **Study History & API Cost** to reopen completed analyses and inspect request logs.

Labels in the current Streamlit UI may be in Korean.

## Storage and caching

A simplified GCS layout is shown below. Exact version/hash subdirectories depend on the selected model, prompt version, page range, and report version.

```text
<gcs-prefix>/
├── raw/textbooks/                  # PDFs uploaded by the user
├── documents/<document-sha256>/
│   ├── original.pdf
│   ├── metadata.json
│   ├── pages.json
│   └── chapter_index_v1.json       # when applicable
├── learning/<document-sha256>/
│   └── p<start>-<end>/
│       └── <version-and-model-key>/
│           ├── result.json
│           ├── mindmap.json
│           ├── notes/
│           └── integrated/         # report artifacts and audits
└── history/events/YYYY-MM-DD/
    └── <event-id>.json             # one record per Claude request
```

Previously cached analyses are preserved when a newer analysis/report version uses a different cache key. **Regeneration may incur additional API charges.**

## Testing

```bash
python -m pip install -e '.[test]'
python -m pytest -q
python -m pip check
```

## Limitations

- PDF extraction is **text-first**. Scanned PDFs require OCR, which is not provided by this version. Complex equations and multi-column layouts may extract imperfectly.
- Inferred chapter headings and PDF page references should be verified manually.
- Cross-chunk knowledge merging does not yet provide full semantic reconciliation.
- HTML diagrams are conceptual, and source PDF figures are not visually interpreted by Claude.
- Offline HTML does not include a complete mathematical typesetting engine.
- No built-in multi-user authentication, background job queue, or hard spending limits are provided.
- Costs are estimates; actual Anthropic billing is authoritative.

## Security and responsible use

- Keep your GCS bucket **private** and limit its IAM permissions.
- Never commit `.env`, API keys, ADC credentials, service-account JSON, or private source PDFs.
- Check `git status` and `git diff --cached` before pushing to a public repository.
- Do not upload confidential company documents or third-party materials without authorization.
- Review AI-generated technical claims against the original document before using them in engineering decisions.

## Version history

| Version | Major additions |
| --- | --- |
| v4 | Chunk-based analysis, inferred outlines, hybrid mindmap views |
| v5 | Integrated HTML reports, glossary, conceptual diagrams, PDF page previews |
| v6 | Study history, per-request API usage and estimated cost logs |
| v7 | Stronger English technical terminology policy and heuristic quality audit |

## License

No license is specified in this repository by default. Add a `LICENSE` file if you intend to grant others permission to use, modify, or redistribute the code.
