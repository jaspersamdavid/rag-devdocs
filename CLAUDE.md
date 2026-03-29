# CLAUDE.md — RAG DevDocs Project

## Project Overview

Production-grade RAG (Retrieval-Augmented Generation) system that ingests developer documentation, retrieves relevant chunks via hybrid search, and answers questions with proper citations. Built as a learning exercise, portfolio piece, and standalone product.

**Repo name:** `rag-devdocs`
**Tagline:** "RAG system for the modern AI application stack — framework to deployment."

---

## Document Corpus (10 Sources)

### Frameworks & Libraries
1. LangChain
2. FastAPI
3. Pydantic
4. ChromaDB
5. Langfuse
6. React

### Developer Tools
7. Docker
8. Kubernetes
9. Terraform
10. Git

**Ingestion approach:** Download markdown docs from each project's GitHub `/docs` folder where possible. Use `PyPDFLoader` for any PDF-based docs, `UnstructuredMarkdownLoader` for markdown, `WebBaseLoader` as fallback.

---

## Tech Stack

| Role | Tool | Notes |
|------|------|-------|
| Orchestration | LangChain | Primary framework |
| Vector store | ChromaDB | PersistentClient, disk-backed |
| Embeddings (prod) | text-embedding-3-small | OpenAI API, stored in `docs_openai` collection |
| Embeddings (local) | all-MiniLM-L6-v2 | Free, stored in `docs_minilm` collection |
| Keyword search | rank_bm25 | Pure Python, no infra |
| Re-ranker | cross-encoder/ms-marco-MiniLM-L-6-v2 | From sentence-transformers, runs locally |
| LLM | GPT-4o / Claude | Abstract behind a generate() function |
| API | FastAPI | Single /ask POST endpoint |
| Logging (local) | structlog | JSON structured logging for dev + CI gate |
| Observability (prod) | Langfuse | LLM tracing, cost tracking, dashboard |
| Evaluation | RAGAS | Faithfulness, answer relevancy, context precision |
| CI | GitHub Actions | Automated eval gate on every PR |

---

## Project Structure

```
rag-devdocs/
├── CLAUDE.md              # This file — project context + progress tracker
├── requirements.txt       # Python dependencies
├── .env                   # API keys (NEVER commit)
├── .gitignore
├── common/
│   ├── __init__.py
│   └── chroma.py          # Shared ChromaDB client, collections, embedding functions
├── ingest/
│   ├── __init__.py
│   ├── loader.py          # Document loaders (PDF, Markdown, Web)
│   ├── chunker.py         # RecursiveCharacterTextSplitter(700/100)
│   └── embed.py           # Embedding + ChromaDB ingest script
├── retriever/
│   ├── __init__.py
│   ├── vector_search.py   # ChromaDB similarity search
│   ├── bm25_search.py     # BM25 keyword search
│   ├── hybrid.py          # RRF fusion of vector + BM25
│   └── reranker.py        # Cross-encoder re-ranking
├── api/
│   ├── __init__.py
│   ├── main.py            # FastAPI app with /ask endpoint
│   └── generate.py        # LLM generation with citation prompting
├── eval/
│   ├── __init__.py
│   ├── golden.json        # 50+ manually curated Q&A pairs
│   └── run_eval.py        # RAGAS eval script with --threshold flag
├── prompts/
│   └── v1.yaml            # Versioned prompts (system, citation format, fallback)
├── docs/
│   └── corpus/            # Downloaded documentation files
└── .github/
    └── workflows/
        └── eval.yml       # CI: run eval on every PR, fail if below threshold
```

---

## Dependencies

```
langchain
langchain-community
langchain-openai
python-dotenv
chromadb
sentence-transformers
fastapi
uvicorn
rank_bm25
openai
anthropic
ragas
structlog
pyyaml
pypdf
unstructured
langfuse
```

---

## Key Design Decisions

