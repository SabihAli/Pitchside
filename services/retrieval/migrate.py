import logging
import os

import chromadb

from services.retrieval.bm25 import BM25Store
from services.retrieval.config import settings
from services.retrieval.engine import RetrievalEngine

logger = logging.getLogger(__name__)


def migrate_chroma_to_qdrant(engine: RetrievalEngine) -> int:
    """Import legacy ChromaDB + BM25 pickle into Qdrant/BM25 store."""
    if not os.path.isdir(settings.chroma_path):
        return 0

    client = chromadb.PersistentClient(path=settings.chroma_path)
    collection_names = [c.name for c in client.list_collections()]
    if not collection_names:
        return 0

    collection = client.get_collection(collection_names[0])
    total = collection.count()
    if total == 0:
        return 0

    if engine.dense.count(project_id=None) > 0:
        return 0

    batch_size = 100
    migrated = 0
    offset = 0
    while offset < total:
        batch = collection.get(
            include=["documents", "metadatas", "embeddings"],
            limit=batch_size,
            offset=offset,
        )
        ids = batch.get("ids") or []
        if not ids:
            break

        documents = batch["documents"]
        metadatas = batch["metadatas"]
        embeddings = batch.get("embeddings")
        project_ids = [None] * len(ids)
        enriched = []
        for meta in metadatas:
            row = dict(meta or {})
            row.setdefault("project_id", None)
            enriched.append(row)

        if embeddings:
            engine.dense.add_chunks_with_vectors(ids, documents, embeddings, project_ids, enriched)
        else:
            engine.dense.add_chunks(ids, documents, project_ids, enriched)

        bm25_texts = list(documents)
        engine.bm25.import_legacy(ids, bm25_texts, enriched)
        migrated += len(ids)
        offset += len(ids)

    legacy_bm25 = BM25Store()
    if legacy_bm25.load(settings.bm25_path) and legacy_bm25.is_loaded():
        engine.bm25.import_legacy(
            legacy_bm25.chunk_ids,
            legacy_bm25.corpus,
            legacy_bm25.metadatas,
        )

    engine.bm25.save(settings.bm25_path)
    logger.info("Migrated %s chunks from ChromaDB to Qdrant", migrated)
    return migrated


def run_startup_migration() -> None:
    from services.retrieval.deps import get_engine

    try:
        migrate_chroma_to_qdrant(get_engine())
    except Exception as exc:
        logger.warning("Retrieval migration skipped: %s", exc)
