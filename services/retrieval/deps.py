import os

from qdrant_client import QdrantClient

from services.retrieval.bm25 import BM25Store
from services.retrieval.config import settings
from services.retrieval.dense import DenseStore
from services.retrieval.engine import RetrievalEngine


_engine: RetrievalEngine | None = None


def get_engine() -> RetrievalEngine:
    global _engine
    if _engine is None:
        client = QdrantClient(url=settings.qdrant_url)
        dense = DenseStore(client, settings.qdrant_collection)
        bm25 = BM25Store()
        bm25_path = os.path.join(settings.data_dir, "bm25_index.pkl")
        bm25.load(bm25_path)
        _engine = RetrievalEngine(dense, bm25)
    return _engine


def reset_engine() -> None:
    global _engine
    _engine = None
