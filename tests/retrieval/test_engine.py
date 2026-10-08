import pytest
from qdrant_client import QdrantClient

from services.retrieval.bm25 import BM25Store
from services.retrieval.dense import DenseStore
from services.retrieval.engine import RetrievalEngine


@pytest.fixture
def engine(mocker):
    mocker.patch(
        "services.retrieval.dense.embed_texts",
        side_effect=lambda texts: [[0.1] * 384 for _ in texts],
    )
    dense = DenseStore(QdrantClient(":memory:"), "hybrid_test")
    bm25 = BM25Store()
    return RetrievalEngine(dense, bm25)


def test_hybrid_retrieve_returns_citation_fields(engine):
    engine.index_chunks(
        project_id=None,
        file_id="file-1",
        chunk_ids=["chunk_001"],
        documents=["Messi scored against Real Madrid."],
        bm25_documents=["Messi scored against Real Madrid."],
        metadatas=[
            {
                "source_file": "news.csv",
                "section_heading": "La Liga",
                "page_number": 2,
            }
        ],
    )

    results = engine.retrieve("Messi Real Madrid", top_k=1, project_id=None)

    assert len(results) == 1
    hit = results[0]
    assert hit["chunk_id"] == "chunk_001"
    assert hit["source_file"] == "news.csv"
    assert hit["page"] == 2
    assert hit["section_heading"] == "La Liga"
    assert hit["document"]
    assert hit["rrf_score"] > 0


def test_hybrid_scopes_project_chunks(engine):
    engine.index_chunks(
        project_id=None,
        file_id="g",
        chunk_ids=["g1"],
        documents=["global football"],
        bm25_documents=["global football"],
        metadatas=[{"source_file": "global.csv"}],
    )
    engine.index_chunks(
        project_id="proj-9",
        file_id="p",
        chunk_ids=["p1"],
        documents=["project tactics board"],
        bm25_documents=["project tactics board"],
        metadatas=[{"source_file": "board.md"}],
    )

    global_hits = engine.retrieve("football", top_k=5, project_id=None)
    project_hits = engine.retrieve("tactics", top_k=5, project_id="proj-9")

    assert [h["chunk_id"] for h in global_hits] == ["g1"]
    assert [h["chunk_id"] for h in project_hits] == ["p1"]
