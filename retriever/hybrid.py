"""Hybrid retrieval: combines vector search + BM25 keyword search.

Runs both search methods in parallel, merges their results using
Reciprocal Rank Fusion (RRF), then re-ranks the top candidates
with a cross-encoder for maximum precision.

This is the main entry point for retrieval in Phase 2+.

Usage:
    from retriever.hybrid import hybrid_retrieve

    # Full pipeline: vector + BM25 → RRF → re-rank → top 5
    results = hybrid_retrieve("How do I create a FastAPI endpoint?")

    # Without re-ranking (for testing RRF alone)
    results = hybrid_retrieve("FastAPI endpoint", use_reranker=False)
"""

from langchain_core.documents import Document

from retriever.bm25_search import retrieve_bm25
from retriever.reranker import rerank
from retriever.vector_search import retrieve as retrieve_vector

# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion (RRF)
# ---------------------------------------------------------------------------

# RRF constant — controls how much weight is given to rank position.
# Standard value from the original RRF paper (Cormack et al., 2009).
RRF_K = 60


def reciprocal_rank_fusion(
    ranked_lists: list[list[Document]],
    k: int = RRF_K,
) -> list[Document]:
    """Merge multiple ranked lists into one using Reciprocal Rank Fusion.

    RRF scores each document based on its rank in each list:
        score = sum( 1 / (k + rank) )  for each list the doc appears in

    A document that appears at rank 1 in both lists gets a higher score
    than one that appears at rank 1 in only one list. This is how we
    combine the strengths of vector search (semantic) and BM25 (keyword).

    Args:
        ranked_lists: A list of ranked document lists (e.g., [vector_results, bm25_results]).
        k: RRF smoothing constant (default: 60).

    Returns:
        A single merged list of Documents, ordered by fused RRF score (highest first).
        Each document's metadata includes an 'rrf_score' field.
    """
    # Use page_content as the dedup key (same text = same chunk)
    doc_scores: dict[str, float] = {}
    doc_map: dict[str, Document] = {}

    for ranked_list in ranked_lists:
        for rank, doc in enumerate(ranked_list, start=1):
            key = doc.page_content
            doc_scores[key] = doc_scores.get(key, 0.0) + 1.0 / (k + rank)
            # Keep the doc with the most metadata
            if key not in doc_map:
                doc_map[key] = doc

    # Sort by fused score descending
    sorted_keys = sorted(doc_scores.keys(), key=lambda x: doc_scores[x], reverse=True)

    results: list[Document] = []
    for key in sorted_keys:
        doc = doc_map[key]
        enriched_metadata = {**doc.metadata, "rrf_score": doc_scores[key]}
        results.append(
            Document(page_content=doc.page_content, metadata=enriched_metadata)
        )

    return results


# ---------------------------------------------------------------------------
# Main hybrid retrieval function
# ---------------------------------------------------------------------------


def hybrid_retrieve(
    query: str,
    vector_top_k: int = 20,
    bm25_top_k: int = 20,
    final_top_k: int = 5,
    use_reranker: bool = True,
) -> list[Document]:
    """Full hybrid retrieval pipeline: vector + BM25 → RRF → re-rank.

    Steps:
        1. Run vector search (semantic) → top vector_top_k results
        2. Run BM25 search (keyword) → top bm25_top_k results
        3. Merge both lists with Reciprocal Rank Fusion (RRF)
        4. (Optional) Re-rank the merged top-20 with cross-encoder
        5. Return the top final_top_k results

    Args:
        query: The user's question.
        vector_top_k: How many results to fetch from vector search (default: 20).
        bm25_top_k: How many results to fetch from BM25 (default: 20).
        final_top_k: How many final results to return (default: 5).
        use_reranker: Whether to apply cross-encoder re-ranking (default: True).

    Returns:
        Top-k Document objects after hybrid fusion and optional re-ranking.
    """
    # Step 1 & 2: Run both search methods
    vector_results = retrieve_vector(query, top_k=vector_top_k)
    bm25_results = retrieve_bm25(query, top_k=bm25_top_k)

    # Step 3: Merge with RRF
    fused_results = reciprocal_rank_fusion([vector_results, bm25_results])

    # Step 4: Re-rank (optional) — take top 20 from RRF, re-rank to top final_top_k
    if use_reranker:
        candidates = fused_results[:20]
        return rerank(query, candidates, top_k=final_top_k)

    # Without re-ranking, just return top final_top_k from RRF
    return fused_results[:final_top_k]
