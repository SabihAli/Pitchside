"""Text embeddings via an OpenAI-compatible ``/embeddings`` HTTP API.

No local model is loaded, so this runs in a small serverless function.
Changing ``EMBEDDING_MODEL`` / ``EMBEDDING_DIM`` invalidates stored vectors:
re-embed the collection with ``scripts/reembed_qdrant.py``.
"""

import os

import httpx

_BATCH_SIZE = 96


def _api_url() -> str:
    base = os.getenv("EMBEDDING_API_URL", "https://api.openai.com/v1").rstrip("/")
    return f"{base}/embeddings"


def embedding_model() -> str:
    return os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")


def embedding_dim() -> int:
    return int(os.getenv("EMBEDDING_DIM", "1536"))


def _embed_batch(client: httpx.Client, texts: list[str]) -> list[list[float]]:
    api_key = os.getenv("EMBEDDING_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("EMBEDDING_API_KEY is not set.")
    body: dict = {"model": embedding_model(), "input": texts}
    # text-embedding-3-* support server-side truncation to a smaller dimension.
    if os.getenv("EMBEDDING_SEND_DIMENSIONS", "true").lower() in {"1", "true", "yes"}:
        body["dimensions"] = embedding_dim()
    response = client.post(
        _api_url(),
        headers={"Authorization": f"Bearer {api_key}"},
        json=body,
    )
    response.raise_for_status()
    rows = sorted(response.json()["data"], key=lambda r: r["index"])
    return [row["embedding"] for row in rows]


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    vectors: list[list[float]] = []
    with httpx.Client(timeout=60.0) as client:
        for start in range(0, len(texts), _BATCH_SIZE):
            vectors.extend(_embed_batch(client, texts[start : start + _BATCH_SIZE]))
    return vectors
