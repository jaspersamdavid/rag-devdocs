"""Document loaders for PDF, Markdown, and web-based documentation.

Each loader returns a list of LangChain Document objects with metadata
including `source` (file path or URL) and `page` (when available).
"""

from pathlib import Path

from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    WebBaseLoader,
)
from langchain_core.documents import Document


def load_pdf(path: Path) -> list[Document]:
    """Load a PDF file, returning one Document per page.

    Each document's metadata includes:
        - source: the file path
        - page: zero-indexed page number
    """
    loader = PyPDFLoader(str(path))
    docs = loader.load()
    for doc in docs:
        doc.metadata["source"] = str(path)
    return docs


def load_markdown(path: Path) -> list[Document]:
    """Load a Markdown file as a single Document.

    Uses TextLoader to read raw markdown content — this preserves
    headings and structure that the chunker uses as split points.

    Metadata includes:
        - source: the file path
    """
    loader = TextLoader(str(path), encoding="utf-8")
    docs = loader.load()
    for doc in docs:
        doc.metadata["source"] = str(path)
    return docs


def load_web(url: str) -> list[Document]:
    """Load a web page as a single Document.

    Metadata includes:
        - source: the URL
    """
    loader = WebBaseLoader(url)
    docs = loader.load()
    for doc in docs:
        doc.metadata["source"] = url
    return docs


def load_document(path_or_url: str) -> list[Document]:
    """Auto-detect the source type and load accordingly.

    - .pdf  → PyPDFLoader  (one Document per page)
    - .md / .mdx / .adoc → TextLoader (one Document, raw text preserved)
    - http*              → WebBaseLoader (one Document)

    Raises ValueError for unsupported file types.
    """
    if path_or_url.startswith(("http://", "https://")):
        return load_web(path_or_url)

    path = Path(path_or_url)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return load_pdf(path)
    if suffix in {".md", ".mdx", ".adoc"}:
        return load_markdown(path)

    raise ValueError(
        f"Unsupported file type '{suffix}' for {path}. "
        "Supported: .pdf, .md, .mdx, .adoc, or a URL."
    )


def load_directory(directory: Path, glob_pattern: str = "**/*") -> list[Document]:
    """Load all supported documents from a directory.

    Walks the directory with the given glob pattern and loads every
    .pdf and .md file it finds, skipping unsupported types.

    Returns a flat list of Documents from all files.
    """
    docs: list[Document] = []
    supported_suffixes = {".pdf", ".md", ".mdx", ".adoc"}

    for file_path in sorted(directory.glob(glob_pattern)):
        if file_path.is_file() and file_path.suffix.lower() in supported_suffixes:
            docs.extend(load_document(str(file_path)))

    return docs
