# FutBot microservices

## Phase 7 (active)

| Service | Port | Run |
|---------|------|-----|
| gateway | 8000 | `uvicorn services.gateway.main:app --port 8000` |
| auth | 8081 | `uvicorn services.auth.main:app --port 8081` |
| chat | 8082 | `uvicorn services.chat.main:app --port 8082` |
| project | 8083 | `uvicorn services.project.main:app --port 8083` |
| rag-orchestrator | 8084 | `uvicorn services.rag_orchestrator.main:app --port 8084` |
| retrieval | 8085 | `uvicorn services.retrieval.main:app --port 8085` |
| ingestion | 8086 | `uvicorn services.ingestion.main:app --port 8086` |
| llm-gateway | 8087 | `uvicorn services.llm_gateway.main:app --port 8087` |
| tools | 8088 | `uvicorn services.tools.main:app --port 8088` |
| observability | 8090 | `uvicorn services.observability.main:app --port 8090` |

```bash
pip install -e packages/futbot-common
pip install -r requirements.txt

docker compose -f docker-compose.services.yml up -d --build
alembic upgrade head
```

Gateway routes: `/auth/*`, `/chats/*`, `/projects/*`, `/traces/*`, `/tools` (catalog proxy). `/ws/pipeline` relays to orchestrator. `/llm/*`, `/retrieve/*`, `/ingest/*`, `/pipeline/*`, and `/tools/execute` are **internal only** (`501` on public gateway).

Chat RAG: user `POST /chats/{id}/messages` with optional `web_search_enabled` → internal `POST /pipeline/run` on orchestrator; assistant reply + `citations_json` + `tool_notice` persisted.

Orchestrator: LangGraph pipeline (`SIMPLE | KNOWLEDGE | TOOL`), `POST /pipeline/run`, `WS /ws/pipeline` on `:8084`. TOOL path runs tools and retrieval in parallel.

Tools: web search (Tavily→Serper), football MCP (LiveScore + API-Football), PDF export via `GET /chats/{id}/export?format=pdf`.

Observability: `GET /traces/{run_id}` on `:8090` (SQLite `trace_logs.db`, includes `tool_calls`).
