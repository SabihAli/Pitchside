"""Per-session event bus for live pipeline status, streamed to clients over SSE.

With ``REDIS_URL`` set, events go to a Redis Stream per session, so the
request running the pipeline and the request streaming its events can land
on different processes (serverless instances, multiple replicas). Without
it, an in-process buffer is used -- fine for a single local container.

Event ids are opaque strings; a client resumes after a dropped connection by
passing the last id it saw (SSE ``Last-Event-ID``).
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any

_STREAM_MAXLEN = 500
_STREAM_TTL_SECONDS = 3600


def _redis_url() -> str:
    return os.getenv("PIPELINE_EVENTS_REDIS_URL") or os.getenv("REDIS_URL", "")


def _key(session_id: str) -> str:
    return f"pipeline:events:{session_id}"


class _MemoryBus:
    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._events: dict[str, list[tuple[int, dict[str, Any]]]] = {}
        self._seq = 0

    def emit(self, session_id: str, event: dict[str, Any]) -> None:
        with self._cond:
            self._seq += 1
            rows = self._events.setdefault(session_id, [])
            rows.append((self._seq, event))
            del rows[:-_STREAM_MAXLEN]
            self._cond.notify_all()

    def latest_id(self, session_id: str) -> str:
        with self._cond:
            return str(self._seq)

    def read(
        self, session_id: str, last_id: str, block_ms: int
    ) -> list[tuple[str, dict[str, Any]]]:
        after = int(last_id or 0)
        with self._cond:

            def pending() -> list[tuple[int, dict[str, Any]]]:
                return [r for r in self._events.get(session_id, []) if r[0] > after]

            rows = pending()
            if not rows:
                self._cond.wait(timeout=block_ms / 1000)
                rows = pending()
            return [(str(seq), event) for seq, event in rows]


class _RedisBus:
    def __init__(self, url: str) -> None:
        import redis

        self._client = redis.Redis.from_url(url, decode_responses=True)

    def emit(self, session_id: str, event: dict[str, Any]) -> None:
        key = _key(session_id)
        pipe = self._client.pipeline()
        pipe.xadd(key, {"data": json.dumps(event)}, maxlen=_STREAM_MAXLEN, approximate=True)
        pipe.expire(key, _STREAM_TTL_SECONDS)
        pipe.execute()

    def latest_id(self, session_id: str) -> str:
        entries = self._client.xrevrange(_key(session_id), count=1)
        return entries[0][0] if entries else "0-0"

    def read(
        self, session_id: str, last_id: str, block_ms: int
    ) -> list[tuple[str, dict[str, Any]]]:
        result = self._client.xread({_key(session_id): last_id or "0-0"}, block=block_ms)
        rows: list[tuple[str, dict[str, Any]]] = []
        for _stream, entries in result or []:
            for entry_id, fields in entries:
                rows.append((entry_id, json.loads(fields["data"])))
        return rows


_bus: _MemoryBus | _RedisBus | None = None
_bus_lock = threading.Lock()


def _get_bus() -> _MemoryBus | _RedisBus:
    global _bus
    with _bus_lock:
        if _bus is None:
            url = _redis_url()
            _bus = _RedisBus(url) if url else _MemoryBus()
        return _bus


def emit_event(session_id: str, event: dict[str, Any]) -> None:
    if not session_id:
        return
    try:
        _get_bus().emit(session_id, event)
    except Exception:
        # Live status is best-effort; never fail the pipeline over it.
        pass


def resolve_start_id(session_id: str, last_event_id: str | None) -> str:
    """Id to read after: the client's last seen id, or the current tail of the stream."""
    if last_event_id:
        return last_event_id
    return _get_bus().latest_id(session_id)


def read_events(
    session_id: str, last_id: str, block_ms: int = 15000
) -> list[tuple[str, dict[str, Any]]]:
    """Block up to ``block_ms`` for events after ``last_id``; returns (id, event) pairs."""
    return _get_bus().read(session_id, last_id, block_ms)
