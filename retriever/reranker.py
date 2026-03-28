"""Cross-encoder re-ranker for improving retrieval precision.

Takes a list of candidate chunks and re-scores them using a
cross-encoder model (ms-marco-MiniLM-L-6-v2). Unlike embedding
models which encode query and document separately, a cross-encoder
looks at the query AND document together — making it much more
accurate at judging relevance, but slower (which is why we only
run it on a small candidate set, not the entire corpus).

Usage:
    from retriever.reranker import rerank

    top_chunks = rerank("How do I create a FastAPI endpoint?", candidates, top_k=5)
"""

from langchain_core.documents import Document
from sentence_transformers import CrossEncoder

# ---------------------------------------------------------------------------
# Model setup — loaded once, reused across calls
# ---------------------------------------------------------------------------

RERANKER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

_model: CrossEncoder | None = None


def _get_model() -> CrossEncoder:
    """Load the cross-encoder model (lazy, loads once on first call)."""
    global _model
    if _model is None:
        _model = CrossEncoder(RERANKER_MODEL_NAME)
    return _model


def rerank(
    query: str,
    documents: list[Document],
    top_k: int = 5,
) -> list[Document]:
    """Re-rank documents using a cross-encoder and return the top-k.

    The cross-encoder takes each (query, chunk_text) pair and produces
    a relevance score. This is more accurate than cosine similarity
    because it sees both texts together, allowing it to understand
    the relationship between query and document.

    Args:
        query: The user's question.
        documents: Candidate chunks to re-rank (typically 20 from hybrid search).
        top_k: Number of top results to keep after re-ranking (default: 5).

    Returns:
        The top-k most relevant Document objects, ordered by cross-encoder
        score (highest first). Each document's metadata includes a
        'rerank_score' field.
    """
    if not documents:
        return []

    model = _get_model()

    # Build pairs of (query, document_text) for the cross-encoder
    pairs = [[query, doc.page_content] for doc in documents]

    # Score all pairs — returns an array of relevance scores
    scores = model.predict(pairs)

    # Pair each document with its score, sort by score descending
    scored_docs = list(zip(documents, scores))
    scored_docs.sort(key=lambda x: x[1], reverse=True)

    # Take top-k and attach the rerank score to metadata
    results: list[Document] = []
    for doc, score in scored_docs[:top_k]:
        enriched_metadata = {**doc.metadata, "rerank_score": float(score)}
        results.append(
            Document(page_content=doc.page_content, metadata=enriched_metadata)
        )

    return results
