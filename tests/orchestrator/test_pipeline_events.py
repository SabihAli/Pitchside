import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.rag_orchestrator import pipeline_events
from services.rag_orchestrator.routes import router


def _memory_bus(monkeypatch) -> None:
    monkeypatch.setattr(pipeline_events, "_bus", pipeline_events._MemoryBus())


def test_read_events_returns_only_events_after_cursor(monkeypatch):
    _memory_bus(monkeypatch)
    pipeline_events.emit_event("s1", {"type": "old"})
    cursor = pipeline_events.resolve_start_id("s1", None)
    pipeline_events.emit_event("s1", {"type": "pipeline_start"})
    pipeline_events.emit_event("other", {"type": "elsewhere"})

    rows = pipeline_events.read_events("s1", cursor, block_ms=10)

    assert [event["type"] for _, event in rows] == ["pipeline_start"]
    assert pipeline_events.read_events("s1", rows[-1][0], block_ms=10) == []


def test_resume_from_last_event_id(monkeypatch):
    _memory_bus(monkeypatch)
    pipeline_events.emit_event("s1", {"type": "a"})
    pipeline_events.emit_event("s1", {"type": "b"})
    first_id = pipeline_events.read_events("s1", "0", block_ms=10)[0][0]

    start = pipeline_events.resolve_start_id("s1", first_id)

    assert [e["type"] for _, e in pipeline_events.read_events("s1", start, 10)] == ["b"]


def test_sse_endpoint_streams_events(monkeypatch):
    _memory_bus(monkeypatch)
    monkeypatch.setattr("services.rag_orchestrator.routes._SSE_MAX_SECONDS", 0.5)
    monkeypatch.setattr("services.rag_orchestrator.routes._SSE_POLL_MS", 50)
    pipeline_events.emit_event("s1", {"type": "pipeline_start"})
    pipeline_events.emit_event("s1", {"type": "pipeline_complete", "reply": "hi"})
    app = FastAPI()
    app.include_router(router)

    with TestClient(app) as client:
        response = client.get(
            "/pipeline/events", params={"session_id": "s1"}, headers={"Last-Event-ID": "0"}
        )

    assert response.headers["content-type"].startswith("text/event-stream")
    events = [
        json.loads(line[len("data: "):])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert [e["type"] for e in events] == ["connected", "pipeline_start", "pipeline_complete"]
