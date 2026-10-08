#!/usr/bin/env python3
"""Copy a Qdrant collection, re-embedding every chunk with the API embedder.

The existing knowledge base was embedded locally with MiniLM (384-dim).
Queries are now embedded through ``EMBEDDING_API_URL``/``EMBEDDING_MODEL``,
whose vectors are not comparable with the old ones, so each stored chunk
must be re-embedded once. Point ids and payloads (text, project scope,
citation metadata) are kept as-is; only the vectors change.

Typical use -- local docker Qdrant into a managed Qdrant Cloud cluster:

    EMBEDDING_API_KEY=sk-... python scripts/reembed_qdrant.py \\
        --source-url http://localhost:6333 --source-collection futbot_chunks \\
        --target-url https://<cluster>.cloud.qdrant.io --target-api-key <key> \\
        --target-collection futbot_chunks
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from services.retrieval.embeddings import embed_texts, embedding_dim, embedding_model

logger = logging.getLogger("reembed_qdrant")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--source-api-key", default=None)
    parser.add_argument("--source-collection", default="futbot_chunks")
    parser.add_argument("--target-url", required=True)
    parser.add_argument("--target-api-key", default=None)
    parser.add_argument("--target-collection", default="futbot_chunks")
    parser.add_argument("--batch-size", type=int, default=96)
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop the target collection first if it already exists.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    source = QdrantClient(url=args.source_url, api_key=args.source_api_key)
    target = QdrantClient(url=args.target_url, api_key=args.target_api_key)

    same_place = (
        args.source_url.rstrip("/") == args.target_url.rstrip("/")
        and args.source_collection == args.target_collection
    )
    if same_place:
        logger.error("Source and target are the same collection; pick a new target name.")
        return 2

    if target.collection_exists(args.target_collection):
        if not args.recreate:
            logger.error(
                "Target collection %s exists; pass --recreate to overwrite it.",
                args.target_collection,
            )
            return 2
        target.delete_collection(args.target_collection)
    target.create_collection(
        collection_name=args.target_collection,
        vectors_config=VectorParams(size=embedding_dim(), distance=Distance.COSINE),
    )

    total = source.count(args.source_collection, exact=True).count
    logger.info(
        "Re-embedding %s chunks with %s (%s-dim)", total, embedding_model(), embedding_dim()
    )

    done = 0
    offset = None
    while True:
        points, offset = source.scroll(
            collection_name=args.source_collection,
            limit=args.batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        if points:
            texts = [str((p.payload or {}).get("document", "")) for p in points]
            vectors = embed_texts(texts)
            target.upsert(
                collection_name=args.target_collection,
                points=[
                    PointStruct(id=p.id, vector=v, payload=p.payload)
                    for p, v in zip(points, vectors, strict=True)
                ],
            )
            done += len(points)
            logger.info("%s / %s", done, total)
        if offset is None:
            break

    logger.info("Done: %s chunks written to %s", done, args.target_collection)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
