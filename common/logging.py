"""Structured logging configuration for RAG DevDocs.

Uses structlog to produce JSON-formatted log entries for every
query flowing through the pipeline. Each log entry captures:
- What happened (event name)
- Timing (how long each step took)
- Scores (retrieval distances, BM25 scores, RRF scores, rerank scores)
- Chunk identifiers (source paths for retrieved documents)

This powers the CI eval gate (parse JSON logs to verify pipeline behaviour)
and serves as the local development observability layer. In production,
Langfuse (Phase 2.5) runs alongside this for cloud-based tracing.

Usage:
    from common.logging import get_logger

    logger = get_logger("retriever.hybrid")
    logger.info("vector_search_complete", top_k=20, duration_ms=134.5)
"""

import structlog


def configure_logging() -> None:
    """Set up structlog with JSON rendering for all loggers.

    Call this once at application startup (in cli.py or api/main.py).
    After this, every logger created with get_logger() will output
    structured JSON lines to stdout.
    """
    structlog.configure(
        processors=[
            # Add log level (info, warning, error) to every entry
            structlog.stdlib.add_log_level,
            # Add ISO-format timestamp to every entry
            structlog.processors.TimeStamper(fmt="iso"),
            # Pretty-print for local dev (human-readable),
            # switch to JSONRenderer() for production/CI
            structlog.dev.ConsoleRenderer(),
        ],
        # Use a plain dict as the base context (not a thread-local)
        context_class=dict,
        # Use the standard library logger factory
        logger_factory=structlog.PrintLoggerFactory(),
        # Cache the logger on first use for performance
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Create a named structured logger.

    The name typically matches the module path (e.g., "retriever.hybrid")
    and appears in every log entry so you can filter by component.

    Args:
        name: Logger name, usually the module path.

    Returns:
        A structlog BoundLogger that outputs structured JSON entries.
    """
    return structlog.get_logger(name)
