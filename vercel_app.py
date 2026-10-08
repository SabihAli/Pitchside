"""Vercel entrypoint: every backend service in one ASGI app (one Python function).

Public traffic goes to the gateway, mounted at ``/``, exactly as it does in
docker-compose. The other services are mounted under ``/_svc/<name>`` and the
service-to-service URLs (``CHAT_SERVICE_URL`` etc.) point back at this same
deployment, so services keep talking over HTTP without code changes.

``/_svc/*`` must not be reachable from the internet: services trust the
``X-User-ID`` header the gateway sets after verifying the JWT. Those routes
therefore require ``X-Internal-Token: $INTERNAL_API_TOKEN``, which is added
automatically to outgoing httpx requests aimed at the internal base URL.

Not mounted: ingestion -- the knowledge base is read-only on this deployment
(``KNOWLEDGE_UPLOADS_ENABLED=false``), and it needs OCR/PDF tooling.
See docs/DEPLOY_VERCEL.md.
"""

from __future__ import annotations

import asyncio
import hmac
import logging
import os
import sys
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
for _path in (_ROOT, _ROOT / "packages" / "futbot-common"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

logger = logging.getLogger("vercel_app")

INTERNAL_PREFIX = "/_svc"
_SERVICES = {
    # env var with the service URL -> mount name
    "AUTH_SERVICE_URL": "auth",
    "CHAT_SERVICE_URL": "chat",
    "PROJECT_SERVICE_URL": "project",
    "LLM_SERVICE_URL": "llm",
    "LLM_GATEWAY_URL": "llm",
    "RETRIEVAL_SERVICE_URL": "retrieval",
    "ORCHESTRATOR_SERVICE_URL": "orchestrator",
    "OBSERVABILITY_SERVICE_URL": "observability",
    "TOOLS_SERVICE_URL": "tools",
}


def _internal_base_url() -> str:
    explicit = os.getenv("INTERNAL_API_BASE_URL", "").rstrip("/")
    if explicit:
        return explicit
    # VERCEL_URL is this deployment's own hostname (set by the platform).
    host = os.getenv("VERCEL_URL", "localhost:8000")
    scheme = "http" if host.startswith("localhost") else "https"
    return f"{scheme}://{host}"


INTERNAL_BASE_URL = _internal_base_url()
INTERNAL_TOKEN = os.getenv("INTERNAL_API_TOKEN", "")

# Service configs read their URLs at import time, so set them before importing.
for _env_name, _mount in _SERVICES.items():
    os.environ.setdefault(_env_name, f"{INTERNAL_BASE_URL}{INTERNAL_PREFIX}/{_mount}")
os.environ.setdefault("TRACING_ENABLED", "false")


def _install_internal_auth_headers() -> None:
    """Attach the internal token (and Vercel protection bypass) to self-calls."""
    import httpx

    prefix = f"{INTERNAL_BASE_URL}{INTERNAL_PREFIX}/"
    bypass = os.getenv("VERCEL_AUTOMATION_BYPASS_SECRET", "")

    def _tag(request: httpx.Request) -> None:
        if str(request.url).startswith(prefix):
            request.headers["X-Internal-Token"] = INTERNAL_TOKEN
            if bypass:
                request.headers["x-vercel-protection-bypass"] = bypass

    sync_send = httpx.Client.send
    async_send = httpx.AsyncClient.send

    def send(self, request, **kwargs):
        _tag(request)
        return sync_send(self, request, **kwargs)

    async def asend(self, request, **kwargs):
        _tag(request)
        return await async_send(self, request, **kwargs)

    httpx.Client.send = send
    httpx.AsyncClient.send = asend


_install_internal_auth_headers()

from starlette.applications import Starlette  # noqa: E402
from starlette.responses import JSONResponse  # noqa: E402
from starlette.routing import Mount  # noqa: E402

from services.auth.app import create_app as create_auth  # noqa: E402
from services.chat.app import create_app as create_chat  # noqa: E402
from services.gateway.app import create_app as create_gateway  # noqa: E402
from services.llm_gateway.app import create_app as create_llm  # noqa: E402
from services.observability.app import create_app as create_observability  # noqa: E402
from services.project.app import create_app as create_project  # noqa: E402
from services.rag_orchestrator.app import create_app as create_orchestrator  # noqa: E402
from services.retrieval.app import create_app as create_retrieval  # noqa: E402
from services.tools.app import create_app as create_tools  # noqa: E402

_internal_apps = {
    "auth": create_auth(),
    "chat": create_chat(),
    "project": create_project(),
    "llm": create_llm(),
    "retrieval": create_retrieval(),
    "orchestrator": create_orchestrator(),
    "observability": create_observability(),
    "tools": create_tools(),
}
_gateway = create_gateway()

# Startup hooks to run once per instance. Retrieval's startup (a legacy
# ChromaDB import) is skipped; its engine is built lazily on first query.
_STARTUP_APPS = ("auth", "chat", "project", "orchestrator", "observability", "tools")

_startup_lock = asyncio.Lock()
_startup_stack: AsyncExitStack | None = None


async def _ensure_started() -> None:
    global _startup_stack
    if _startup_stack is not None:
        return
    async with _startup_lock:
        if _startup_stack is not None:
            return
        stack = AsyncExitStack()
        for name in _STARTUP_APPS:
            sub = _internal_apps[name]
            await stack.enter_async_context(sub.router.lifespan_context(sub))
        _startup_stack = stack


@asynccontextmanager
async def _lifespan(_app: Starlette):
    await _ensure_started()
    yield
    if _startup_stack is not None:
        await _startup_stack.aclose()


class _Guard:
    """Runs service startup on first request (in case the platform skips ASGI
    lifespan) and keeps /_svc/* closed to callers without the internal token."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "http":
            await _ensure_started()
            path = scope.get("path", "")
            if path == INTERNAL_PREFIX or path.startswith(INTERNAL_PREFIX + "/"):
                supplied = dict(scope.get("headers") or []).get(b"x-internal-token", b"")
                if not INTERNAL_TOKEN or not hmac.compare_digest(
                    supplied, INTERNAL_TOKEN.encode()
                ):
                    response = JSONResponse(
                        {"error": {"code": "NOT_FOUND", "message": "Route not found"}},
                        status_code=404,
                    )
                    await response(scope, receive, send)
                    return
        await self.app(scope, receive, send)


if not INTERNAL_TOKEN:
    logger.error("INTERNAL_API_TOKEN is not set; internal service calls will be refused.")

_starlette = Starlette(
    routes=[
        *(Mount(f"{INTERNAL_PREFIX}/{name}", app=sub) for name, sub in _internal_apps.items()),
        Mount("/", app=_gateway),
    ],
    lifespan=_lifespan,
)

app = _Guard(_starlette)