- **Citations are non-negotiable.** Every answer must cite its source as `[Source: doc.pdf, p.3]`. No citation = incomplete answer. If confidence is below threshold, return fallback: "I couldn't find sufficient information to answer this confidently."
- **Hybrid search = BM25 + vector.** Merge results using Reciprocal Rank Fusion (RRF). Then re-rank top-20 → top-5 with cross-encoder before passing to LLM.
- **Dual observability.** structlog for local dev and powering the CI eval gate. Langfuse for production monitoring, cost tracking, and trace visualization. Both run in parallel.
- **Prompts are versioned code.** All prompts live in `prompts/v1.yaml`, loaded at runtime, tracked in git.
- **Golden eval dataset is manually written.** No AI-generated Q&A pairs. 50+ triples: question, ground_truth_answer, source_doc.
- **LLM is abstracted.** `generate()` function wraps the LLM call so GPT-4o and Claude can be swapped without changing retrieval logic.
- **Order matters.** Phase 1 must be solid before Phase 2. Phase 2 before Phase 3. Don't skip ahead.

---

## Coding Conventions

- Python 3.11+
- Type hints on all function signatures
- Docstrings on all public functions
- Use `pathlib.Path` for file paths, not string concatenation
- All config (API keys, model names, chunk sizes) via environment variables or YAML — never hardcoded
- Commit after completing each task, not at end of day
- Meaningful commit messages: `feat: add BM25 keyword search with RRF fusion`

---

## Progress Tracker

> **How to use:** Mark tasks `[x]` when completed. When Jasper asks "what's next" or "what's remaining", read this checklist to determine current status.

### Pre-Sprint Prep (Sunday Mar 22)
- [x] Pick document corpus — decided: 10 sources (LangChain, FastAPI, Pydantic, ChromaDB, Langfuse, React, Docker, Kubernetes, Terraform, Git)
- [x] Install core dependencies (`pip install -r requirements.txt`)
- [x] Create GitHub repo + clone locally
- [x] Initialize folder structure
- [x] Add this CLAUDE.md to project root

### Phase 1 — Core RAG Pipeline (Days 1–4)

**Day 1 (Mon Mar 23) — Scaffold + Loader + Chunking**
- [x] Create project scaffold: pyproject.toml or requirements.txt, folder structure, git init
- [x] Build document loader: PyPDFLoader, TextLoader (for .md), WebBaseLoader, output Document objects with metadata (source, page)
- [x] Implement chunking: RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=100), preserve metadata through splits

**Day 2 (Tue Mar 24) — ChromaDB + Dual Embeddings + Basic Retrieval**
- [x] Set up OpenAI API key: create API account at platform.openai.com (same login as ChatGPT), add payment method, generate API key, add to .env as OPENAI_API_KEY
- [x] Build `ingest/embed.py`: support both embedding models, write to separate ChromaDB collections (`docs_openai` for text-embedding-3-small, `docs_minilm` for all-MiniLM-L6-v2), PersistentClient, re-runnable ingest script
- [x] Run OpenAI embedding: embed 60,812 chunks with text-embedding-3-small → `docs_openai` collection (~$0.12, production flow)
- [x] Build `retriever/vector_search.py`: retrieve(query: str) → list[Document], top-k=5 similarity search, switchable between collections via ACTIVE_COLLECTION config
- [x] Test retrieval against `docs_openai` collection with sample queries
- [x] Run MiniLM embedding: embed 60,812 chunks with all-MiniLM-L6-v2 → `docs_minilm` collection (free, local, done last)
- [x] Compare both: run same queries against both collections, compare retrieved chunks for learning

**Day 3 (Wed Mar 25) — LLM Generation with Citations**
- [x] Add LLM generation with citations: pass retrieved chunks + query to LLM, prompt must enforce citing sources as [Source: doc.pdf, p.3], iterate until citations are reliable

**Day 4 (Thu Mar 26) — FastAPI Endpoint + Phase 1 Wrap**
- [x] Wire up FastAPI /ask POST endpoint: take question, return answer + source chunks
- [x] End-to-end smoke test: ingest → retrieve → generate → verify output
- [x] Phase 1 buffer: debug edge cases, clean up code, commit

### Phase 2 — Production-Quality Retrieval (Days 5–7)

**Day 5 (Fri Mar 27) — BM25 + Hybrid Search + Re-ranker**
- [x] Add BM25 keyword search: install rank_bm25, index same chunks
- [x] Implement hybrid fusion: run BM25 + vector in parallel, merge via Reciprocal Rank Fusion (RRF)
- [x] Implement cross-encoder re-ranker: ms-marco-MiniLM-L-6-v2, rescore top-20 → keep top-5

