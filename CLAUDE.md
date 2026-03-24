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
| Embeddings | text-embedding-3-small | Or all-MiniLM-L6-v2 for zero API cost |
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

**Day 2 (Tue Mar 24) — ChromaDB + Basic Retrieval**
- [ ] Set up ChromaDB vector store: embed chunks with text-embedding-3-small or all-MiniLM-L6-v2, PersistentClient, re-runnable ingest script
- [ ] Build basic retrieval: retrieve(query: str) -> list[Document], top-k=5 similarity search

**Day 3 (Wed Mar 25) — LLM Generation with Citations**
- [ ] Add LLM generation with citations: pass retrieved chunks + query to LLM, prompt must enforce citing sources as [Source: doc.pdf, p.3], iterate until citations are reliable

**Day 4 (Thu Mar 26) — FastAPI Endpoint + Phase 1 Wrap**
- [ ] Wire up FastAPI /ask POST endpoint: take question, return answer + source chunks
- [ ] End-to-end smoke test: ingest → retrieve → generate → verify output
- [ ] Phase 1 buffer: debug edge cases, clean up code, commit

### Phase 2 — Production-Quality Retrieval (Days 5–7)

**Day 5 (Fri Mar 27) — BM25 + Hybrid Search + Re-ranker**
- [ ] Add BM25 keyword search: install rank_bm25, index same chunks
- [ ] Implement hybrid fusion: run BM25 + vector in parallel, merge via Reciprocal Rank Fusion (RRF)
- [ ] Implement cross-encoder re-ranker: ms-marco-MiniLM-L-6-v2, rescore top-20 → keep top-5

**Day 6 (Mon Mar 30) — Citation Enforcement + Prompt Versioning**
- [ ] Add citation enforcement logic: post-generation parsing for citation markers, confidence threshold → fallback response
- [ ] Move prompts to versioned config: prompts/v1.yaml with system prompt, citation format, fallback message, load at runtime

**Day 7 (Tue Mar 31) — Logging + Phase 2 Integration Test**
- [ ] Add structured logging with structlog: log every query (question, chunk IDs + scores, re-ranker scores, final answer) as JSON
- [ ] Phase 2 integration test: end-to-end hybrid search → re-rank → generate → verify citations, fix regressions from Phase 1

### Phase 2.5 — Langfuse Observability Layer (Day 8)

**Day 8 (Wed Apr 1) — Langfuse Integration**
- [ ] Install & configure Langfuse: set up project on Langfuse cloud (free tier), configure API keys in .env
- [ ] Add Langfuse tracing alongside structlog: wrap retrieve() and generate() with Langfuse traces, track latency, token usage, retrieval scores, cost per query
- [ ] Verify dual logging: run 5-10 test queries, confirm structlog JSON output matches Langfuse dashboard traces

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

---

## Current Status

**Last updated:** Monday Mar 23, 2026
**Current phase:** Phase 1, Day 1 (complete)
**Completed:** Project scaffold, document loader (`ingest/loader.py`), chunker (`ingest/chunker.py`)
**Next task:** Phase 1, Day 2 — ChromaDB vector store + basic retrieval
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

**Corpus status:**
- Only 1 doc ingested so far (`fastapi_first_steps.md`). Remaining 9 sources (LangChain, Pydantic, ChromaDB, Langfuse, React, Docker, Kubernetes, Terraform, Git) still need to be downloaded into `docs/corpus/`.
