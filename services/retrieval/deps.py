import logging
import os

from qdrant_client import QdrantClient

from services.retrieval.bm25 import BM25Store
from services.retrieval.config import settings
from services.retrieval.dense import DenseStore
from services.retrieval.engine import RetrievalEngine


logger = logging.getLogger(__name__)

_engine: RetrievalEngine | None = None


def _rebuild_bm25(dense: DenseStore, bm25: BM25Store) -> None:
    """Build the in-memory BM25 index from Qdrant payloads.

    Used where no pickle is on disk (e.g. Vercel, whose filesystem is
    ephemeral). The knowledge base is read-only there, so the index is
    built once per warm instance.
    """
    chunk_ids, corpus, project_ids, metadatas = [], [], [], []
    for chunk_id, document, project_id, meta in dense.iter_all():
        chunk_ids.append(chunk_id)
        corpus.append(document)
        project_ids.append(project_id)
        metadatas.append(meta)
    if chunk_ids:
        bm25.add_chunks(chunk_ids, corpus, project_ids, metadatas)
    logger.info("Rebuilt BM25 index from Qdrant (%s chunks)", len(chunk_ids))


def get_engine() -> RetrievalEngine:
    global _engine
    if _engine is None:
        client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
        dense = DenseStore(client, settings.qdrant_collection)
        bm25 = BM25Store()
        bm25_path = os.path.join(settings.data_dir, "bm25_index.pkl")
        if not bm25.load(bm25_path) and settings.bm25_rebuild_from_qdrant:
            _rebuild_bm25(dense, bm25)
        _engine = RetrievalEngine(dense, bm25)
    return _engine


def reset_engine() -> None:
    global _engine
    _engine = None
