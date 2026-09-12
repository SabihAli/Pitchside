# Pitchside Architecture

This document details the end-to-end architecture of the current microservice-based Pitchside RAG (Retrieval-Augmented Generation) system. It supersedes the original monolith design (`src/`, now legacy — see [Legacy: Original Monolith Design](#legacy-original-monolith-design) at the bottom).

## System Overview

Pitchside is an intelligent, football-focused conversational agent split into independently deployable FastAPI microservices under `services/`, fronted by a single API gateway and a Next.js web client. The core reasoning pipeline is a LangGraph-orchestrated state machine that rewrites queries, classifies intent, retrieves context via hybrid search, drafts an answer, and fact-checks it before returning a response.

```
services/web (Next.js)
        │  same-origin /api, WebSockets for pipeline events
        ▼
services/gateway  ──► services/auth (JWT, 2FA, sessions)
        │              services/project (leagues / Ball Knowledge)
        │              services/chat (conversation CRUD, context)
        │              services/tools (web search, MCP: LiveScore/API-Football)
        │              services/observability (trace store)
        ▼
services/chat → pipeline_runner ──► services/rag_orchestrator (LangGraph)
                                          │
                                          ├─► services/llm_gateway (Groq/local providers)
                                          └─► services/retrieval (Qdrant dense + BM25 sparse + RRF)
                                                     │
                                          services/ingestion (extractors, chunking, relevance guard)
```

Shared code (JWT helpers, error/exception handling, logging/metrics/tracing config, common Pydantic models, middleware) lives in `packages/futbot-common` and is imported by every service.

`services/realtime` is currently a stub (`create_stub_app`) and not yet implemented.

---

## 1. Retrieval (`services/retrieval`)

Hybrid search combines:
1. **Dense retrieval (Qdrant)**: chunks are embedded (via `DefaultEmbeddingFunction`, `services/retrieval/embeddings.py`) and stored/queried in Qdrant (`services/retrieval/dense.py`, `config.py`).
2. **Sparse retrieval (BM25Okapi)**: exact lexical matches (`services/retrieval/bm25.py`), with title fields boosted at indexing time so articles matching query names score highly.
3. **Reciprocal Rank Fusion (RRF)**: results from Qdrant and BM25 are merged in `services/retrieval/rrf.py` (`score = 1 / (k + rank)`), so documents ranking highly in both lists bubble to the top.
4. **Scope filtering** (`services/retrieval/scope.py`): supports per-user/per-project ("Ball Knowledge") scoped retrieval alongside the global knowledge base, so the same engine serves both global football knowledge and a user's uploaded documents.

Ingestion into the retrieval store is handled by `services/ingestion` (extractors for PDF/image/OCR/text/spreadsheet, a chunking layer with smart/text/table/pdf/image-specific chunkers, and a relevance guard that filters out non-football content) plus `scripts/seed_global_kb.py` for bulk-seeding the global KB from `data/final-articles.csv`.

---

## 2. LLM Orchestration Workflow (`services/rag_orchestrator`, LangGraph)

The reasoning loop is a `StateGraph` (`services/rag_orchestrator/graph.py`) with the following nodes and edges:

1. **Compressor** — compresses/summarizes prior conversation context before the turn proceeds (supports long chat histories without blowing the context window).
2. **Rewriter** — rewrites the user's raw query (with history) into a standalone, self-contained query.
3. **Orchestrator (classifier)** — routes the rewritten query as `SIMPLE` (small talk) vs. requiring knowledge/tools.
4. **Simple Responder** — replies directly for `SIMPLE` queries, bypassing retrieval, → `END`.
5. **External Context** — for queries needing live/external data (e.g. live match events, web search via `services/tools`), fetches that context before drafting.
6. **Retriever** — for knowledge queries, runs the hybrid retrieval described above.
7. **Drafter** — generates a draft answer strictly from the retrieved/external context.
8. **Judge** — fact-checks the draft against the retrieved context; returns `PASS`/`FAIL`.
   - **PASS** → answer returned to the user.
   - **FAIL** → loops back for another retrieval/draft attempt (bounded retries) via a conditional edge.

All LLM calls are routed through `services/llm_gateway`, which abstracts the underlying provider (Groq or a local model), centralizes prompt loading, and tracks token budget usage per call.

Pipeline progress is streamed to the frontend over WebSockets/SSE via `services/rag_orchestrator`'s `pipeline_events` module, and every run is invoked through `services/chat`'s `pipeline_runner`, which owns the conversation/turn lifecycle.

---

## 3. Observability (`services/observability`)

Each pipeline run and its LLM calls, retrieval events, and retry loops are traced and stored via `services/observability`, exposed through `/traces/{run_id}`. In deployment, this is backed by the full OpenTelemetry stack in `k8s/observability/` (OTel Collector → Jaeger/Loki, Prometheus rules + ServiceMonitors, Grafana dashboards) rather than the old flat SQLite trace DB — see the Legacy section below for how this worked in the monolith.

---

## 4. API & Frontend

- **Gateway (`services/gateway`, FastAPI)**: single API entry point, routing to auth, chat, project/knowledge, tools, observability, and the orchestrator pipeline; also owns settings/API-key routes.
- **Frontend (`services/web`, Next.js App Router)**: the Pitchside UI (auth, chat, knowledge/"Ball Knowledge", leagues, live events, settings, help). Same-origin `/api` calls; pipeline updates via WebSockets. See `docs/UI_REQUIREMENTS.md` for the living UI spec and `docs/design-reference/` for the original design mocks (`pitchai-analyst.html`, `auth-reference.html`, `theme.css`).
- **State**: chats and account/project metadata persist in Postgres (per-service, via SQLAlchemy + Alembic migrations); auth sessions in Redis; files/objects in MinIO; pipeline traces in the observability store; retrieval in Qdrant + BM25.
- **Deployment**: Docker Compose (`docker-compose.services.yml` + `docker-compose.infra.yml` + `docker-compose.observability.yml`) for local/dev, and a full Kustomize k8s setup (`k8s/base`, `k8s/overlays/dev`, `k8s/observability`) for cluster deployment.

---

## Key Design Decisions

1. **Service-per-domain decomposition**: auth, chat, project, retrieval, ingestion, llm_gateway, rag_orchestrator, tools, observability, and gateway are independently deployable FastAPI services sharing only `packages/futbot-common`, replacing the original single-process monolith.
2. **Model specialization (multi-agent routing)**: rather than one large model for everything, the graph uses smaller/faster models for routing and rewriting and a stronger model as the strict judge, via `services/llm_gateway`'s provider abstraction — optimizing latency and cost.
3. **Hybrid retrieval + RRF**: combining dense (Qdrant) and sparse (BM25) retrieval catches both semantic and exact-match queries (player names, years, teams) better than either alone.
4. **Self-correction loop**: the Judge node catches hallucinations before the user sees them, retrying retrieval/drafting with a bounded number of attempts.
5. **Context compression**: the Compressor node keeps long-running conversations within the LLM context window without discarding relevant history outright.
6. **Scoped retrieval**: the same retrieval engine serves both the global knowledge base and per-user/per-project "Ball Knowledge" uploads via scope filtering, rather than maintaining separate retrieval stacks.

---

## Legacy: Original Monolith Design

The sections below describe `src/` — the original single-process prototype that predates the microservice split. **This code is no longer used or imported anywhere** (see `CODEBASE.md` for confirmation) and is kept only for historical reference; it should not be treated as a description of the current system.

- **Retrieval**: ChromaDB (`DefaultEmbeddingFunction`, all-MiniLM-L6-v2) for dense search + BM25Okapi for sparse, merged via RRF — the same overall technique later reimplemented against Qdrant in `services/retrieval`.
- **Orchestration**: a similar LangGraph state machine (Query Rewriter → Orchestrator Classifier → Simple Responder / Retriever → Draft Generator → Decision Judge), using named Qwen3 model sizes (0.8B router, 2B drafter/rewriter, 4B judge) hardcoded rather than provider-abstracted.
- **Logging**: a heavily normalized SQLite database (`trace_logs.db`, now deleted from the repo root — see `CODEBASE.md`) with `pipeline_runs`, `llm_calls`, `loop_iterations`, and `retrieval_events`/`retrieved_chunks` tables, written via thread-local connections opened per insert (`PipelineRunLogger`) to work around LangGraph's multi-threaded node execution.
- **`<think>` tag stripping**: Qwen3 models emit `<think>` reasoning blocks; these were stripped in `invoke_llm()` before showing the user the final answer, while raw reasoning was preserved in the DB for debugging. The current `services/llm_gateway` provider abstraction is expected to handle this per-provider going forward.
