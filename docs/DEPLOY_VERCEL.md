# Deploying Pitchside on Vercel

The repo deploys as **two Vercel projects** from the same Git repository:

| Project  | Root directory | What it runs |
|----------|----------------|--------------|
| backend  | `/` (repo root) | All Python services in one FastAPI function (`vercel_app.py`) |
| frontend | `services/web` | Next.js app; proxies `/api/*` to the backend |

Docker Compose and k8s setups are unchanged and keep working.

## Architecture on Vercel

```
browser ──► frontend (Next.js) ──/api/* rewrite──► backend function (vercel_app.py)
                                                     ├─ /            gateway (public: auth, JWT, routing)
                                                     └─ /_svc/<svc>  auth, chat, project, llm, retrieval,
                                                                     orchestrator, observability, tools
                                                                     (internal: X-Internal-Token required)
External, managed: Postgres · Redis · Qdrant · S3-compatible storage (optional)
```

- The gateway proxies to services over HTTP exactly as in docker-compose.
  Service URLs default to `https://$VERCEL_URL/_svc/<svc>`, which is the
  deployment's own URL.
- `/_svc/*` returns 404 unless the request carries `X-Internal-Token: $INTERNAL_API_TOKEN`.
  `vercel_app.py` adds the header automatically to outgoing self-calls.
- **Ingestion is not deployed.** The knowledge base is read-only
  (`KNOWLEDGE_UPLOADS_ENABLED=false`). Upload endpoints return
  `403 KNOWLEDGE_READ_ONLY`, and the UI hides the upload box.
- Live pipeline status uses **Server-Sent Events**
  (`GET /events/pipeline?session_id=…`). Events go through a Redis Stream, so
  they reach the client whichever instance runs the pipeline.
- `PIPELINE_INLINE=true`: a chat message runs the RAG pipeline inside the
  request (max 300s) and returns the reply. Background tasks are not safe on
  serverless.

## 1. Provision managed services

| Need | Suggested | Notes |
|------|-----------|-------|
| Postgres | Neon (Vercel Marketplace) | Use the **direct** (non-pooled) connection string. asyncpg and PgBouncer transaction pooling don't mix. Tables are created automatically on startup. |
| Redis | Upstash (Vercel Marketplace) | Use the TCP/TLS URL (`rediss://…`), not the REST URL. Needs Streams (`XADD`/`XREAD`). |
| Vector DB | Qdrant Cloud | Holds the re-embedded knowledge base (step 2). |
| File storage | Cloudflare R2 / S3 (optional) | Only needed to serve files uploaded before the KB went read-only. Set `MINIO_*`. |

Size and plan choices for these are up to you. The knowledge base is read-only
on this deployment, so data only grows through Postgres (users, chats) and
Redis (short-lived events and tokens).

## 2. Re-embed the knowledge base (one-off, required)

Retrieval used to embed text locally with MiniLM (384-dim). It now calls an
embeddings API (`EMBEDDING_*`). The old vectors aren't comparable with the new
ones, so every stored chunk must be re-embedded once. Texts and metadata are
kept; only the vectors change.

Run this from a machine that can reach the current Qdrant (e.g. the existing
docker stack):

```bash
pip install -r requirements-docker.txt
EMBEDDING_API_KEY=sk-... EMBEDDING_MODEL=text-embedding-3-small EMBEDDING_DIM=1536 \
python scripts/reembed_qdrant.py \
  --source-url http://localhost:6333 --source-collection futbot_chunks \
  --target-url https://<cluster>.cloud.qdrant.io --target-api-key <key> \
  --target-collection futbot_chunks
```

The backend's `EMBEDDING_MODEL`/`EMBEDDING_DIM` **must match** the values used here.
Cost is a one-off: roughly the number of tokens in the corpus × the model's price.

The BM25 keyword index isn't stored. Each new instance rebuilds it from Qdrant
on its first retrieval call. This adds latency to that first query, which
grows with corpus size.

## 3. Backend project

1. New Vercel project → import this repo → **Root Directory: repo root**.
   Framework preset: FastAPI (auto-detected from `pyproject.toml`).
2. Set the environment variables from [`.env.vercel.example`](../.env.vercel.example).
   - `INTERNAL_API_TOKEN` and `JWT_SECRET`: long random strings (`openssl rand -hex 32`).
3. Deploy. Health check: `GET https://<backend>/health`, which should return `{"status":"ok","service":"gateway"}`.

Config lives in:
- `pyproject.toml`: runtime dependencies (slim set, Python 3.12) and `[tool.vercel] entrypoint = "vercel_app:app"`.
- `vercel.json`: `maxDuration: 300` and the files excluded from the bundle.
- Docker images keep using `requirements-docker.txt`.

**Deployment Protection:** the backend calls its own deployment URL. If
Vercel Authentication or password protection is on, enable **Protection Bypass
for Automation**. Vercel then exposes `VERCEL_AUTOMATION_BYPASS_SECRET`, which
the app sends automatically. Alternatively set `INTERNAL_API_BASE_URL` to an
unprotected production domain.

## 4. Frontend project

1. New Vercel project → same repo → **Root Directory: `services/web`** (Next.js auto-detected).
2. Environment variables:
   - `API_URL=https://<backend-domain>`. Used by the `/api/*` rewrite in `next.config.ts`.
   - `NEXT_PUBLIC_KNOWLEDGE_UPLOADS_ENABLED=false`
3. Update the backend's `WEB_APP_URL` and `GOOGLE_REDIRECT_URI` to the frontend domain,
   and add the redirect URI in Google Cloud Console.

## Limits on Vercel

| Area | Behaviour |
|------|-----------|
| Request time | 300s max per request (`maxDuration`). A pipeline run that exceeds it fails. Raise `maxDuration` on Pro if needed. |
| Knowledge base | Read-only. No uploads, no OCR. |
| PDF chat export | Unavailable: it shells out to `npx`, and the Python runtime has no Node.js. Markdown/JSON export work. |
| API-Football MCP tool | Disabled (`API_FOOTBALL_MCP_ENABLED=false`) for the same reason. Livescore MCP (remote SSE) works. |
| Traces page | SQLite in `/tmp`, so it's per instance and lost on recycle. Traces are partial. Needs a Postgres-backed trace store for durable traces. |
| Settings → API keys | Disabled (`403 SETTINGS_MANAGED_EXTERNALLY`). Keys are Vercel env vars. |
| Distributed tracing | Off (`TRACING_ENABLED=false`); no OTLP collector. |
| Live status stream | Each SSE response ends after `SSE_MAX_SECONDS` (240s), and the browser reconnects and resumes automatically. |

## Smoke test after deploy

1. Open the frontend, sign up / sign in.
2. Ask a question that hits the knowledge base. The match-status panel should
   step through stages live, and the answer should cite sources.
3. `GET https://<backend>/_svc/chat/health` without the header must return **404**.
