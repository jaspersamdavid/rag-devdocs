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

## 3. Expanded Tech Stack with Role-Based Routing

**Goal:** Before expanding to other domains, first widen the developer documentation corpus with more technology stacks and introduce role-based intent classification to route queries intelligently.

**Additional tech stacks to ingest:**

| Category | Technologies |
|----------|-------------|
| Frontend | React (existing), Angular, Vue, Next.js, Tailwind CSS |
| Backend | FastAPI (existing), Django, Express, Spring Boot, Node.js |
| Database | PostgreSQL, MongoDB, Redis, MySQL, SQLite |
| Data Warehousing | Snowflake, BigQuery, Redshift, dbt |
| Data & Analytics | Pandas, Apache Spark, Airflow, Jupyter |
| DevOps | Docker (existing), Kubernetes (existing), Terraform (existing), AWS, GCP |

**Role-based intent classification:**

The key insight is that the same topic (e.g., "database") is relevant to multiple roles but in different ways. A user asking "how to use a database" could be a backend developer, a data analyst, or a database administrator — and each needs different documentation.

**Defined roles and their knowledge boundaries:**

| Role | Primary Scope | Includes | Does NOT Include |
|------|--------------|----------|-----------------|
| **Frontend** | UI, components, styling, client-side state | React, Angular, Vue, CSS, frontend testing, API integration to backend | Backend logic, database queries, infrastructure |
| **Backend** | Server logic, APIs, authentication | FastAPI, Django, Express, database integration, API design, backend-to-frontend integration | Frontend components, data warehousing, analytics |
| **Database** | Schema design, queries, optimization | PostgreSQL, MongoDB, Redis, migrations, indexing, integration to backend and warehousing | Frontend, application logic, CI/CD |
| **Data Warehousing** | ETL, data pipelines, storage | Snowflake, BigQuery, dbt, Airflow, database integration | Frontend, backend APIs, deployment |
| **Data Analyst** | Querying, visualization, reporting | SQL, Pandas, Jupyter, BI tools, warehouse querying | Frontend, backend code, infrastructure |
| **DevOps** | Deployment, CI/CD, infrastructure | Docker, Kubernetes, Terraform, AWS, monitoring | Frontend components, business logic, data analysis |

**How routing works:**

```
User: "how do I connect to a PostgreSQL database?"
                    |
                    v
         Intent Classifier
         (lightweight LLM call or rule-based)
                    |
        +-----------+-----------+
        |                       |
  Role: Backend            Role: Database
  Scope: database          Scope: schema,
  integration,             queries, optimization,
  ORM usage,               connection config,
  connection pooling       permissions
        |                       |
        v                       v
  Search backend +          Search database
  database docs             docs only
  (FastAPI + PostgreSQL)    (PostgreSQL deep dive)
```

**Key principle:** Each role has **overlapping but distinct** boundaries. "Database" appears in Backend, Database, Data Warehousing, and Data Analyst roles — but each role surfaces different aspects:
- Backend developer asking about databases → connection pooling, ORM setup, query execution from application code
- Database admin asking about databases → schema design, indexing, performance tuning, backup/restore
- Data analyst asking about databases → writing SELECT queries, joins, aggregations, exporting data

**Multi-role queries:**

The classifier doesn't always need to pick just one role. Many real-world questions span multiple roles:

- "How do I connect my React frontend to my FastAPI backend?" → **Frontend + Backend**
- "How do I set up a PostgreSQL database and deploy it with Docker?" → **Database + DevOps**
- "How do I query Snowflake data and display it in a React dashboard?" → **Data Warehousing + Data Analyst + Frontend**

For these queries, the system should:
1. Detect all relevant roles from the question
2. Search across documentation tagged with any of the detected roles
3. Use RRF to merge results from each role's document pool — chunks that appear across multiple role pools get boosted, naturally surfacing integration-focused documentation
4. The re-ranker then picks the top chunks that best answer the cross-role question

This means the role classifier outputs a **list of roles with confidence scores**, not a single role. Any role above a confidence threshold gets included in the search.

**Implementation plan:**
1. Tag each documentation source with applicable roles during ingestion
2. Build a role classifier that detects the most likely role(s) from the question (supports multi-role output)
3. Filter the search corpus to only docs tagged with the detected role(s)
4. For multi-role queries, search each role's pool separately and merge with RRF for cross-role boosting
5. Fall back to full corpus search if role detection confidence is low

---

## 4. Domain Expansion — Healthcare, Education, Law

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

## 5. Frontend Chatbot Interface — Web & Mobile

**Goal:** Build a React-based chatbot UI that connects to the FastAPI `/ask` endpoint, making RAG DevDocs accessible as a web application and mobile app — not just a CLI tool.

**Web application (React):**

- **Chat interface:** Conversational UI with message bubbles, typing indicator, and citation highlighting
- **Document upload:** Users can upload their own documentation (PDF, Markdown, text files) which gets ingested into the pipeline in real-time
- **Source preview panel:** When a user clicks a `[Source: ...]` citation, show the full chunk in a side panel with the relevant section highlighted
- **Conversation history:** Maintain chat history per session so users can refer back to previous answers
- **Role selector:** Dropdown to select role context (Frontend, Backend, Database, etc.) to improve retrieval routing

**Tech stack for frontend:**
- React (with TypeScript) for the web UI
- Tailwind CSS for styling
- WebSocket or SSE for streaming LLM responses (instead of waiting for full answer)
- React Native or Expo for mobile app (shared component logic with web)

**Mobile application:**
- Cross-platform using React Native — same chatbot interface optimized for mobile
- Camera-based document upload: take a photo of printed documentation, OCR it, ingest it
- Push notifications for long-running ingestion jobs
- Offline mode: cache recent answers locally for reference without internet

**Document upload flow:**
```
User uploads PDF/MD file
        |
        v
  Backend receives file
        |
        v
  loader.py parses it → chunker.py splits it → embed.py embeds it
        |
        v
  Chunks added to ChromaDB with user-specific metadata
        |
        v
  User can now ask questions about their uploaded document
```

**Deployment:**
- Web app hosted on Vercel (static React build)
- Backend API on Railway / Fly.io / AWS Lambda
- ChromaDB on a hosted solution (Chroma Cloud, Pinecone, or Supabase pgvector)

---

## 6. Agentic Features — Actions Beyond Q&A

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
