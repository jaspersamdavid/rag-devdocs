"""Test script to compare retrieval methods side-by-side.

Run:
    python scripts/test_retrieval.py

This lets you see the results from each stage independently:
  1. Vector search only (what you had before)
  2. BM25 keyword search only (new)
  3. RRF hybrid fusion (vector + BM25 merged)
  4. Re-ranked hybrid (cross-encoder on top)
"""

from pathlib import Path

from common.chroma import CORPUS_DIR
from retriever.bm25_search import retrieve_bm25
from retriever.hybrid import hybrid_retrieve, reciprocal_rank_fusion
from retriever.reranker import rerank
from retriever.vector_search import retrieve as retrieve_vector


def _clean_source(source: str) -> str:
    """Strip the corpus directory prefix from source paths."""
    try:
        return str(Path(source).relative_to(CORPUS_DIR))
    except ValueError:
        return source


def _print_results(title: str, docs: list, max_display: int = 5) -> None:
    """Pretty-print a list of retrieval results."""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")

    for i, doc in enumerate(docs[:max_display], start=1):
        source = _clean_source(doc.metadata.get("source", "unknown"))
        content_preview = doc.page_content[:120].replace("\n", " ")

        # Show whatever scores are available
        scores = []
        if "distance" in doc.metadata:
            scores.append(f"distance={doc.metadata['distance']:.4f}")
        if "bm25_score" in doc.metadata:
            scores.append(f"bm25={doc.metadata['bm25_score']:.4f}")
        if "rrf_score" in doc.metadata:
            scores.append(f"rrf={doc.metadata['rrf_score']:.6f}")
        if "rerank_score" in doc.metadata:
            scores.append(f"rerank={doc.metadata['rerank_score']:.4f}")

        score_str = " | ".join(scores) if scores else "no score"

        print(f"\n  #{i} [{source}]  ({score_str})")
        print(f"     {content_preview}...")


def main() -> None:
    """Run all four retrieval stages on a test query."""
    print("\n" + "~" * 70)
    query = input("  Enter your test query: ").strip()
    if not query:
        print("No query provided. Exiting.")
        return
    print("~" * 70)

    # --- Stage 1: Vector search only ---
    print("\n⏳ Running vector search...")
    vector_results = retrieve_vector(query, top_k=20)
    _print_results("STAGE 1: Vector Search (semantic similarity) — all 20", vector_results, max_display=20)

    # --- Stage 2: BM25 keyword search only ---
    print("\n⏳ Running BM25 keyword search...")
    bm25_results = retrieve_bm25(query, top_k=20)
    _print_results("STAGE 2: BM25 Keyword Search (exact word matching) — all 20", bm25_results, max_display=20)

    # --- Stage 3: RRF hybrid fusion (no re-ranking) ---
    print("\n⏳ Merging with Reciprocal Rank Fusion...")
    fused_results = reciprocal_rank_fusion([vector_results, bm25_results])
    _print_results("STAGE 3: RRF Hybrid Fusion (vector + BM25 merged) — top 20", fused_results, max_display=20)

    # --- Stage 4: Cross-encoder re-ranking ---
    print("\n⏳ Re-ranking with cross-encoder...")
    reranked_results = rerank(query, fused_results[:20], top_k=5)
    _print_results("STAGE 4: Cross-Encoder Re-ranked — final top 5", reranked_results, max_display=5)

    print(f"\n{'='*70}")
    print("  Done! These top 5 re-ranked chunks are what gets sent to the LLM.")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
