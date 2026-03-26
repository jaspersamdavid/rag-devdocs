"""LLM generation with citation-enforced prompting.

Takes retrieved document chunks and a user query, formats them into
a citation-aware prompt, and returns an answer grounded in the sources.

Usage:
    from retriever.vector_search import retrieve
    from api.generate import generate

    chunks = retrieve("How do I define a FastAPI route?")
    answer = generate("How do I define a FastAPI route?", chunks)
    print(answer)
"""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from langchain_core.documents import Document
from openai import OpenAI

from common.chroma import CORPUS_DIR

load_dotenv()

# ---------------------------------------------------------------------------
# Load prompt config
# ---------------------------------------------------------------------------

PROMPTS_PATH = Path(__file__).resolve().parent.parent / "prompts" / "v1.yaml"

with open(PROMPTS_PATH) as f:
    PROMPTS = yaml.safe_load(f)

# ---------------------------------------------------------------------------
# LLM config
# ---------------------------------------------------------------------------

DEFAULT_MODEL = os.getenv("LLM_MODEL", "gpt-4o")


def _build_context(chunks: list[Document]) -> str:
    """Format retrieved chunks into numbered context blocks."""
    template = PROMPTS["context_template"]
    parts: list[str] = []
    for i, chunk in enumerate(chunks, start=1):
        raw_source = chunk.metadata.get("source", "unknown")
        # Strip the local corpus path prefix for cleaner citations
        try:
            source = str(Path(raw_source).relative_to(CORPUS_DIR))
        except ValueError:
            source = raw_source
        parts.append(
            template.format(index=i, source=source, content=chunk.page_content)
        )
    return "\n".join(parts)


def generate(
    question: str,
    chunks: list[Document],
    model: str | None = None,
) -> str:
    """Generate a cited answer from retrieved documentation chunks.

    Args:
        question: The user's question.
        chunks: Retrieved LangChain Document objects with metadata.
        model: Override the LLM model name (default: gpt-4o).

    Returns:
        The LLM's answer string with [Source: ...] citations.
    """
    if not chunks:
        return PROMPTS["fallback"].strip()

    context = _build_context(chunks)
    user_message = PROMPTS["user_template"].format(
        context=context, question=question
    )

    client = OpenAI()
    response = client.chat.completions.create(
        model=model or DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": PROMPTS["system"].strip()},
            {"role": "user", "content": user_message},
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content or PROMPTS["fallback"].strip()
