# RAG DevDocs

**RAG system for the modern AI application stack — framework to deployment.**

A production-grade Retrieval-Augmented Generation (RAG) system that ingests developer documentation from 10 popular frameworks and tools, retrieves relevant chunks via hybrid search, and answers questions with proper citations. Every answer is grounded in the actual documentation — no hallucinations, no uncited claims.

---

## What It Does

Ask a question about any of the 10 supported documentation sources, and RAG DevDocs will:

1. **Search** across 60,000+ document chunks using hybrid search (semantic + keyword)
2. **Re-rank** candidates with a cross-encoder for maximum precision
3. **Generate** a grounded answer using GPT-4o with enforced citations
4. **Cite** every claim with `[Source: filename]` markers pointing to the actual docs

If the system can't find sufficient information, it tells you honestly instead of guessing.

### Example

```
devdoc> what is FastAPI?

FastAPI is a modern, fast (high-performance) web framework for building APIs
with Python based on standard Python type hints [Source: fastapi/index.md].
It is designed to be easy to use and learn, while also being fast to code
and ready for production [Source: fastapi/tutorial/first-steps.md].
```

---

## Supported Documentation

| Category | Sources |
|----------|---------|
| Frameworks & Libraries | LangChain, FastAPI, Pydantic, ChromaDB, Langfuse, React |
| Developer Tools | Docker, Kubernetes, Terraform, Git |

**Corpus stats:** 4,396 files, 60,812 chunks, 31.6M characters

---

## How It Works

### Architecture

```
                          User Question
                               |
                               v
                 +-----------------------------+
                 |     Hybrid Retrieval        |
                 |                             |
                 |  Vector Search (semantic)   |
                 |         +                   |
                 |  BM25 Search (keyword)      |
                 |         |                   |
                 |    RRF Fusion (merge)       |
                 |         |                   |
                 |  Cross-Encoder Re-ranker    |
                 |     (top 20 -> top 5)       |
                 +-----------------------------+
                               |
                               v
                 +-----------------------------+
                 |     LLM Generation          |
                 |                             |
                 |  GPT-4o with citation       |
                 |  enforcement prompt         |
                 |         |                   |
                 |  Post-generation check:     |
                 |  citations present?         |
                 |   yes -> return answer      |
                 |   no  -> return fallback    |
                 +-----------------------------+
                               |
                               v
                     Cited Answer + Sources
```

### Retrieval Pipeline (Phase 2)

The retrieval system uses a multi-stage approach to find the most relevant documentation chunks:

1. **Vector Search** — Embeds the query using OpenAI's `text-embedding-3-small` and finds semantically similar chunks via cosine similarity in ChromaDB. Good at understanding meaning ("what does FastAPI do?" finds description pages).

2. **BM25 Keyword Search** — Tokenises the query into words and scores every chunk by keyword overlap using the BM25Okapi algorithm. Good at exact matches ("PerplexityEmbeddingFunction" finds that specific page).

3. **Reciprocal Rank Fusion (RRF)** — Merges the vector and BM25 results into a single ranked list. Documents appearing in both lists get boosted. Formula: `score = sum(1/(60+rank))` per list.

4. **Cross-Encoder Re-ranking** — Takes the top 20 merged results and re-scores them using `ms-marco-MiniLM-L-6-v2`. Unlike embedding models that encode query and document separately, the cross-encoder reads both together for more accurate relevance judgments. Keeps the top 5.

### Citation Enforcement

The system prompt instructs the LLM to cite every claim. After generation, a regex-based enforcement layer scans the answer for `[Source: ...]` markers. If no citations are found, the answer is rejected and replaced with a fallback message. This ensures no uncited content reaches the user.

---

## Tech Stack

| Role | Tool | Notes |
|------|------|-------|
| Orchestration | LangChain | Primary framework |
| Vector store | ChromaDB | PersistentClient, disk-backed |
| Embeddings (prod) | text-embedding-3-small | OpenAI API |
| Embeddings (local) | all-MiniLM-L6-v2 | Free, local alternative |
| Keyword search | rank_bm25 | Pure Python BM25Okapi |
| Re-ranker | ms-marco-MiniLM-L-6-v2 | Cross-encoder, runs locally |
| LLM | GPT-4o | Abstracted behind `generate()` |
| API | FastAPI | POST `/ask` endpoint |
| CLI | Custom | Interactive `devdoc>` prompt |

---

## Installation & Setup

### Prerequisites

- Python 3.11+
- An OpenAI API key (for embeddings and LLM generation)

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/rag-devdocs.git
cd rag-devdocs
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Set up your API key

Create a `.env` file in the project root:

```bash
OPENAI_API_KEY=your-openai-api-key-here
```

### 4. Install the package in editable mode

```bash
pip install -e .
```

This registers the `ragdevdocs` CLI command.

### 5. Ingest the documentation corpus

If you need to re-embed the documentation (first time setup or after corpus changes):

```bash
python -m ingest.embed
```

This embeds all document chunks into ChromaDB. The OpenAI embedding costs ~$0.12 for the full 60k corpus.

---

## Usage

### Interactive CLI

```bash
ragdevdocs
```

This starts the interactive prompt:

```
RAG DevDocs — Ask questions about developer documentation
Type 'exit' or 'quit' to stop.

devdoc> how do I define a route in FastAPI?

FastAPI allows you to define routes using Python decorators. You use
@app.get("/path") or @app.post("/path") to define endpoints...
[Source: fastapi/tutorial/first-steps.md]

devdoc> what is a Kubernetes pod?

A Pod is the smallest deployable unit in Kubernetes...
[Source: kubernetes/concepts/workloads/pods/index.md]

devdoc> exit
Goodbye!
```

### HTTP API

Start the FastAPI server:

```bash
uvicorn api.main:app --reload
```

Send a question:

```bash
curl -X POST http://localhost:8000/ask \
     -H "Content-Type: application/json" \
     -d '{"question": "How do I create a Docker container?"}'
```

Response:

```json
{
  "answer": "To create a Docker container, you can use the `docker run` command... [Source: docker/guides/getting-started.md]",
  "sources": [
    {
      "source": "docker/guides/getting-started.md",
      "content": "...",
      "distance": 0.32
    }
  ]
}
```

Interactive API docs available at: `http://localhost:8000/docs` (Swagger UI)

### Retrieval Stage Comparison

To see how each retrieval stage performs on a query:

```bash
python scripts/test_retrieval.py
```

This shows all 4 stages side by side: vector search, BM25, RRF fusion, and cross-encoder re-ranking — useful for understanding and debugging retrieval quality.

---

## Cost

| Component | Cost |
|-----------|------|
| Embeddings (one-time) | ~$0.12 |
| LLM generation | ~$0.008 per query |
| Re-ranker | Free (runs locally) |
| BM25 search | Free (runs locally) |

Estimated total project cost: $2-5

---

## License

MIT