**Day 6 (Fri Mar 27) — Citation Enforcement + Prompt Versioning**
- [x] Add citation enforcement logic: post-generation parsing for citation markers, confidence threshold → fallback response
- [x] Move prompts to versioned config: prompts/v1.yaml with system prompt, citation format, fallback message, load at runtime (already done in Day 3)

**Day 7 (Sat Mar 29) — Logging + Phase 2 Integration Test**
- [x] Add structured logging with structlog: log every query (question, chunk IDs + scores, re-ranker scores, final answer) as JSON
- [x] Phase 2 integration test: end-to-end hybrid search → re-rank → generate → verify citations, fix regressions from Phase 1

### Phase 2.5 — Langfuse Observability Layer (Day 8)

**Day 8 (Sat Mar 29) — Langfuse Integration**
- [x] Install & configure Langfuse: set up project on Langfuse cloud (free tier), configure API keys in .env
- [x] Add Langfuse tracing alongside structlog: wrap retrieve() and generate() with Langfuse traces, track latency, token usage, retrieval scores, cost per query
- [x] Verify dual logging: run 5-10 test queries, confirm structlog JSON output matches Langfuse dashboard traces

### Phase 3 — Eval Pipeline + CI (Days 9–11)

**Day 9 (Thu Apr 2) — Golden Eval Dataset (Batch 1)**
- [ ] Curate golden eval dataset batch 1: manually write 25-30 question/answer/source_doc triples (NO AI generation)

**Day 10 (Fri Apr 3) — Finish Dataset + RAGAS Eval**
- [ ] Finish golden dataset batch 2: remaining 20-25 Q&A pairs → eval/golden.json (50+ total)
- [ ] Set up RAGAS evaluation: measure faithfulness, answer relevancy, context precision
- [ ] Write eval script: run_eval.py with --threshold flag, exits code 1 if faithfulness below 0.75

**Day 11 (Mon Apr 6) — CI Pipeline + README + Ship It**
- [ ] Wire eval into GitHub Actions: .github/workflows/eval.yml, on PR: install → run_eval.py --threshold 0.75 → fail if below
- [ ] Write README: architecture, how to ingest new corpus, how to run locally, eval score explanation, dual observability docs
- [ ] Add GitHub Actions eval badge
- [ ] Final cleanup, clean git history, push, pin repo

### Phase 4 — LangChain Integration + LangSmith (Days 12–13)

**Day 12 — LangChain Method Implementation**
- [ ] Create `langchain_method/` folder with LangChain equivalents of all custom retrieval and generation code
- [ ] `langchain_method/retriever.py`: Replace custom vector search + BM25 with `Chroma.as_retriever()` + `BM25Retriever` + `EnsembleRetriever` (RRF built-in)
- [ ] `langchain_method/reranker.py`: Replace custom cross-encoder with `CrossEncoderReranker` from langchain_community
- [ ] `langchain_method/generate.py`: Replace direct OpenAI API call with `ChatOpenAI` + `PromptTemplate` + chain
- [ ] `langchain_method/pipeline.py`: Wire everything into a `RetrievalQA` or LCEL chain — single entry point that matches `hybrid_retrieve()` interface
- [ ] Swap import in `cli.py` and `api/main.py` to use LangChain method, verify same output

**Day 13 — LangSmith Observability + A/B Comparison**
- [ ] Set up LangSmith: create account, configure API keys, connect to LangChain pipeline
- [ ] Run same test queries through both methods (custom + LangChain), compare LangSmith vs Langfuse dashboards
- [ ] Run RAGAS eval on both methods — same golden dataset, compare faithfulness and answer relevancy scores
- [ ] Document findings: which approach is better for what, tradeoffs between custom code and LangChain abstractions

---

## Current Status

**Last updated:** Saturday Mar 29, 2026
**Current phase:** Phase 2 + 2.5 complete (Days 5–8 done)
**Completed:** BM25 keyword search, hybrid RRF fusion, cross-encoder re-ranker, citation enforcement, prompt versioning, structlog logging, integration test, Langfuse observability
**Next task:** Phase 3, Day 9 — Golden eval dataset (batch 1)
**Blockers:** `ragas` install deferred to Phase 3 (llvmlite/numba build issue on Python 3.12, not needed until then)

