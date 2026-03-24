"""Chunking logic for splitting documents into retrieval-sized pieces.

Uses LangChain's RecursiveCharacterTextSplitter with settings tuned for
developer documentation: 700-char chunks with 100-char overlap.
"""

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Default chunk settings — can be overridden via environment or arguments
DEFAULT_CHUNK_SIZE = 700
DEFAULT_CHUNK_OVERLAP = 100


def get_splitter(
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> RecursiveCharacterTextSplitter:
    """Create a text splitter configured for developer docs.

    The RecursiveCharacterTextSplitter tries to split on these separators
    in order, keeping chunks semantically coherent:
        1. Double newline (paragraph break)
        2. Single newline
        3. Space
        4. Empty string (character-level, last resort)
    """
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""],
        length_function=len,
    )


def chunk_documents(
    documents: list[Document],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Document]:
    """Split a list of Documents into smaller chunks.

    Metadata from the original document (source, page, etc.) is
    preserved on every chunk automatically by LangChain's splitter.

    Args:
        documents: List of Documents to split.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Characters of overlap between consecutive chunks.

    Returns:
        A flat list of chunked Documents with original metadata intact.
    """
    splitter = get_splitter(chunk_size, chunk_overlap)
    return splitter.split_documents(documents)
