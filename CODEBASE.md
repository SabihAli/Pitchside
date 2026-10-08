# CODEBASE.md — Pitchside (formerly FutBot) RAG Project

_Last audited: 2026-09-05. This document is a snapshot of the current state of the repository: what's built, what's stale, and what's outstanding. Regenerate/update it whenever a major phase lands._

## 1. What This Project Is

A football-focused conversational RAG agent, originally prototyped as a single-service monolith (`src/`) and later rebuilt as a microservice architecture (`services/`) with a Next.js frontend. Pipeline: **Query Rewriter → Orchestrator (classifier) → Hybrid Retriever (Qdrant + BM25 + RRF) → Draft Generator → Decision Judge**, with a loop-back/retry (max 3) on judge FAIL, orchestrated via LangGraph.

Product history, in order:
1. Monolithic prototype (`src/`) — PRD in `docs/football_rag_prd.md`, plan in `docs/PROJECT_PLAN.md`.
2. A round of monolith enhancements (`docs/ENHANCEMENTS.md`, `docs/IMPLEMENTATION_PLAN.md`) — snapshot context, multi-format ingestion, Groq provider, smart chunking, SSE streaming.
3. Full microservice refactor, phases 0–7 (foundations → auth/gateway → chat/project → llm gateway → phase4 → phase6 → mcp/tools), landing in `services/`.
4. Phase 8 (`docs/PHASE_8_PLAN.md`) — Next.js web frontend (`services/web`) + companion APIs (chat merge, "Ball Knowledge" user-scoped RAG, settings/API keys, 2FA, live events). Mostly verified live as of 2026-08-17 per that doc.
5. `db48608` "refactor: major architecture refactor" — current HEAD.

## 2. Current Architecture — services/

