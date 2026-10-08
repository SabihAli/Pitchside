# Deploying Pitchside on a VPS (Contabo)

The whole stack runs with Docker Compose on one server. The production overlay
`docker-compose.prod.yml` adds:

- **Caddy** on ports 80/443 with automatic HTTPS. It is the only published service.
- Real database and object-store passwords from `.env`.
- `restart: unless-stopped` on every service.
- Production flags: `ENVIRONMENT=production`, `DEBUG=false`, and
  `SETTINGS_API_KEYS_ENABLED=false` so end users can't read or change server API keys.

```
internet ──443──► caddy ──► web (Next.js :3000) ──/api/*──► gateway :8000 ──► services
                                                      (internal docker network only)
```

The browser only talks to the web app. `/api/*`, including the live pipeline
event stream (`/api/events/pipeline`, Server-Sent Events), is proxied to the
gateway inside the Docker network.

## 1. Server

Suggested size: **8 GB RAM / 4 vCPU or more**. The stack runs ~15 containers,
and retrieval loads a local embedding model. Ubuntu 22.04/24.04.

```bash
# Docker Engine + compose plugin
curl -fsSL https://get.docker.com | sh

# Firewall: SSH + HTTP(S) only
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw allow 443/udp && ufw enable
```

Docker's published ports bypass `ufw`. That's why the prod overlay publishes
nothing except Caddy. Don't add `ports:` to other services.

DNS: point an A record for your domain (e.g. `app.example.com`) at the server's IP
**before** first start, so Caddy can issue the certificate.

## 2. Configure

```bash
git clone <repo> /opt/pitchside && cd /opt/pitchside
cp .env.example .env
```

Edit `.env`:

| Variable | Value |
|----------|-------|
| `DOMAIN` | `app.example.com` (used by Caddy) |
| `POSTGRES_PASSWORD` | long random (`openssl rand -hex 24`) |
| `MINIO_ROOT_PASSWORD` | long random |
| `JWT_SECRET` | long random, different from the above |
| `ENVIRONMENT` / `DEBUG` | `production` / `false` |
| `LLM_PROVIDER`, `GROQ_API_KEY` | `groq` and the key |
| `TAVILY_API_KEY` / `SERPER_API_KEY`, `API_FOOTBALL_KEY` | as used today |
| `WEB_APP_URL` | `https://app.example.com` |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | OAuth app |
| `GOOGLE_REDIRECT_URI` | `https://app.example.com/api/auth/oauth/google/callback` (also register it in Google Cloud Console) |
| `SMTP_*` | needed for signup verification emails in production |

`POSTGRES_PASSWORD` / `MINIO_ROOT_PASSWORD` only take effect when their volumes
are first created. See step 3 if you restore existing volumes.

## 3. Bring over the existing data (knowledge base, users, chats)

The knowledge base lives in Docker volumes on the current machine. Copy them as-is:

| Volume | Contents |
|--------|----------|
| `rag_project_qdrant_data` | knowledge-base vectors |
| `rag_project_retrieval_data` | BM25 keyword index |
| `rag_project_minio_data` | uploaded files |
| `rag_project_postgres_data` | users, chats, projects |

On the **current** machine, with the stack stopped (`docker compose down`):

```bash
for v in qdrant_data retrieval_data minio_data postgres_data; do
  docker run --rm -v rag_project_$v:/data -v "$PWD":/backup alpine \
    tar czf /backup/$v.tgz -C /data .
done
scp *.tgz root@<server>:/opt/pitchside/
```

On the **server**:

```bash
cd /opt/pitchside
for v in qdrant_data retrieval_data minio_data postgres_data; do
  docker volume create rag_project_$v
  docker run --rm -v rag_project_$v:/data -v "$PWD":/backup alpine \
    tar xzf /backup/$v.tgz -C /data
done
```

The restored Postgres and MinIO volumes were created with the local defaults
(`futbot` / `futbotminio`). Start with those values in `.env`, then rotate:

```bash
dc exec postgres psql -U futbot -c "ALTER USER futbot PASSWORD '<new>';"
# then set POSTGRES_PASSWORD=<new> in .env and run: dc up -d
```

(For MinIO, the simplest route is a fresh `minio_data` volume with the new
password, then copying the bucket over with `mc mirror`.)

Fresh start instead (empty users/chats): skip the copy and seed the global
knowledge base from the CSV:
`dc --profile seed run --rm kb-seed` (needs `final-articles.csv` in the repo root).

## 4. Start

Always pass both files and the project name. `docker-compose.override.yml` is a
local-dev file and must **not** be applied on the server.

```bash
alias dc='docker compose -p rag_project -f docker-compose.yml -f docker-compose.prod.yml'
dc up -d --build
dc ps
```

Check:
- `https://app.example.com` loads and shows a valid certificate.
- Sign in, ask a question. The status panel steps through stages live, and the answer cites sources.
- From another machine, `nc -zv <server-ip> 5432` (and 6379, 6333, 8000, 9000) must **fail**.

## 5. Operations

**Update:** `git pull && dc up -d --build`

**Logs:** `dc logs -f gateway rag-orchestrator chat` (all services log JSON to stdout).

**Backups:** schedule nightly with cron, and copy off the server (e.g. Contabo
Object Storage or another host):

```bash
dc exec -T postgres pg_dump -U futbot futbot | gzip > /backups/pg-$(date +%F).sql.gz
for v in qdrant_data retrieval_data minio_data; do
  docker run --rm -v rag_project_$v:/data -v /backups:/backup alpine \
    tar czf /backup/$v-$(date +%F).tgz -C /data .
done
```

**Admin access** to internal tools (MinIO console, Postgres, Qdrant dashboard)
goes through an SSH tunnel, never public ports.

## Notes

- Live pipeline status uses Server-Sent Events. Caddy streams them without
  buffering. If you put another proxy in front (Cloudflare, nginx), disable
  response buffering for `/api/events/pipeline`.
- Distributed tracing exports to `otel-collector:4317`, which only exists if
  `docker-compose.observability.yml` is also started. Otherwise the export
  errors in logs are harmless.
- Settings → API keys is disabled in production (`403 SETTINGS_MANAGED_EXTERNALLY`).
  Change keys in `.env`, then `dc up -d`.
