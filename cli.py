"""Interactive CLI for the RAG DevDocs system.

Run:
    ragdevdocs

Or directly:
    python cli.py
"""

from retriever.hybrid import hybrid_retrieve
from api.generate import generate


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

        chunks = hybrid_retrieve(question)
        answer = generate(question, chunks)
        print(f"\n{answer}\n")


if __name__ == "__main__":
    main()
