"""Shared ChromaDB utilities used by both ingest and retriever.

Centralises the ChromaDB client, collection names, and embedding
functions so they are defined once and reused everywhere.
"""

import os
from pathlib import Path

import chromadb
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHROMA_DIR = PROJECT_ROOT / "chroma_data"
CORPUS_DIR = PROJECT_ROOT / "docs" / "corpus"

# Collection names — one per embedding model
COLLECTION_OPENAI = "docs_openai"
COLLECTION_MINILM = "docs_minilm"

# Default active collection (switchable via env var)
ACTIVE_COLLECTION = os.getenv("ACTIVE_COLLECTION", COLLECTION_OPENAI)


def get_chroma_client() -> chromadb.ClientAPI:
    """Return a persistent ChromaDB client backed by disk."""
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def get_embedding_function(collection_name: str):
    """Return the embedding function for a given collection.

    Args:
        collection_name: Either 'docs_openai' or 'docs_minilm'.

    Returns:
        A ChromaDB-compatible embedding function.
    """
    if collection_name == COLLECTION_OPENAI:
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set. Add it to your .env file.")

        return OpenAIEmbeddingFunction(
            api_key=api_key,
            model_name="text-embedding-3-small",
        )

    if collection_name == COLLECTION_MINILM:
        from chromadb.utils.embedding_functions import (
            SentenceTransformerEmbeddingFunction,
        )

        return SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2",
        )

    raise ValueError(
        f"Unknown collection: {collection_name}. "
        f"Use '{COLLECTION_OPENAI}' or '{COLLECTION_MINILM}'."
    )


def get_collection(collection_name: str | None = None) -> chromadb.Collection:
    """Get a ChromaDB collection with its embedding function attached.

    Args:
        collection_name: Override the active collection. If None, uses
                         ACTIVE_COLLECTION from environment.

    Returns:
        A ChromaDB Collection ready for querying or upserting.
    """
    name = collection_name or ACTIVE_COLLECTION
    client = get_chroma_client()
    embed_fn = get_embedding_function(name)
    return client.get_or_create_collection(name=name, embedding_function=embed_fn)
