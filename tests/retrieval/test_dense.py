import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from services.retrieval.dense import DenseStore


@pytest.fixture
def dense_store(mocker):
    mocker.patch(
        "services.retrieval.dense.embed_texts",
        side_effect=lambda texts: [[float(i)] * 384 for i, _ in enumerate(texts)],
    )
    client = QdrantClient(":memory:")
    return DenseStore(client=client, collection_name="test_chunks")


def test_dense_add_and_query(dense_store):
    dense_store.add_chunks(
        chunk_ids=["c1", "c2"],
        documents=["Messi scored against Real Madrid.", "Ronaldo won the UCL."],
        project_ids=[None, None],
        metadatas=[
            {"source_file": "a.txt", "section_heading": "Goals", "page_number": 1},
            {"source_file": "b.txt", "section_heading": "", "page_number": -1},
        ],
    )

    results = dense_store.query("Messi Real Madrid", top_k=1, project_id=None)

    assert len(results) == 1
    assert results[0]["chunk_id"] in ("c1", "c2")
    assert "document" in results[0]
    assert results[0]["metadata"]["source_file"] == results[0]["metadata"]["source_file"]


def test_dense_filters_by_project_id(dense_store):
    dense_store.add_chunks(
        chunk_ids=["g1", "p1"],
        documents=["global article", "project notes"],
        project_ids=[None, "proj-1"],
        metadatas=[
            {"source_file": "global.csv"},
            {"source_file": "notes.md"},
        ],
    )

    global_hits = dense_store.query("article", top_k=5, project_id=None)
    project_hits = dense_store.query("notes", top_k=5, project_id="proj-1")

    assert [r["chunk_id"] for r in global_hits] == ["g1"]
    assert [r["chunk_id"] for r in project_hits] == ["p1"]


def test_dense_delete_project(dense_store):
    dense_store.add_chunks(
        chunk_ids=["g1", "p1", "p2"],
        documents=["global", "proj one", "proj two"],
        project_ids=[None, "proj-1", "proj-1"],
        metadatas=[{}, {}, {}],
    )

    removed = dense_store.delete_project("proj-1")

    assert removed == 2
    assert dense_store.count(project_id="proj-1") == 0
    assert dense_store.count(project_id=None) == 1