> **Update this section** every time a task is completed or status changes.

---

## Observations & Notes

### Day 1 — Mar 23, 2026

**Dependency issues encountered:**
- `torch 2.2.2` is the latest available for Python 3.12 x86_64. Newer `transformers` (v5.x) requires `torch>=2.4`, causing an `nn` NameError at import. **Fix:** pinned `transformers<4.52` (installed 4.51.3).
- `numpy 2.x` is incompatible with `torch 2.2.2` (compiled against NumPy 1.x ABI). **Fix:** pinned `numpy<2` (installed 1.26.4).
- `UnstructuredMarkdownLoader` requires `unstructured[md]` extras, which pulls in `llvmlite` — fails to build on this system. **Fix:** switched to `TextLoader` for `.md` files. This is actually better for RAG since it preserves raw markdown structure (headings, code blocks) that the chunker uses as split points.
- `unstructured` package has many missing optional deps (`emoji`, `markdown`, `spacy`, etc.) — only relevant if we use its parsers. Currently not needed since we use `TextLoader` for markdown and `PyPDFLoader` for PDFs.

**Chunking results (fastapi_first_steps.md):**
- 7,327 chars → 13 chunks, avg ~620 chars each (max 700 as configured)
- Splitter correctly breaks on paragraph/section boundaries — no mid-sentence cuts observed
- 100-char overlap working as expected at chunk boundaries
- Metadata (`source`) preserved through all splits

**Corpus download (all 10 sources):**
- Downloaded via parallel sparse-checkout (`scripts/download_corpus.sh`)
- Loader updated to support `.mdx` (Langfuse, ChromaDB) and `.adoc` (Git) formats
- Full corpus: 4,396 files → 60,812 chunks (31.6M chars, avg 519 chars/chunk)
- Breakdown: kubernetes 21,635 | docker 14,835 | git 10,307 | react 7,320 | fastapi 2,780 | chromadb 1,796 | pydantic 1,297 | terraform 524 | langfuse 178 | langchain 140

**Embedding strategy decision:**
- Will use **both** models: text-embedding-3-small (OpenAI, production) and all-MiniLM-L6-v2 (local, free)
- Stored in separate ChromaDB collections (`docs_openai`, `docs_minilm`) for A/B comparison
- OpenAI embedding cost for 60k chunks: ~$0.12
- MiniLM is already installed locally via sentence-transformers
- Production flow uses OpenAI; MiniLM run last as free alternative for learning/comparison

**Cost analysis (full project):**
- Embeddings (OpenAI text-embedding-3-small): ~$0.12 one-time
- LLM generation (GPT-4o or Claude): ~$0.008 per query
- RAGAS eval (50+ queries): ~$0.40-0.50
- Total estimated: $2-5 (or use Anthropic $5 free API credits for generation)
- Re-ranker (ms-marco-MiniLM) runs locally, always free

### Day 2 — Mar 25, 2026

**New dependencies added:**
- `langchain-openai` — provides OpenAI embedding support for LangChain/ChromaDB
- `python-dotenv` — loads `.env` file into environment variables (was already installed, added to requirements.txt)

**Refactored shared code into `common/chroma.py`:**
- Embedding functions (OpenAI + MiniLM) were duplicated in `ingest/embed.py` and `retriever/vector_search.py`
- Extracted into `common/chroma.py`: `get_chroma_client()`, `get_embedding_function()`, `get_collection()`, collection name constants
- Both modules now import from single source of truth

**Embedding results:**
- OpenAI (text-embedding-3-small): 60,812 chunks in 438s (~7 min), 1536-dim vectors, ~$0.12
- MiniLM (all-MiniLM-L6-v2): 60,812 chunks in 2,134s (~35 min), 384-dim vectors, free
- MiniLM 5x slower because it runs on local CPU vs OpenAI's cloud GPUs

**Retrieval quality comparison (OpenAI vs MiniLM):**
- OpenAI consistently more accurate — finds the most relevant docs (e.g., fastapi/tutorial/first-steps.md for FastAPI questions)
- MiniLM sometimes pulls tangential results (e.g., release-notes.md instead of tutorials)
- Both models correctly identify the right source project (Docker questions → Docker docs, etc.)
- Pydantic queries performed well on both models
- Confirms decision: OpenAI for production, MiniLM for learning/comparison

