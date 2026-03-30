"""RAGAS evaluation script for the RAG DevDocs pipeline.

Loads the golden eval dataset, runs each question through the full
hybrid retrieval + generation pipeline, then scores the results
using RAGAS metrics.

Also runs a consistency check on list-all / rephrased-list-all
question pairs to measure answer stability across rephrasings.

Usage:
    # Run full eval with default threshold (0.75)
    python eval/run_eval.py

    # Run with custom threshold
    python eval/run_eval.py --threshold 0.80

    # Skip consistency check
    python eval/run_eval.py --skip-consistency

Exit codes:
    0 = all metrics above threshold (CI pass)
    1 = at least one metric below threshold (CI fail)
"""

import argparse
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from ragas import EvaluationDataset, SingleTurnSample, evaluate
from ragas.embeddings import OpenAIEmbeddings as RagasOpenAIEmbeddings
from ragas.llms import llm_factory
from ragas.metrics._answer_relevance import ResponseRelevancy
from ragas.metrics._answer_similarity import AnswerSimilarity
from ragas.metrics._context_precision import ContextPrecision
from ragas.metrics._faithfulness import Faithfulness

from common.logging import configure_logging, get_logger

load_dotenv()
configure_logging()
log = get_logger("eval")

# ---------------------------------------------------------------------------
# RAGAS LLM + Embeddings (explicit to avoid version mismatch issues)
# ---------------------------------------------------------------------------

_openai_client = OpenAI()
RAGAS_LLM = llm_factory("gpt-4o", client=_openai_client)
# Default max_tokens is 1024 — far too small for Faithfulness metric which
# verifies every statement in a single JSON response.
RAGAS_LLM.model_args["max_tokens"] = 8192

# RAGAS v0.4.3 bug: ResponseRelevancy calls embed_query()/embed_documents()
# (old LangChain interface), but ragas.embeddings.OpenAIEmbeddings only
# provides embed_text()/embed_texts() (new interface).  This wrapper bridges
# the gap so the metric doesn't crash with AttributeError.
_raw_embeddings = RagasOpenAIEmbeddings(client=_openai_client)


