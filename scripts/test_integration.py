"""Phase 2 integration test — automated end-to-end pipeline validation.

Unlike test_retrieval.py (which is interactive and visual), this script
runs a set of predefined test queries through the FULL pipeline:
    hybrid retrieval → LLM generation → citation enforcement

Each test checks:
    1. Pipeline runs without crashing (no exceptions)
    2. Answer is not empty
    3. Answer contains at least one [Source: ...] citation
    4. Retrieved chunks are returned (not zero)

Run:
    python scripts/test_integration.py

Exit codes:
    0 = all tests passed
    1 = one or more tests failed
"""

import re
import sys
import time

# Configure structured logging before importing pipeline modules
from common.logging import configure_logging

configure_logging()

from api.generate import generate
from common.langfuse_client import get_langfuse_client
from retriever.hybrid import hybrid_retrieve

# ---------------------------------------------------------------------------
# Test cases — each is a (name, question) tuple
# ---------------------------------------------------------------------------

TEST_CASES = [
    (
        "fastapi_basic",
        "What is FastAPI and what are its main features?",
    ),
    (
        "docker_howto",
        "How do I create a Docker container?",
    ),
    (
        "kubernetes_concept",
        "What is a Kubernetes Pod?",
    ),
    (
        "pydantic_validation",
        "How does Pydantic validate data?",
    ),
    (
        "git_branching",
        "How do I create a new branch in Git?",
    ),
    (
        "chromadb_collections",
        "How do I create a collection in ChromaDB?",
    ),
    (
        "react_components",
        "What are React components?",
    ),
    (
        "off_topic",
        "How do I cook pasta?",
    ),
]

# Regex pattern for citation markers
CITATION_PATTERN = re.compile(r"\[Source:\s*[^\]]+\]")


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------


def run_test(name: str, question: str) -> tuple[bool, str]:
    """Run a single integration test.

    Args:
        name: Test case name (for display).
        question: The question to send through the pipeline.

    Returns:
        (passed: bool, detail: str) — whether the test passed and why.
    """
    try:
        t0 = time.perf_counter()

        # Create a Langfuse observation for this test query (v4 API)
        langfuse = get_langfuse_client()
        trace = langfuse.start_observation(
            name="integration-test",
            as_type="span",
            input={"question": question, "test_name": name},
        )

        # Step 1: Hybrid retrieval
        chunks = hybrid_retrieve(question, trace=trace)

        # Step 2: LLM generation with citation enforcement
        answer = generate(question, chunks, trace=trace)

        duration_ms = (time.perf_counter() - t0) * 1000

        # --- Checks ---

        # Check: answer is not empty
        if not answer or not answer.strip():
            return False, "Answer is empty"

        # Check: chunks were retrieved (except for off-topic)
        if name != "off_topic" and len(chunks) == 0:
            return False, "No chunks retrieved"

        # Check: citations present (except for off-topic which may use fallback)
        citations = CITATION_PATTERN.findall(answer)
        if name == "off_topic":
            # Off-topic: either fallback message OR a polite decline — both are valid
            trace.update(
                output={"answer": answer, "passed": True, "off_topic": True},
                metadata={"duration_ms": round(duration_ms, 1)},
            )
            trace.end()
            return True, f"OK (off-topic handled) [{duration_ms:.0f}ms]"

        if not citations:
            return False, f"No citations found in answer: {answer[:100]}..."

        # Update the trace with the final result
        trace.update(
            output={"answer": answer, "passed": True, "citation_count": len(citations)},
            metadata={"duration_ms": round(duration_ms, 1)},
        )
        trace.end()

        return True, f"OK — {len(citations)} citation(s) [{duration_ms:.0f}ms]"

    except Exception as e:
        return False, f"EXCEPTION: {type(e).__name__}: {e}"


def main() -> None:
    """Run all integration tests and report results."""
    print("\n" + "=" * 70)
    print("  RAG DevDocs — Phase 2 Integration Test")
    print("=" * 70)

    passed = 0
    failed = 0
    results: list[tuple[str, bool, str]] = []

    for name, question in TEST_CASES:
        print(f"\n  Running: {name}")
        print(f"  Query:   \"{question}\"")

        ok, detail = run_test(name, question)
        results.append((name, ok, detail))

        if ok:
            passed += 1
            print(f"  Result:  PASS — {detail}")
        else:
            failed += 1
            print(f"  Result:  FAIL — {detail}")

    # --- Summary ---
    print("\n" + "=" * 70)
    print(f"  RESULTS: {passed} passed, {failed} failed, {len(TEST_CASES)} total")
    print("=" * 70)

    if failed > 0:
        print("\n  Failed tests:")
        for name, ok, detail in results:
            if not ok:
                print(f"    - {name}: {detail}")
        print()

    # Flush all pending Langfuse traces before exiting
    get_langfuse_client().flush()

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
