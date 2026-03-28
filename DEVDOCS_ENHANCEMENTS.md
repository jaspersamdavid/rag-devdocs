# DevDocs Enhancements — Future Roadmap

Ideas and improvements identified during development. These are beyond the current project scope but represent meaningful next steps for turning this into a production-grade product.

---

## 1. Smarter Retrieval — Metadata Filtering & Intent Classification

**Problem discovered:** When asking broad questions like "what are all the embedding models available in chromadb", the system fails to find specific pages (e.g., Perplexity's embedding integration page) because common words like "embedding" and "models" appear across thousands of chunks in the 60k corpus. The relevant page gets buried at rank 50+ and never makes it into the top-20 candidate pool.

**Root cause:** Both vector search and BM25 search the entire 60,812-chunk corpus without filtering. Specific provider pages compete against thousands of chunks containing the same common terms.

**Proposed solutions:**

- **Metadata filtering:** Before searching, filter chunks by source project. If the query mentions "chromadb", only search the ~1,796 ChromaDB chunks instead of all 60,812. This dramatically reduces competition and surfaces niche pages.

- **Intent classification:** Add a lightweight classifier (could be rule-based or a small LLM call) that analyses the user's question before retrieval:
  - Detect which documentation source(s) the question targets (ChromaDB, FastAPI, Docker, etc.)
  - Detect query type: specific lookup ("how do I X") vs. broad enumeration ("list all X") vs. comparison ("X vs Y")
  - Route to the appropriate search strategy based on intent

- **Isolated collection search:** For "list all" type queries, search within a single source's collection rather than the merged corpus. This prevents cross-source noise (Docker "models" pages competing with ChromaDB "models" pages).

- **New retrieval algorithm considerations:**
  - Hierarchical search: first identify relevant source → then search within that source
  - Query expansion: for broad queries, generate sub-queries targeting specific aspects
  - Chunk-level metadata enrichment: tag each chunk with its section heading, doc category, and topic keywords during ingestion

---

## 2. Product Packaging — PyPI / npm Distribution

**Goal:** Package the RAG DevDocs system so anyone can install it with a single command, similar to how `claude` CLI works.

**Options:**

- **PyPI package (`pip install ragdevdocs`):**
  - Already have `pyproject.toml` with `ragdevdocs` console entry point
  - Need to bundle or externalize the vector store (ChromaDB data is ~500MB+)
  - Users would need their own OpenAI API key for embeddings and LLM generation
  - Could ship with pre-built MiniLM embeddings for a free-tier experience

- **npm wrapper (`npx ragdevdocs`):**
  - Thin Node.js wrapper that spawns the Python process underneath
  - Similar to how some CLI tools work cross-platform
  - Adds complexity — Python still required as a dependency

**Challenges to solve:**
- **API key management:** Users need their own OpenAI key. Options: prompt on first run, `.env` file, or environment variable
- **Vector store distribution:** Ship pre-embedded data or require users to run ingestion themselves
- **Backend hosting:** For a fully hosted version, need a server running FastAPI + ChromaDB (options: Supabase, Vercel serverless, Railway, Fly.io)
- **Corpus updates:** How to update documentation when upstream sources change — versioned releases or auto-sync

---

## 3. Domain Expansion — Healthcare, Education, Law

**Goal:** Extend beyond developer documentation to other domains that have a mix of structured and unstructured data.

**Proposed domains:**

- **Healthcare:**
  - Unstructured: clinical guidelines, research papers, drug information leaflets
  - Structured: drug interaction tables, dosage charts, ICD codes
  - Challenge: accuracy is critical — wrong medical information is dangerous. Need higher confidence thresholds and mandatory citations.

- **Education:**
  - Unstructured: textbooks, lecture notes, course descriptions
  - Structured: curriculum tables, grading rubrics, prerequisite chains, timetables
  - Challenge: answers need to be tailored to the student's level. A high school question needs a different answer than a graduate-level question.

- **Law:**
  - Unstructured: case law, legal opinions, regulatory guidance
  - Structured: statute tables, jurisdiction lookups, filing deadlines, fee schedules
  - Challenge: jurisdiction matters — the same question has different answers in different states/countries. Need location-aware retrieval.

**Technical requirements for mixed data:**

- **Table-aware chunking:** Current chunker splits on text boundaries. For structured data in tables, need to preserve row/column relationships. Options: convert tables to markdown tables before chunking, or use specialised table extractors.

- **Intent classification (expanded):** The classifier needs to determine not just which source to search, but whether the answer lives in structured data (table lookup) or unstructured data (text retrieval):
  - "What are the side effects of ibuprofen?" → unstructured text retrieval
  - "What is the maximum daily dosage of ibuprofen?" → structured table lookup
  - "Compare ibuprofen and acetaminophen" → both structured + unstructured

- **Hybrid data store:** Structured data may be better served by a traditional database (SQL) rather than vector search. Could use a routing layer that sends structured queries to SQL and unstructured queries to the RAG pipeline, then merges results.

---

## 4. Agentic Features — Actions Beyond Q&A

**Goal:** Move from a read-only Q&A system to an agent that can take actions on the user's behalf.

**Proposed capabilities:**

- **Update structured data:**
  - User: "Update the dosage for ibuprofen in the drug table to 400mg"
  - Agent: Validates the request → updates the database table → confirms the change
  - Requires: write access to the data store, validation logic, audit trail

- **Send notifications / emails:**
  - User: "Email the compliance team about the updated drug interaction for warfarin"
  - Agent: Retrieves the relevant information → drafts an email → sends via SMTP/API on user confirmation
  - Requires: email integration (SendGrid, AWS SES), confirmation step before sending

- **Generate reports:**
  - User: "Generate a summary of all FastAPI security best practices"
  - Agent: Retrieves all relevant chunks → synthesizes into a structured report → exports as PDF/markdown
  - Requires: report template system, PDF generation

- **Cross-system actions:**
  - Create Jira tickets from documentation gaps identified during Q&A
  - Update a knowledge base when new information is discovered
  - Trigger CI/CD pipelines when configuration docs change

**Architecture for agentic features:**

- **Tool/function calling:** Use LLM function calling (OpenAI tools / Claude tool use) to let the model decide when to invoke actions
- **Confirmation step:** All write operations must require explicit user confirmation before execution — never auto-execute destructive actions
- **Audit logging:** Every action taken must be logged with who, what, when, and why
- **Permission model:** Role-based access — not every user should be able to update tables or send emails
