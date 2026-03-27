"""FastAPI application with /ask endpoint for the RAG DevDocs system.

Run:
    uvicorn api.main:app --reload

Then POST a question:
    curl -X POST http://localhost:8000/ask \
         -H "Content-Type: application/json" \
         -d '{"question": "How do I create a FastAPI endpoint?"}'
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from api.generate import generate
from retriever.vector_search import retrieve

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="RAG DevDocs",
    description="Ask questions about developer documentation and get cited answers.",
    version="0.1.0",
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

    chunks = retrieve(request.question)
    answer = generate(request.question, chunks)

    sources = [
        SourceChunk(
            source=chunk.metadata.get("source", "unknown"),
            content=chunk.page_content,
            distance=chunk.metadata.get("distance"),
        )
        for chunk in chunks
    ]

    return AskResponse(answer=answer, sources=sources)


@app.get("/health")
def health() -> dict[str, str]:
    """Simple health check endpoint."""
    return {"status": "ok"}
