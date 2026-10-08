from typing import Optional

from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

_EMBEDDER: Optional[DefaultEmbeddingFunction] = None


def _get_embedder() -> DefaultEmbeddingFunction:
    global _EMBEDDER
    if _EMBEDDER is None:
        _EMBEDDER = DefaultEmbeddingFunction()
    return _EMBEDDER


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return _get_embedder()(texts)
