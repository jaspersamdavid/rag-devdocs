"""Vector similarity search against ChromaDB collections.

Queries the embedded document chunks and returns the most relevant
results for a given question. Supports switching between the OpenAI
and MiniLM collections via the ACTIVE_COLLECTION env var.

Usage:
    from retriever.vector_search import retrieve

    results = retrieve("How do I create a FastAPI endpoint?")
    for doc in results:
        print(doc.page_content[:100], doc.metadata["source"])
"""

from langchain_core.documents import Document

from common.chroma import get_collection

# Default number of results to return
DEFAULT_TOP_K = 5


def retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    collection_name: str | None = None,
) -> list[Document]:
    """Search for the most relevant document chunks for a query.

    Converts the query to a vector using the same embedding model
    that was used to embed the collection, then finds the closest
    chunks by cosine similarity.

    Args:
        query: The user's question or search string.
        top_k: Number of results to return (default: 5).
        collection_name: Override which collection to search.

    Returns:
        A list of LangChain Document objects, ordered by relevance
        (most relevant first). Each document has:
          - page_content: the chunk text
          - metadata: includes 'source', 'distance' (lower = more similar)
    """
    collection = get_collection(collection_name)

    results = collection.query(
        query_texts=[query],
        n_results=top_k,
    )

    # Convert ChromaDB results into LangChain Document objects
    documents: list[Document] = []

    for i in range(len(results["ids"][0])):
        metadata = results["metadatas"][0][i] if results["metadatas"] else {}
        # Add the similarity distance to metadata for transparency
        if results["distances"]:
            metadata["distance"] = results["distances"][0][i]

        doc = Document(
            page_content=results["documents"][0][i],
            metadata=metadata,
        )
        documents.append(doc)

    return documents


def retrieve_with_scores(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    collection_name: str | None = None,
) -> list[tuple[Document, float]]:
    """Same as retrieve(), but returns (Document, distance) tuples.

    Useful when you need the similarity scores for re-ranking
    or confidence thresholds.

    Args:
        query: The user's question or search string.
        top_k: Number of results to return.
        collection_name: Override which collection to search.

    Returns:
        List of (Document, distance) tuples. Lower distance = more similar.
    """
    collection = get_collection(collection_name)

    results = collection.query(
        query_texts=[query],
        n_results=top_k,
    )

    doc_score_pairs: list[tuple[Document, float]] = []

    for i in range(len(results["ids"][0])):
        metadata = results["metadatas"][0][i] if results["metadatas"] else {}
        distance = results["distances"][0][i] if results["distances"] else 0.0

        doc = Document(
            page_content=results["documents"][0][i],
            metadata=metadata,
        )
        doc_score_pairs.append((doc, distance))

    return doc_score_pairs
