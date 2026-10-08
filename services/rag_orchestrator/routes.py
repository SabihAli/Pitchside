import asyncio
import json
import os
import time
from typing import AsyncIterator

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import StreamingResponse

from futbot_common.responses import DataResponse
from services.rag_orchestrator.pipeline_events import (
    emit_event,
    read_events,
    resolve_start_id,
)
from services.rag_orchestrator.schemas import PipelineRunRequest, PipelineRunResponse

router = APIRouter(tags=["pipeline"])


def _run_pipeline(**kwargs):
    from services.rag_orchestrator.graph import run_pipeline

    return run_pipeline(**kwargs)


@router.post("/pipeline/run", response_model=DataResponse[PipelineRunResponse])
def pipeline_run(body: PipelineRunRequest) -> DataResponse[PipelineRunResponse]:
    emit_event(body.session_id, {"type": "pipeline_start", "query": body.query})

    try:
        result = _run_pipeline(
            query=body.query,
            context_messages=body.context_messages,
            session_id=body.session_id,
            snapshot=body.snapshot,
            snapshot_turn_count=body.snapshot_turn_count,
            project_id=body.project_id,
            user_id=body.user_id,
            web_search_enabled=body.web_search_enabled,
        )
    except Exception as exc:
        emit_event(body.session_id, {"type": "pipeline_error", "message": str(exc)})
        return DataResponse(
            data=PipelineRunResponse(
                reply=f"Pipeline failed: {exc}",
                snapshot=body.snapshot,
                snapshot_turn_count=body.snapshot_turn_count,
            )
        )

    return DataResponse(data=PipelineRunResponse(**result))


# Each SSE response ends after this long; EventSource reconnects with
# Last-Event-ID and resumes. Keep it below the platform's function timeout.
_SSE_MAX_SECONDS = float(os.getenv("SSE_MAX_SECONDS", "240"))
_SSE_POLL_MS = 15000


def _sse(event: dict, event_id: str | None = None) -> str:
    head = f"id: {event_id}\n" if event_id else ""
    return f"{head}data: {json.dumps(event)}\n\n"


@router.get("/pipeline/events")
async def pipeline_events(
    request: Request,
    session_id: str = Query(...),
    last_event_id: str | None = Header(default=None),
) -> StreamingResponse:
    async def stream() -> AsyncIterator[str]:
        cursor = await asyncio.to_thread(resolve_start_id, session_id, last_event_id)
        yield "retry: 2000\n"
        yield _sse({"type": "connected", "session_id": session_id})
        deadline = time.monotonic() + _SSE_MAX_SECONDS
        while time.monotonic() < deadline:
            if await request.is_disconnected():
                return
            rows = await asyncio.to_thread(read_events, session_id, cursor, _SSE_POLL_MS)
            if not rows:
                yield ": ping\n\n"
                continue
            for event_id, event in rows:
                cursor = event_id
                yield _sse(event, event_id)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
