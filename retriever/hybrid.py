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

import time
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from common.chroma import CORPUS_DIR
from common.logging import get_logger
from retriever.bm25_search import retrieve_bm25
from retriever.reranker import rerank
from retriever.vector_search import retrieve as retrieve_vector

log = get_logger("retriever.hybrid")


def _clean(doc: Document) -> str:
    """Extract a short source path for logging (strips local corpus prefix)."""
    raw = doc.metadata.get("source", "unknown")
    try:
        return str(Path(raw).relative_to(CORPUS_DIR))
    except ValueError:
        return raw


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


def _docs_summary(docs: list[Document], limit: int = 5) -> list[dict[str, Any]]:
    """Build a compact summary of documents for Langfuse span output."""
    return [
        {"source": _clean(d), "preview": d.page_content[:80]}
        for d in docs[:limit]
    ]


def hybrid_retrieve(
    query: str,
    vector_top_k: int = 20,
    bm25_top_k: int = 20,
    final_top_k: int = 5,
    use_reranker: bool = True,
    trace: Any | None = None,
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
        trace: Optional Langfuse trace/span to attach child spans to.

    Returns:
        Top-k Document objects after hybrid fusion and optional re-ranking.
    """
    log.info("retrieval_start", query=query)

    # Step 1: Vector search (semantic)
    vs_span = trace.start_observation(name="vector_search", as_type="span", input={"query": query, "top_k": vector_top_k}) if trace else None
    t0 = time.perf_counter()
    vector_results = retrieve_vector(query, top_k=vector_top_k)
    vector_ms = (time.perf_counter() - t0) * 1000
    log.info(
        "vector_search_complete",
        count=len(vector_results),
        top_k=vector_top_k,
        duration_ms=round(vector_ms, 1),
        top_sources=[_clean(d) for d in vector_results[:3]],
    )
    if vs_span:
        vs_span.update(output={"count": len(vector_results), "results": _docs_summary(vector_results)}, metadata={"duration_ms": round(vector_ms, 1)})
        vs_span.end()

    # Step 2: BM25 keyword search
    bm25_span = trace.start_observation(name="bm25_search", as_type="span", input={"query": query, "top_k": bm25_top_k}) if trace else None
    t0 = time.perf_counter()
    bm25_results = retrieve_bm25(query, top_k=bm25_top_k)
    bm25_ms = (time.perf_counter() - t0) * 1000
    log.info(
        "bm25_search_complete",
        count=len(bm25_results),
        top_k=bm25_top_k,
        duration_ms=round(bm25_ms, 1),
        top_sources=[_clean(d) for d in bm25_results[:3]],
    )
    if bm25_span:
        bm25_span.update(output={"count": len(bm25_results), "results": _docs_summary(bm25_results)}, metadata={"duration_ms": round(bm25_ms, 1)})
        bm25_span.end()

    # Step 3: Merge with RRF
    rrf_span = trace.start_observation(name="rrf_fusion", as_type="span", input={"vector_count": len(vector_results), "bm25_count": len(bm25_results)}) if trace else None
    t0 = time.perf_counter()
    fused_results = reciprocal_rank_fusion([vector_results, bm25_results])
    rrf_ms = (time.perf_counter() - t0) * 1000
    log.info(
        "rrf_fusion_complete",
        unique_chunks=len(fused_results),
        duration_ms=round(rrf_ms, 1),
        top_sources=[_clean(d) for d in fused_results[:3]],
    )
    if rrf_span:
        rrf_span.update(output={"unique_chunks": len(fused_results), "results": _docs_summary(fused_results)}, metadata={"duration_ms": round(rrf_ms, 1)})
        rrf_span.end()

    # Step 4: Re-rank (optional) — take top 20 from RRF, re-rank to top final_top_k
    if use_reranker:
        candidates = fused_results[:20]
        rerank_span = trace.start_observation(name="cross_encoder_rerank", as_type="span", input={"query": query, "candidates_in": len(candidates)}) if trace else None
        t0 = time.perf_counter()
        reranked = rerank(query, candidates, top_k=final_top_k)
        rerank_ms = (time.perf_counter() - t0) * 1000
        log.info(
            "rerank_complete",
            candidates_in=len(candidates),
            results_out=len(reranked),
            duration_ms=round(rerank_ms, 1),
            top_sources=[_clean(d) for d in reranked],
        )
        if rerank_span:
            rerank_span.update(output={"results_out": len(reranked), "results": _docs_summary(reranked)}, metadata={"duration_ms": round(rerank_ms, 1)})
            rerank_span.end()
        total_ms = vector_ms + bm25_ms + rrf_ms + rerank_ms
        log.info("retrieval_complete", total_duration_ms=round(total_ms, 1))
        return reranked

    # Without re-ranking, just return top final_top_k from RRF
    final = fused_results[:final_top_k]
    total_ms = vector_ms + bm25_ms + rrf_ms
    log.info("retrieval_complete", total_duration_ms=round(total_ms, 1))
    return final
