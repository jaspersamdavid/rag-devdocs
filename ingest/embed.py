"""Embed chunked documents into ChromaDB collections.

Supports two embedding models stored in separate collections:
  - docs_openai:  OpenAI text-embedding-3-small (production, paid)
  - docs_minilm:  all-MiniLM-L6-v2 (local, free)

Usage:
    python -m ingest.embed --model openai     # embed with OpenAI
    python -m ingest.embed --model minilm     # embed with MiniLM
    python -m ingest.embed --model openai --reset  # wipe collection first

The script is re-runnable: it skips chunks whose IDs already exist
in the collection, so running it twice won't create duplicates.
"""

import hashlib
import time

from langchain_core.documents import Document

from common.chroma import (
    COLLECTION_OPENAI,
    COLLECTION_MINILM,
    CORPUS_DIR,
    get_chroma_client,
    get_embedding_function,
)
from ingest.chunker import chunk_documents
from ingest.loader import load_directory

# Batch size for ChromaDB upserts (ChromaDB recommends ≤5000 per call)
BATCH_SIZE = 500


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_chunk_id(source: str, index: int) -> str:
    """Create a deterministic ID for a chunk.

    Uses a hash of the source path + chunk index so the same document
    always produces the same IDs. This is what makes the script
    re-runnable without duplicates.
    """
    raw = f"{source}::chunk_{index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Core embedding logic
# ---------------------------------------------------------------------------


def load_and_chunk_corpus() -> list[Document]:
    """Load all docs from the corpus directory and chunk them."""
    print(f"Loading documents from {CORPUS_DIR} ...")
    documents = load_directory(CORPUS_DIR)
    print(f"  Loaded {len(documents)} raw documents")

    print("Chunking documents ...")
    chunks = chunk_documents(documents)
    print(f"  Created {len(chunks)} chunks")

    return chunks


def embed_chunks(
    chunks: list[Document],
    model: str,
    reset: bool = False,
) -> None:
    """Embed chunks into the appropriate ChromaDB collection.

    Args:
        chunks: List of chunked Documents to embed.
        model: Which model to use — "openai" or "minilm".
        reset: If True, delete the collection before embedding.
    """
    client = get_chroma_client()

    # Pick collection name and embedding function based on model choice
    if model == "openai":
        collection_name = COLLECTION_OPENAI
    elif model == "minilm":
        collection_name = COLLECTION_MINILM
    else:
        raise ValueError(f"Unknown model: {model}. Use 'openai' or 'minilm'.")

    embed_fn = get_embedding_function(collection_name)

    # Reset collection if requested
    if reset:
        print(f"Resetting collection '{collection_name}' ...")
        try:
            client.delete_collection(collection_name)
        except ValueError:
            pass  # Collection didn't exist yet

    # Get or create the collection with the embedding function
    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=embed_fn,
    )

    existing_count = collection.count()
    print(f"Collection '{collection_name}': {existing_count} existing chunks")

    # Build lists of IDs, documents, and metadata for upsert
    ids: list[str] = []
    documents_text: list[str] = []
    metadatas: list[dict] = []

    for i, chunk in enumerate(chunks):
        chunk_id = make_chunk_id(chunk.metadata.get("source", "unknown"), i)
        ids.append(chunk_id)
        documents_text.append(chunk.page_content)
        metadatas.append(chunk.metadata)

    # Filter out chunks that already exist (skip if reset)
    if not reset and existing_count > 0:
        print("Checking for existing chunks to skip ...")
        existing_ids = set()
        # Check in batches (ChromaDB .get() has limits)
        for batch_start in range(0, len(ids), BATCH_SIZE):
            batch_ids = ids[batch_start : batch_start + BATCH_SIZE]
            result = collection.get(ids=batch_ids)
            existing_ids.update(result["ids"])

        new_indices = [i for i, cid in enumerate(ids) if cid not in existing_ids]
        if len(new_indices) == 0:
            print("All chunks already exist. Nothing to embed.")
            return

        ids = [ids[i] for i in new_indices]
        documents_text = [documents_text[i] for i in new_indices]
        metadatas = [metadatas[i] for i in new_indices]
        print(f"  Skipping {existing_count} existing, embedding {len(ids)} new chunks")

    # Upsert in batches
    total = len(ids)
    print(f"Embedding {total} chunks with '{model}' ...")
    start_time = time.time()

    for batch_start in range(0, total, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total)
        batch_num = (batch_start // BATCH_SIZE) + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

        collection.upsert(
            ids=ids[batch_start:batch_end],
            documents=documents_text[batch_start:batch_end],
            metadatas=metadatas[batch_start:batch_end],
        )

        elapsed = time.time() - start_time
        print(
            f"  Batch {batch_num}/{total_batches} "
            f"({batch_end}/{total} chunks, {elapsed:.1f}s elapsed)"
        )

    elapsed = time.time() - start_time
    final_count = collection.count()
    print(
        f"\nDone! Collection '{collection_name}' now has {final_count} chunks. "
        f"Took {elapsed:.1f}s."
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Parse arguments and run the embedding pipeline."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Embed document chunks into ChromaDB."
    )
    parser.add_argument(
        "--model",
        choices=["openai", "minilm"],
        default="openai",
        help="Embedding model to use (default: openai)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing collection before embedding",
    )
    args = parser.parse_args()

    chunks = load_and_chunk_corpus()
    embed_chunks(chunks, model=args.model, reset=args.reset)


if __name__ == "__main__":
    main()
