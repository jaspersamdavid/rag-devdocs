"""FastAPI application with /ask endpoint for the RAG DevDocs system.

Run:
    uvicorn api.main:app --reload

Then POST a question:
    curl -X POST http://localhost:8000/ask \
         -H "Content-Type: application/json" \
         -d '{"question": "How do I create a FastAPI endpoint?"}'
"""

import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api.generate import generate
from common.langfuse_client import get_langfuse_client
from common.logging import configure_logging, get_logger
from retriever.hybrid import hybrid_retrieve

# Initialise structured logging on app startup
configure_logging()
log = get_logger("api.main")

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="RAG DevDocs",
    description="Ask questions about developer documentation and get cited answers.",
    version="0.1.0",
)

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class AskRequest(BaseModel):
    """The JSON body for a question."""

    question: str


class SourceChunk(BaseModel):
    """A single retrieved source chunk returned alongside the answer."""

    source: str
    content: str
    distance: float | None = None


class AskResponse(BaseModel):
    """The JSON response containing the answer and its sources."""

    answer: str
    sources: list[SourceChunk]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    """Accept a question, retrieve relevant docs, and return a cited answer."""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    log.info("request_received", question=request.question)
    t0 = time.perf_counter()

    # Create a Langfuse trace for this request (v4 API)
    langfuse = get_langfuse_client()
    trace = langfuse.start_observation(
        name="rag-query",
        as_type="span",
        input={"question": request.question},
    )

    chunks = hybrid_retrieve(request.question, trace=trace)
    answer = generate(request.question, chunks, trace=trace)

    sources = [
        SourceChunk(
            source=chunk.metadata.get("source", "unknown"),
            content=chunk.page_content,
            distance=chunk.metadata.get("distance"),
        )
        for chunk in chunks
    ]

    total_ms = (time.perf_counter() - t0) * 1000
    trace.update(
        output={"answer": answer, "source_count": len(sources)},
        metadata={"total_duration_ms": round(total_ms, 1)},
    )
    trace.end()

    log.info(
        "request_complete",
        question=request.question,
        source_count=len(sources),
        answer_length=len(answer),
        total_duration_ms=round(total_ms, 1),
    )

    return AskResponse(answer=answer, sources=sources)


@app.get("/health")
def health() -> dict[str, str]:
    """Simple health check endpoint."""
    return {"status": "ok"}