### Day 3 — Mar 26, 2026

**LLM generation with citations:**
- Built `api/generate.py` with `generate()` function wrapping OpenAI GPT-4o chat completions API
- System prompt enforces citation format `[Source: fastapi/index.md]` and fallback when context is insufficient
- `temperature=0.2` for deterministic, grounded answers
- Source paths cleaned: strips local corpus prefix so citations show relative paths (e.g., `fastapi/index.md` not full absolute path)
- LLM model configurable via `LLM_MODEL` env var, defaults to `gpt-4o`

**Versioned prompt config:**
- Created `prompts/v1.yaml` with system prompt, fallback message, context template, and user template
- Loaded once at module import, not per-call
- Prompts tracked in git — changes are visible in diff history

**Interactive CLI:**
- Added `cli.py` with `while True` input loop: `devdoc>` prompt → retrieve → generate → print answer
- Registered as `ragdevdocs` console command via `pyproject.toml` entry point
- Installed with `pip install -e .` (editable mode) for development

**Observations on retrieval quality:**
- Vector-only search struggles with code example queries — retrieves descriptive text instead of code snippets
- Semantic queries ("what is FastAPI", "benefits of FastAPI") work well
- Phase 2 hybrid search (BM25 + vector) will address the code retrieval gap

### Day 4 — Mar 26, 2026

**FastAPI /ask endpoint:**
- Built `api/main.py` with POST `/ask` and GET `/health` endpoints
- Request/response models defined with Pydantic: `AskRequest`, `AskResponse`, `SourceChunk`
- Response includes both the cited answer and the raw source chunks with similarity distances
- Auto-generated Swagger UI at `/docs` for interactive testing

**Edge case testing:**
- Empty question `""` → returns 400 with "Question cannot be empty"
- Missing `question` field → Pydantic auto-rejects with 422
- No JSON body → Pydantic auto-rejects with 422
- Off-topic question ("How do I cook pasta?") → LLM correctly declines, no hallucination
- Normal questions → cited answers with source chunks

**Phase 1 complete:**
- Full pipeline working: ingest → embed → retrieve → generate → serve via API
- Two access methods: interactive CLI (`ragdevdocs`) and HTTP API (`/ask`)
- Known limitation: vector-only search misses code examples — Phase 2 hybrid search will fix this

### Day 5 — Mar 27, 2026

**BM25 keyword search (`retriever/bm25_search.py`):**
- Loads all 60,812 chunks from ChromaDB into memory, tokenises into words, builds BM25Okapi index
- Lazy initialisation: index built on first call, cached in module-level variables for subsequent calls
- Had to batch ChromaDB `.get()` calls in groups of 5,000 — SQLite throws "too many SQL variables" error when fetching all 60k at once
- BM25 scores attached to document metadata as `bm25_score` for transparency

**Hybrid fusion (`retriever/hybrid.py`):**
- Runs vector search (top 20) + BM25 (top 20) in parallel
- Merges via Reciprocal Rank Fusion (RRF): `score = sum(1/(60+rank))` for each list a doc appears in
- Documents appearing in both lists get boosted scores
- RRF constant k=60 from original Cormack et al. (2009) paper

**Cross-encoder re-ranker (`retriever/reranker.py`):**
- Uses `cross-encoder/ms-marco-MiniLM-L-6-v2` from sentence-transformers
- Model downloaded on first use (~90MB), cached locally after that
- Takes top 20 RRF results, re-scores by looking at (query, chunk) pairs together, keeps top 5
- Re-rank scores attached to metadata as `rerank_score`

**Pipeline change:**
- CLI and API updated: `from retriever.hybrid import hybrid_retrieve` replaces `from retriever.vector_search import retrieve`
- Full pipeline: query → vector (20) + BM25 (20) → RRF merge → cross-encoder re-rank → top 5 → LLM

