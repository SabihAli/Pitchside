import pytest
from httpx import ASGITransport, AsyncClient
from qdrant_client import QdrantClient

from services.retrieval.app import create_app
from services.retrieval.bm25 import BM25Store
from services.retrieval.dense import DenseStore
from services.retrieval.deps import get_engine
from services.retrieval.engine import RetrievalEngine


@pytest.fixture
def retrieval_client(mocker, tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    mocker.patch(
        "services.retrieval.dense.embed_texts",
        side_effect=lambda texts: [[0.1] * 384 for _ in texts],
    )
    mocker.patch("services.retrieval.app.run_startup_migration")

    dense = DenseStore(QdrantClient(":memory:"), "route_test")
    bm25 = BM25Store()
    engine = RetrievalEngine(dense, bm25)

    app = create_app()
    app.dependency_overrides[get_engine] = lambda: engine
    transport = ASGITransport(app=app)
    yield AsyncClient(transport=transport, base_url="http://test"), engine
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_retrieve_endpoint_returns_citations(retrieval_client):
    client, engine = retrieval_client
    engine.index_chunks(
        project_id=None,
        file_id="f1",
        chunk_ids=["c1"],
        documents=["Messi scored."],
        bm25_documents=["Messi scored."],
        metadatas=[{"source_file": "news.csv", "section_heading": "Goals", "page_number": 1}],
    )

    async with client:
        response = await client.post(
            "/retrieve",
            json={"query": "Messi", "top_k": 1, "project_id": None},
        )

    assert response.status_code == 200
    chunks = response.json()["data"]["chunks"]
    assert len(chunks) == 1
    assert chunks[0]["chunk_id"] == "c1"
    assert chunks[0]["source_file"] == "news.csv"
    assert chunks[0]["page"] == 1


@pytest.mark.asyncio
async def test_index_chunks_endpoint(retrieval_client):
    client, engine = retrieval_client

    async with client:
        response = await client.post(
            "/index/chunks",
            json={
                "project_id": "proj-1",
                "file_id": "file-9",
                "chunks": [
                    {
                        "chunk_id": "p1",
                        "text": "Project specific tactics",
                        "source_file": "tactics.md",
                        "section_heading": "Defense",
                    }
                ],
            },
        )

    assert response.status_code == 200
    assert response.json()["data"]["indexed"] == 1
    hits = engine.retrieve("tactics", top_k=1, project_id="proj-1")
    assert hits[0]["chunk_id"] == "p1"


@pytest.mark.asyncio
async def test_delete_project_index_endpoint(retrieval_client):
    client, engine = retrieval_client
    engine.index_chunks(
        project_id="proj-x",
        file_id="f",
        chunk_ids=["x1"],
        documents=["secret project doc"],
        bm25_documents=["secret project doc"],
        metadatas=[{"source_file": "x.md"}],
    )

    async with client:
        response = await client.delete("/index/proj-x")

    assert response.status_code == 200
    assert response.json()["data"]["removed"] >= 1
    assert engine.retrieve("secret", top_k=5, project_id="proj-x") == []
