from typing import Any
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from services.retrieval.embeddings import embed_texts

GLOBAL_PROJECT_KEY = "__global__"


def _point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


def _storage_project_id(project_id: str | None) -> str:
    return project_id if project_id is not None else GLOBAL_PROJECT_KEY


def _filter_for_project(project_id: str | None) -> Filter:
    return Filter(
        must=[
            FieldCondition(
                key="project_id",
                match=MatchValue(value=_storage_project_id(project_id)),
            )
        ]
    )


class DenseStore:
    def __init__(self, client: QdrantClient, collection_name: str) -> None:
        self._client = client
        self._collection = collection_name
        if not self._client.collection_exists(self._collection):
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )

    def add_chunks(
        self,
        chunk_ids: list[str],
        documents: list[str],
        project_ids: list[str | None],
        metadatas: list[dict[str, Any]],
    ) -> None:
        vectors = embed_texts(documents)
        points = []
        for chunk_id, doc, project_id, meta in zip(
            chunk_ids, documents, project_ids, metadatas, strict=True
        ):
            payload = {
                **meta,
                "chunk_id": chunk_id,
                "document": doc,
                "project_id": _storage_project_id(project_id),
            }
            points.append(
                PointStruct(id=_point_id(chunk_id), vector=vectors[len(points)], payload=payload)
            )
        self._client.upsert(collection_name=self._collection, points=points)

    def add_chunks_with_vectors(
        self,
        chunk_ids: list[str],
        documents: list[str],
        vectors: list[list[float]],
        project_ids: list[str | None],
        metadatas: list[dict[str, Any]],
    ) -> None:
        points = []
        for chunk_id, doc, vector, project_id, meta in zip(
            chunk_ids, documents, vectors, project_ids, metadatas, strict=True
        ):
            payload = {
                **meta,
                "chunk_id": chunk_id,
                "document": doc,
                "project_id": _storage_project_id(project_id),
            }
            points.append(PointStruct(id=_point_id(chunk_id), vector=vector, payload=payload))
        self._client.upsert(collection_name=self._collection, points=points)

    def query(
        self, query_text: str, top_k: int = 5, project_id: str | None = None
    ) -> list[dict[str, Any]]:
        vector = embed_texts([query_text])[0]
        hits = self._client.query_points(
            collection_name=self._collection,
            query=vector,
            limit=top_k,
            query_filter=_filter_for_project(project_id),
        ).points

        results: list[dict[str, Any]] = []
        for point in hits:
            payload = dict(point.payload or {})
            chunk_id = payload.pop("chunk_id", str(point.id))
            document = payload.pop("document", "")
            payload.pop("project_id", None)
            results.append(
                {
                    "chunk_id": chunk_id,
                    "document": document,
                    "metadata": payload,
                    "distance": point.score,
                }
            )
        return results

    def count(self, project_id: str | None = None) -> int:
        result = self._client.count(
            collection_name=self._collection,
            count_filter=_filter_for_project(project_id),
            exact=True,
        )
        return int(result.count)

    def delete_project(self, project_id: str) -> int:
        before = self.count(project_id=project_id)
        self._client.delete(
            collection_name=self._collection,
            points_selector=_filter_for_project(project_id),
        )
        return before
