"""Interactive CLI for the RAG DevDocs system.

Run:
    ragdevdocs

Or directly:
    python cli.py
"""

import time

from api.generate import generate
from common.langfuse_client import get_langfuse_client
from common.logging import configure_logging, get_logger
from retriever.hybrid import hybrid_retrieve

# Initialise structured logging on CLI startup
configure_logging()
log = get_logger("cli")


def main() -> None:
    """Run the interactive RAG Q&A loop."""
    print("RAG DevDocs — Ask questions about developer documentation")
    print("Type 'exit' or 'quit' to stop.\n")

    while True:
        try:
            question = input("devdoc> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not question:
            continue
        if question.lower() in ("exit", "quit"):
            print("Goodbye!")
            break

        log.info("cli_query", question=question)
        t0 = time.perf_counter()

        # Create a Langfuse trace for this CLI query (v4 API)
        langfuse = get_langfuse_client()
        trace = langfuse.start_observation(
            name="rag-query",
            as_type="span",
            input={"question": question},
        )

        chunks = hybrid_retrieve(question, trace=trace)
        answer = generate(question, chunks, trace=trace)

        total_ms = (time.perf_counter() - t0) * 1000
        trace.update(
            output={"answer": answer, "chunk_count": len(chunks)},
            metadata={"total_duration_ms": round(total_ms, 1)},
        )
        trace.end()

        log.info(
            "cli_query_complete",
            question=question,
            chunk_count=len(chunks),
            answer_length=len(answer),
            total_duration_ms=round(total_ms, 1),
        )

        print(f"\n{answer}\n")


if __name__ == "__main__":
    main()
