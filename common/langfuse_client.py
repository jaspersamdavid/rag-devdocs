"""Langfuse observability client for RAG DevDocs.

Centralises the Langfuse client so all modules import from one place.
The client auto-reads connection details from environment variables:
    - LANGFUSE_PUBLIC_KEY
    - LANGFUSE_SECRET_KEY
    - LANGFUSE_HOST

Uses Langfuse v4 API which is based on OpenTelemetry-style observations.

Usage:
    from common.langfuse_client import get_langfuse_client

    langfuse = get_langfuse_client()
    with langfuse.start_as_current_observation(name="my-step", as_type="span") as span:
        # do work
        span.end(output={"result": "..."})
"""

from langfuse import Langfuse, get_client


def get_langfuse_client() -> Langfuse:
    """Return the shared Langfuse client.

    In v4, `get_client()` returns the global singleton client that
    auto-reads LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, and LANGFUSE_HOST
    from environment variables.

    Returns:
        A configured Langfuse client ready to create observations.
    """
    return get_client()