class _CompatEmbeddings:
    """Adapter: expose embed_query / embed_documents AND async variants.

    RAGAS metrics use a mix of old (embed_query) and new (embed_text) interfaces,
    plus async variants. This wrapper bridges all of them to the sync OpenAI client.
    """

    def __init__(self, inner: RagasOpenAIEmbeddings):
        self._inner = inner

    def embed_query(self, text: str) -> list[float]:
        return self._inner.embed_text(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._inner.embed_texts(texts)

    def embed_text(self, text: str) -> list[float]:
        return self._inner.embed_text(text)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return self._inner.embed_texts(texts)

    async def aembed_text(self, text: str) -> list[float]:
        # AnswerSimilarity calls async, but our client is sync — just delegate
        return self._inner.embed_text(text)

    async def aembed_query(self, text: str) -> list[float]:
        return self._inner.embed_text(text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._inner.embed_texts(texts)

    # Forward everything else so RAGAS internals still work
    def __getattr__(self, name):
        return getattr(self._inner, name)


RAGAS_EMBEDDINGS = _CompatEmbeddings(_raw_embeddings)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

GOLDEN_PATH = Path(__file__).resolve().parent / "golden.json"

# ---------------------------------------------------------------------------
# Load golden dataset
# ---------------------------------------------------------------------------


def load_golden(path: Path | None = None) -> list[dict]:
    """Load the golden eval dataset from JSON."""
    p = path or GOLDEN_PATH
    with open(p) as f:
        data = json.load(f)
    log.info("golden_loaded", path=str(p), count=len(data))
    return data


# ---------------------------------------------------------------------------
# Run pipeline on each question
# ---------------------------------------------------------------------------


def run_pipeline(golden: list[dict]) -> list[dict]:
    """Run each golden question through the RAG pipeline.

    Returns a list of dicts with keys:
        - question, ground_truth, answer, contexts, question_type, source_doc
    """
    # Import here to avoid slow module-level imports during --help
    from api.generate import generate
    from retriever.hybrid import hybrid_retrieve

    results = []
    for i, item in enumerate(golden, start=1):
        question = item["question"]
        log.info(
            "eval_question",
            index=i,
            total=len(golden),
            question=question[:80],
        )

        t0 = time.perf_counter()

        # Step 1: Retrieve
        chunks = hybrid_retrieve(question, use_reranker=True)

        # Step 2: Generate
        answer = generate(question, chunks)

        duration_ms = (time.perf_counter() - t0) * 1000

        # Extract context strings for RAGAS
        contexts = [chunk.page_content for chunk in chunks]

        results.append(
            {
                "question": question,
                "ground_truth": item["ground_truth_answer"],
                "answer": answer,
                "contexts": contexts,
                "question_type": item.get("question_type", "unknown"),
                "source_doc": item.get("source_doc", "unknown"),
                "duration_ms": round(duration_ms, 1),
            }
        )

        log.info(
            "eval_question_complete",
            index=i,
            duration_ms=round(duration_ms, 1),
            answer_length=len(answer),
            context_count=len(contexts),
        )

    return results


# ---------------------------------------------------------------------------
# RAGAS evaluation
# ---------------------------------------------------------------------------


def run_ragas_eval(results: list[dict]) -> dict:
    """Score all results using RAGAS metrics.

    Returns a dict with metric names as keys and scores as values.
    """
    # Build RAGAS dataset
    samples = []
    for r in results:
        samples.append(
            SingleTurnSample(
                user_input=r["question"],
                response=r["answer"],
                retrieved_contexts=r["contexts"],
                reference=r["ground_truth"],
            )
        )

    dataset = EvaluationDataset(samples=samples)

    metrics = [
        Faithfulness(llm=RAGAS_LLM),
        ResponseRelevancy(llm=RAGAS_LLM, embeddings=RAGAS_EMBEDDINGS),
        ContextPrecision(llm=RAGAS_LLM),
    ]

    metric_names = [m.name for m in metrics]
    log.info("ragas_eval_start", sample_count=len(samples), metrics=metric_names)

    t0 = time.perf_counter()
    result = evaluate(
        dataset=dataset,
        metrics=metrics,
        llm=RAGAS_LLM,
        embeddings=RAGAS_EMBEDDINGS,
        show_progress=True,
    )
    eval_ms = (time.perf_counter() - t0) * 1000

    # Extract per-question scores from pandas DataFrame
    df = result.to_pandas()

    # Add question_type and source_doc columns for grouping in the report
    df["question_type"] = [r["question_type"] for r in results]
    df["source_doc"] = [r["source_doc"] for r in results]

    # Compute aggregate scores (mean of each metric column)
    scores = {}
    for name in metric_names:
        if name in df.columns:
            scores[name] = round(df[name].mean(), 4)

    log.info("ragas_eval_complete", duration_ms=round(eval_ms, 1), scores=scores)
    return {"aggregate": scores, "per_question": df, "eval_ms": eval_ms}


# ---------------------------------------------------------------------------
# Consistency check: list-all vs rephrased-list-all
# ---------------------------------------------------------------------------


def run_consistency_check(results: list[dict]) -> list[dict]:
    """Compare list-all and rephrased-list-all answer pairs per source.

    Uses RAGAS AnswerSimilarity to score how consistent the pipeline
    is when the same question is asked with different wording.

    Returns a list of dicts with source, score, and both answers.
    """
    # Group by source_doc and question_type
    list_all = {}
    rephrased = {}

    for r in results:
        qtype = r["question_type"]
        source = r["source_doc"]

        if qtype == "factual-list-all":
            list_all[source] = r
        elif qtype == "rephrased-list-all":
            rephrased[source] = r

    # Find matching pairs
    pairs = []
    for source in list_all:
        if source in rephrased:
            pairs.append((source, list_all[source], rephrased[source]))

    if not pairs:
        log.warning("no_consistency_pairs_found")
        return []

    log.info("consistency_check_start", pair_count=len(pairs))

    # Build RAGAS dataset for similarity scoring
    # We compare the list-all answer against the rephrased answer
    samples = []
    for source, la, rp in pairs:
        samples.append(
            SingleTurnSample(
                user_input=la["question"],
                response=la["answer"],
                reference=rp["answer"],  # compare against the rephrased answer
            )
        )

    dataset = EvaluationDataset(samples=samples)
    metrics = [AnswerSimilarity(embeddings=RAGAS_EMBEDDINGS)]

    t0 = time.perf_counter()
    result = evaluate(
        dataset=dataset,
        metrics=metrics,
        llm=RAGAS_LLM,
        embeddings=RAGAS_EMBEDDINGS,
        show_progress=True,
    )
    check_ms = (time.perf_counter() - t0) * 1000

    df = result.to_pandas()

    consistency_results = []
    for i, (source, la, rp) in enumerate(pairs):
        score = float(df.iloc[i].get("answer_similarity", 0.0))
        consistency_results.append(
            {
                "source": source,
                "similarity_score": round(score, 4),
                "list_all_question": la["question"],
                "rephrased_question": rp["question"],
                "list_all_answer_preview": la["answer"][:150],
                "rephrased_answer_preview": rp["answer"][:150],
            }
        )

    log.info("consistency_check_complete", duration_ms=round(check_ms, 1))
    return consistency_results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def print_report(
    ragas_result: dict,
    consistency: list[dict],
    threshold: float,
) -> bool:
    """Print a formatted eval report. Returns True if all metrics pass."""

    scores = ragas_result["aggregate"]
    df = ragas_result["per_question"]

    print("\n" + "=" * 70)
    print("  RAG DEVDOCS — EVALUATION REPORT")
    print("=" * 70)

    # --- Aggregate scores ---
    print("\n--- RAGAS Aggregate Scores ---\n")
    all_pass = True
    for metric, score in scores.items():
        status = "PASS" if score >= threshold else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"  {metric:<30} {score:.4f}  [{status}] (threshold: {threshold})")

    # --- Per question-type breakdown ---
    print("\n--- Scores by Question Type ---\n")
    metric_cols = [c for c in df.columns if c in scores]
    if metric_cols and "question_type" in df.columns:
        grouped = df.groupby("question_type")[metric_cols].mean().round(4)
        print(grouped.to_string())
    else:
        print("  (breakdown not available)")

    # --- Consistency check ---
    if consistency:
        print("\n--- Consistency Check (List-All vs Rephrased) ---\n")
        print(f"  {'Source':<15} {'Similarity':<12} {'Status'}")
        print(f"  {'-'*15} {'-'*12} {'-'*10}")
        for c in sorted(consistency, key=lambda x: x["similarity_score"]):
            score = c["similarity_score"]
            status = "STABLE" if score >= 0.7 else "FRAGILE"
            print(f"  {c['source']:<15} {score:<12.4f} {status}")

        avg_consistency = sum(c["similarity_score"] for c in consistency) / len(
            consistency
        )
        print(f"\n  Average consistency: {avg_consistency:.4f}")

    # --- Summary ---
    print("\n" + "=" * 70)
    eval_time = ragas_result["eval_ms"] / 1000
    print(f"  Total questions: {len(df)}")
    print(f"  RAGAS eval time: {eval_time:.1f}s")
    print(f"  Threshold: {threshold}")
    print(f"  Result: {'ALL PASS' if all_pass else 'FAILED'}")
    print("=" * 70 + "\n")

    return all_pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Run RAGAS evaluation on golden dataset")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.75,
        help="Minimum score for each metric to pass (default: 0.75)",
    )
    parser.add_argument(
        "--golden",
        type=str,
        default=None,
        help="Path to golden JSON file (default: eval/golden.json)",
    )
    parser.add_argument(
        "--skip-consistency",
        action="store_true",
        help="Skip the list-all consistency check",
    )
    args = parser.parse_args()

    log.info("eval_start", threshold=args.threshold)

    # 1. Load golden dataset
    golden_path = Path(args.golden) if args.golden else None
    golden = load_golden(golden_path)

    # 2. Run pipeline on each question
    results = run_pipeline(golden)

    # 3. Run RAGAS evaluation
    ragas_result = run_ragas_eval(results)

    # 4. Run consistency check (optional)
    consistency = []
    if not args.skip_consistency:
        consistency = run_consistency_check(results)

    # 5. Print report and determine exit code
    all_pass = print_report(ragas_result, consistency, args.threshold)

    # 6. Save raw results for debugging
    output_path = Path(__file__).resolve().parent / "eval_results.json"
    output_data = {
        "threshold": args.threshold,
        "aggregate_scores": ragas_result["aggregate"],
        "consistency": consistency,
        "per_question": [
            {
                "question": r["question"],
                "question_type": r["question_type"],
                "source_doc": r["source_doc"],
                "answer_preview": r["answer"][:200],
                "duration_ms": r["duration_ms"],
            }
            for r in results
        ],
    }
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)
    log.info("results_saved", path=str(output_path))

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
