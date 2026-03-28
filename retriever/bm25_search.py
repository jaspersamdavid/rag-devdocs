"""BM25 keyword search over the document corpus.

Uses the rank_bm25 library to perform keyword-based retrieval.
Unlike vector search (which understands meaning), BM25 finds documents
that share the exact words/terms with the query. This is great for
matching specific function names, error messages, or technical terms.

Usage:
    from retriever.bm25_search import retrieve_bm25

    results = retrieve_bm25("PerplexityEmbeddingFunction")
    for doc in results:
        print(doc.page_content[:100], doc.metadata["source"])
"""

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from common.chroma import get_collection

# ---------------------------------------------------------------------------
# Module-level cache: we load chunks once and reuse them
# ---------------------------------------------------------------------------

_bm25_index: BM25Okapi | None = None
_corpus_docs: list[Document] = []


def _build_index() -> None:
    """Load all chunks from ChromaDB and build the BM25 index.

    This runs once on first call, then caches the index in memory.
    The BM25 index tokenises every chunk into words so it can later
    score queries by keyword overlap.
    """
    global _bm25_index, _corpus_docs

    collection = get_collection()

    # Pull ALL documents from ChromaDB in batches
    # (SQLite has a limit on SQL variables, so we can't fetch 60k at once)
    BATCH_SIZE = 5000
    total = collection.count()

    documents: list[Document] = []
    tokenised_corpus: list[list[str]] = []

    for offset in range(0, total, BATCH_SIZE):
        batch = collection.get(
            include=["documents", "metadatas"],
            limit=BATCH_SIZE,
            offset=offset,
        )

        for i in range(len(batch["ids"])):
            text = batch["documents"][i]
            metadata = batch["metadatas"][i] if batch["metadatas"] else {}

            documents.append(Document(page_content=text, metadata=metadata))

            # Tokenise: lowercase and split on whitespace
            # BM25 works on word tokens, not embeddings
            tokens = text.lower().split()
            tokenised_corpus.append(tokens)

    _corpus_docs = documents
    _bm25_index = BM25Okapi(tokenised_corpus)


def retrieve_bm25(
    query: str,
    top_k: int = 20,
) -> list[Document]:
    """Search for document chunks using BM25 keyword matching.

    Tokenises the query into words, then scores every chunk in the
    corpus by how well its words overlap with the query words.
    Returns the top-k highest-scoring chunks.

    Args:
        query: The user's question or search string.
        top_k: Number of results to return (default: 20).

    Returns:
        A list of Document objects ordered by BM25 score (best first).
        Each document's metadata includes a 'bm25_score' field.
    """
    # Build index on first call (lazy initialisation)
    if _bm25_index is None:
        _build_index()

    # Tokenise the query the same way we tokenised the corpus
    query_tokens = query.lower().split()

    # Score every document against the query
    scores = _bm25_index.get_scores(query_tokens)

    # Get the indices of the top-k highest scores
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

    results: list[Document] = []
    for idx in top_indices:
        doc = _corpus_docs[idx]
        # Attach the BM25 score to metadata so we can inspect it
        enriched_metadata = {**doc.metadata, "bm25_score": float(scores[idx])}
        results.append(
            Document(page_content=doc.page_content, metadata=enriched_metadata)
        )

    return results