**Retrieval quality testing:**
- Built `scripts/test_retrieval.py` to compare all 4 stages side by side (vector, BM25, RRF, re-ranked)
- Tested "what are all embedding models available in chromadb" — hybrid found Baseten and HuggingFace sparse models that vector-only missed
- Perplexity embedding page still not in top 20 for broad queries — common words ("embedding", "models") compete across 60k chunks
- Specific queries like "perplexity embedding chromadb" work perfectly — BM25 nails exact keyword matches
- Identified need for metadata filtering and intent classification for broad "list all" type queries (documented in DEVDOCS_ENHANCEMENTS.md)

### Day 6 — Mar 27, 2026

**Citation enforcement (`api/generate.py`):**
- Added regex-based citation parsing: `CITATION_PATTERN = re.compile(r"\[Source:\s*[^\]]+\]")`
- `_extract_citations(answer)` finds all `[Source: ...]` markers in LLM output
- `_enforce_citations(answer)` checks if at least one citation exists; returns fallback message if none found
- Hooked into `generate()`: LLM answer passes through enforcement before reaching user
- Tested: normal questions pass with citations, off-topic questions ("how do I cook pasta") correctly trigger fallback

**Prompt versioning:**
- Already completed in Day 3 — `prompts/v1.yaml` with system prompt, fallback, context_template, user_template
- No additional work needed

### Day 7 — Mar 29, 2026

**Structured logging (`common/logging.py`):**
- Created centralised structlog configuration with `configure_logging()` and `get_logger(name)`
- Uses `ConsoleRenderer` for local dev (human-readable), swappable to `JSONRenderer` for production/CI
- Processors chain: `add_log_level` → `TimeStamper(iso)` → `ConsoleRenderer`
- Called once at app startup in both `cli.py` and `api/main.py`

**Pipeline instrumentation:**
- `retriever/hybrid.py`: every stage timed with `time.perf_counter()` and logged — vector search, BM25, RRF fusion, cross-encoder re-rank, plus total duration
- `api/generate.py`: LLM call timed, token usage logged (prompt_tokens, completion_tokens, total_tokens), citation enforcement logged at info/warning level
- `api/main.py` and `cli.py`: full request lifecycle logged (received → complete with duration)
- Each log entry includes top source paths for quick debugging without reading full result sets

**Integration test (`scripts/test_integration.py`):**
- 8 predefined test cases across 7 documentation sources + 1 off-topic
- Each test checks: no crash, answer not empty, citations present (except off-topic)
- Exit code 0/1 for CI compatibility
- All 8 tests passed on first run — pipeline is stable

**Performance observations from integration test:**
- First query slow due to lazy init: vector search 2723ms, BM25 6334ms (building 60k-chunk index)
- Subsequent queries fast: vector 400-700ms, BM25 130-330ms (index cached)
- LLM generation is the bottleneck: 1400-4100ms per query (OpenAI API round trip)
- RRF fusion is essentially free: 0.2-4.7ms (pure math, no models)

### Day 8 — Mar 29, 2026

**Langfuse integration (`common/langfuse_client.py`):**
- Langfuse v4 installed (4.0.1) — API completely different from v2/v3 documentation
- v4 uses `start_observation(name, as_type)` instead of old `.trace()` / `.span()` / `.generation()` methods
- v4 pattern: `start_observation()` → `.update(output, metadata)` → `.end()` — `end()` takes no args
- Client auto-reads `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` from environment
- Langfuse US region: `https://us.cloud.langfuse.com`

**Tracing architecture:**
- Top-level span created in `cli.py` / `api/main.py` per query (name: "rag-query")
- Passed as `trace` parameter through `hybrid_retrieve()` → each retrieval stage creates child spans
- Passed to `generate()` → creates a "generation" observation with model name, prompt, answer, token usage
- Langfuse auto-calculates cost from token counts for GPT-4o

**Key lesson — span timing:**
- Initial implementation created spans AFTER work was done → Langfuse showed 0ms duration
- Fix: open span BEFORE the work, close AFTER — Langfuse measures wall-clock time between `start_observation()` and `.end()`
- Structlog duration (manual `perf_counter()`) and Langfuse duration (automatic start/end) now match

**Dual observability confirmed:**
- structlog: local terminal output, per-stage timing, top sources, token counts
- Langfuse: cloud dashboard with trace visualization, nested spans, cost tracking, token breakdown
- Both show consistent data for the same queries
