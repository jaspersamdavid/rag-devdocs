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
import re
import time
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from langchain_core.documents import Document
from openai import OpenAI

from common.chroma import CORPUS_DIR
from common.logging import get_logger

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

log = get_logger("api.generate")


# ---------------------------------------------------------------------------
# Citation enforcement
# ---------------------------------------------------------------------------

# Regex pattern that matches [Source: anything_here]
CITATION_PATTERN = re.compile(r"\[Source:\s*[^\]]+\]")


def _extract_citations(answer: str) -> list[str]:
    """Find all citation markers in the LLM's answer.

    Scans the answer text for patterns like [Source: fastapi/index.md]
    and returns them as a list.

    Args:
        answer: The raw answer string from the LLM.

    Returns:
        A list of citation strings found (e.g., ["[Source: fastapi/index.md]"]).
        Empty list if no citations found.
    """
    return CITATION_PATTERN.findall(answer)


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
    trace: Any | None = None,
) -> str:
    """Generate a cited answer from retrieved documentation chunks.

    Args:
        question: The user's question.
        chunks: Retrieved LangChain Document objects with metadata.
        model: Override the LLM model name (default: gpt-4o).
        trace: Optional Langfuse trace/span to attach a generation to.

    Returns:
        The LLM's answer string with [Source: ...] citations.
    """
    if not chunks:
        log.warning("generate_no_chunks", question=question)
        return PROMPTS["fallback"].strip()

    used_model = model or DEFAULT_MODEL
    log.info("generate_start", question=question, model=used_model, chunk_count=len(chunks))

    context = _build_context(chunks)
    user_message = PROMPTS["user_template"].format(
        context=context, question=question
    )

    messages = [
        {"role": "system", "content": PROMPTS["system"].strip()},
        {"role": "user", "content": user_message},
    ]

    # Start Langfuse generation span BEFORE the LLM call so timing is accurate
    gen_span = None
    if trace:
        gen_span = trace.start_observation(
            name="llm_generation",
            as_type="generation",
            model=used_model,
            input=messages,
        )

    client = OpenAI()
    t0 = time.perf_counter()
    response = client.chat.completions.create(
        model=used_model,
        messages=messages,
        temperature=0.2,
    )
    llm_ms = (time.perf_counter() - t0) * 1000

    raw_answer = response.choices[0].message.content or PROMPTS["fallback"].strip()

    # Extract token usage from the OpenAI response
    usage = response.usage
    log.info(
        "llm_response",
        model=used_model,
        duration_ms=round(llm_ms, 1),
        prompt_tokens=usage.prompt_tokens if usage else None,
        completion_tokens=usage.completion_tokens if usage else None,
        total_tokens=usage.total_tokens if usage else None,
    )

    # Close the Langfuse generation span with output and token usage
    if gen_span:
        gen_span.update(
            output=raw_answer,
            usage_details={
                "input": usage.prompt_tokens if usage else 0,
                "output": usage.completion_tokens if usage else 0,
            },
            metadata={"duration_ms": round(llm_ms, 1), "temperature": 0.2},
        )
        gen_span.end()

    # Enforce citations — reject uncited answers
    citations = _extract_citations(raw_answer)
    if citations:
        log.info("citations_found", count=len(citations), citations=citations)
        return raw_answer

    log.warning("citations_missing", question=question, answer_preview=raw_answer[:200])
    return PROMPTS["fallback"].strip()