| Service | Purpose | Status |
|---|---|---|
| `services/auth` | Register/login, JWT, 2FA (pyotp), email verification, Redis sessions, Alembic migrations (5 versions) | ✅ Implemented, migrated |
| `services/chat` | Conversation CRUD, context building/usage tracking, pipeline_runner → orchestrator | ✅ Implemented (chat's own `alembic/versions` appears empty — verify whether it truly needs migrations or inherits schema elsewhere) |
| `services/gateway` | API gateway: routing, middleware, settings/API-key routes | ✅ Implemented, best test coverage (7 test files) |
| `services/ingestion` | File ingestion: extractors (pdf/image/OCR/text/spreadsheet), chunking (smart/text/table/pdf/image), relevance guard, background worker | ✅ Implemented, most heavily tested (13 test files); mirrors `docs/ENHANCEMENTS.md` design closely |
| `services/llm_gateway` | LLM provider abstraction (Groq/local), prompt loading, token budget tracking | ✅ Implemented |
| `services/observability` | Trace store, `/traces/{run_id}` | ✅ Implemented (minimal) |
| `services/project` | "Leagues"/Projects CRUD, Ball Knowledge routes, ingestion trigger | ✅ Implemented |
| `services/rag_orchestrator` | LangGraph pipeline orchestration, tool_client, retrieval_scope, SSE/WS pipeline events | ✅ Implemented (test dir is named `tests/orchestrator`, not `tests/rag_orchestrator` — naming mismatch only) |
| `services/realtime` | Real-time service | 🟥 **STUB ONLY** — `main.py` is `create_stub_app("realtime")`, 2 lines. No Dockerfile, no tests. Not implemented. |
| `services/retrieval` | Hybrid retrieval: BM25, dense, RRF, embeddings, scope filtering, migrate.py | ✅ Implemented, well-tested |
| `services/tools` | Tool/MCP registry: web_search (Tavily/Serper), MCP bridge (LiveScore/API-Football), live_events | ✅ Implemented |
| `services/web` | Next.js App Router frontend (auth, chat, knowledge, leagues, live-events, settings, help) | ✅ Implemented per Phase 8 plan; no visible test suite under root `tests/` (frontend tests, if any, live inside `services/web` itself — unverified) |

`packages/futbot-common` — shared library (JWT, error/exception handling, logging/metrics/tracing config, common models, middleware). Actively used across services, has its own tests. **Not stale.**

## 2a. Cleanup Performed (2026-09-05)

The root-level clutter and stale-doc issues identified below were addressed:
- Deleted (untracked/gitignored, safe to remove from disk): duplicate root `final-articles.csv` (43MB, byte-identical to `data/final-articles.csv`), `trace_logs.db`, `.coverage`, the stray `alembic.ini;C` directory.
- Removed from git (`git rm`): `auth ss.png`, `dashboard.png`, `projects claude.png` (unreferenced screenshots), `seed_global_kb.log`, `seed_global_kb_resume.log` (runtime logs).
- Relocated (`git mv`) into `docs/design-reference/`: `auth-reference.html`, `pitchai-analyst.html`, `theme.css` — these **are** actively referenced as UI design sources of truth in `docs/PHASE_8_PLAN.md` and `docs/UI_REQUIREMENTS.md`, so they were moved rather than deleted; all references in those docs were updated to the new path.
- Deleted root `skills/` directory (personal Claude Code skill defs + stray phone photos, already gitignored/untracked, unrelated to this product).
- Fixed `Makefile`'s `GLOBAL_KB_CSV` to point at `data/final-articles.csv` instead of the now-removed root duplicate.
- Added `*.log` and `alembic.ini;*` to `.gitignore` to stop these artifacts from recurring.
- Rewrote `docs/ARCHITECTURE.md` to describe the actual current `services/` microservice architecture (it previously described the dead `src/` monolith in present tense); the old monolith description was preserved as a clearly-labeled "Legacy" section at the bottom for historical reference.
- Added "historical/archived" callouts (with pointers to the current docs) to the tops of `docs/football_rag_prd.md`, `docs/PROJECT_PLAN.md`, `docs/ENHANCEMENTS.md`, and `docs/IMPLEMENTATION_PLAN.md` rather than rewriting them — their content is only useful as historical design rationale, so a full rewrite wasn't warranted.
- **Correction to the original audit**: `docs/README.md`'s reference to `docs/UI_REQUIREMENTS.md` is *not* a dead link — that file exists (25KB, last updated 2026-08-17) and is in fact the most detailed living UI spec in the repo. The original audit was wrong on this point.

**Not touched, still outstanding** (flagged, not executed — bigger/riskier calls the user should confirm separately):
- `src/` monolith + its 6 orphaned legacy tests are still present. Safe to delete once confirmed nothing depends on them, but this wasn't part of the requested cleanup pass.
- `services/realtime` is still an unimplemented stub.

## 3. Legacy / Stale Code

### `src/` — dead monolith
`src/api.py`, `config.py`, `context.py`, `data_layer.py`, `db_logger.py`, `ingestion/`, `prompts.txt` is the **original pre-microservices prototype**. Confirmed:
- **Zero imports** of `src.*` anywhere under `services/`.
- Only referenced by 6 orphaned top-level test files: `tests/test_api.py`, `tests/test_context.py`, `tests/test_data_layer.py`, `tests/ingestion/test_ingestion_db.py`, `tests/ingestion/test_monolith_ingest.py` (filename literally says "monolith"), and likely `tests/test_graph.py`.
- Its functionality has been superseded by `services/rag_orchestrator`, `services/ingestion`, `services/llm_gateway`, `services/observability`.

**Recommendation:** delete `src/` and its 6 orphaned tests once confirmed nothing in CI/Docker/deploy still references it.

### Stale/superseded docs — ✅ addressed (see §2a)
- `docs/football_rag_prd.md` — pre-build PRD; explicitly lists "no auth", "no multi-user" as non-goals that were later built anyway. **Now marked historical** with a callout pointing to current docs; left otherwise unchanged since its only value is historical.
- `docs/ENHANCEMENTS.md` and `docs/IMPLEMENTATION_PLAN.md` — both explicitly target `src/` (the dead monolith). **Now marked historical/archived** with callouts; not rewritten since their content is only useful as design rationale.
- `docs/ARCHITECTURE.md` — previously described the old monolith design (ChromaDB, SQLite `trace_logs.db`, thread-local logging) in present tense. **Rewritten** to describe the actual current `services/` microservice architecture, with the old design preserved as a labeled "Legacy" section.
- `docs/PROJECT_PLAN.md` — checkbox phase tracker whose checked/unchecked state doesn't match reality. **Now marked historical/stale** with a callout pointing to this file and `PHASE_8_PLAN.md` for current status; checkboxes themselves left as-is (not worth reconciling retroactively).
- `docs/README.md`'s reference to `docs/UI_REQUIREMENTS.md` — **not actually a dead link**; the original audit was wrong, the file exists and is current. No change needed.
- `docs/PHASE_8_PLAN.md` and `docs/UI_REQUIREMENTS.md` remain the **most current and trustworthy** planning/spec docs; their design-file references were updated to the new `docs/design-reference/` path.

### Root-level clutter (recommend cleanup)
| Item | Verdict |
|---|---|
| `final-articles.csv` (43MB, root) | ✅ **Deleted.** Duplicate of `data/final-articles.csv`; `Makefile`'s `GLOBAL_KB_CSV` now points at `data/final-articles.csv`. |
| `trace_logs.db` | ✅ **Deleted.** Was a committed SQLite runtime artifact from the legacy monolith. |
| `.coverage` | ✅ **Deleted.** Pytest-cov artifact; already gitignored. |
| `seed_global_kb.log`, `seed_global_kb_resume.log` | ✅ **Deleted & un-tracked** (`git rm`); `*.log` added to `.gitignore`. |
| `alembic.ini;C` | ✅ **Deleted.** Was an accidental directory from a mistyped shell command; `alembic.ini;*` added to `.gitignore`. Real config is the sibling `alembic.ini`. |
| `auth ss.png`, `dashboard.png`, `projects claude.png` | ✅ **Deleted & un-tracked** (`git rm`) — unreferenced screenshots. |
| `auth-reference.html`, `pitchai-analyst.html`, `theme.css` | ✅ **Relocated** (`git mv`) to `docs/design-reference/` — kept because they're actively referenced as UI design sources of truth in `docs/PHASE_8_PLAN.md` / `docs/UI_REQUIREMENTS.md`; both docs' references updated to the new path. |
| `skills/` (root, distinct from `.agents/skills`) | ✅ **Deleted.** Was already gitignored/untracked; personal Claude Code skill defs + stray personal photos, unrelated to the RAG product. |

## 4. Deployment / Infra

- `docker-compose.yml` is just an `include:` shim → `docker-compose.services.yml` (full stack: auth, gateway, observability, chat, retrieval, tools, ingestion, project, web + minio/postgres/redis/qdrant).
- `docker-compose.infra.yml` — infra-only (for local dev without full app stack).
- `docker-compose.observability.yml` — separate observability stack.
- `k8s/base/` — Kustomize manifests for **all** core services including `llm-gateway` and `rag-orchestrator` (more complete than the services-compose file, which should be double-checked for parity).
- `k8s/observability/` — Loki, OTel→Jaeger, Prometheus rules/ServiceMonitors — a fairly mature setup.
- `k8s/overlays/dev`, `k8s/kind-cluster.yaml` — local kind cluster tooling.
- `infra/` (root) — nearly empty (`.env.example` only), largely vestigial next to `docker-compose.infra.yml`.

Overall the deployment setup (Compose + Kustomize + observability stack) is more mature than the stale PRD/plan docs would suggest.

## 5. Tests

- Every implemented service has a matching `tests/<service>` directory **except**:
  - `services/realtime` — no tests (consistent with it being an unbuilt stub).
  - `services/web` — no Python test dir under root `tests/` (frontend may have its own JS/TS tests inside `services/web`, unverified here).
- `tests/orchestrator/` tests `services/rag_orchestrator` — directory naming mismatch, not a functional gap.
- Orphaned legacy tests at `tests/` root (`test_api.py`, `test_context.py`, `test_data_layer.py`, `test_graph.py`) test the dead `src/` monolith and should be deleted alongside it. `test_correlation_middleware.py` and `test_jwt_tokens.py` actually test `packages/futbot-common` and are still valid.
- No TODO/FIXME/XXX markers found anywhere in `services/` or `src/` — either unusually clean code or such markers were deliberately scrubbed.
- No per-service requirements files; Docker images install the root `requirements-docker.txt` (~45 packages — FastAPI/SQLAlchemy/alembic, LangGraph/LangChain, ChromaDB, rank-bm25, Groq, OpenTelemetry, MCP, Qdrant client, ingestion libs). `packages/futbot-common` is the only package with its own `pyproject.toml`, installed editable.

## 6. Outstanding / To-Do (from PHASE_8_PLAN.md success criteria, still unchecked)

- Anonymous chat + merge-on-login flow — implemented but **not yet exercised live**.
- Settings API keys persistence — implemented but **not yet smoke-tested live**.

## 7. Summary Verdict

- **Done and solid:** auth, gateway, ingestion, llm_gateway, project, rag_orchestrator, retrieval, tools, web (per Phase 8), shared `futbot-common` lib, k8s/observability deployment story.
- **Stub / not built:** `services/realtime`.
- **Dead code still to remove (not yet executed, needs a separate confirm):** `src/` monolith + its 6 orphaned tests.
- **Root clutter:** ✅ cleaned up — see §2a.
- **Docs:** ✅ `docs/ARCHITECTURE.md` rewritten; `docs/football_rag_prd.md`, `docs/PROJECT_PLAN.md`, `docs/ENHANCEMENTS.md`, `docs/IMPLEMENTATION_PLAN.md` marked historical/archived; `docs/README.md`'s `UI_REQUIREMENTS.md` link was confirmed valid (no fix needed).
- **Live sources of truth:** `docs/PHASE_8_PLAN.md`, `docs/UI_REQUIREMENTS.md`, and this file (`CODEBASE.md`) for current status; `docs/ARCHITECTURE.md` for current system design.
