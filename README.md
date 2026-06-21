# VOREE Agent Framework v1.1

A production-ready AI agent backend powered by Claude. Submit a task and get an intelligent, quality-checked response — with semantic memory, document RAG, multi-agent collaboration, and extensible tool use.

![Python](https://img.shields.io/badge/python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![Tests](https://img.shields.io/badge/tests-35%20passing-brightgreen)
![Deploy](https://img.shields.io/badge/deploy-Railway-purple)

## Features

**Core Pipeline**
- Workflow routing — 4 built-in + custom workflows via API
- Semantic memory — Voyage AI embeddings + pgvector cosine similarity
- Document RAG — upload files, auto-chunk, embed, retrieve relevant context
- Claude integration — tool use with up to 5 rounds per request
- Quality critic — scores output 1-10, auto-retries if below 7

**5 Task Execution Modes**
- `POST /api/task` — synchronous (blocking)
- `POST /api/task/stream` — streaming via Server-Sent Events
- `POST /api/task/async` — background processing with polling
- `POST /api/chain` — multi-agent collaboration (researcher → critic → synthesizer)
- `POST /api/schedules` — cron-style recurring tasks

**Infrastructure**
- API key auth with SHA-256 hashing
- Per-key rate limiting + usage tracking
- Webhook notifications with HMAC-SHA256 signing
- Plugin system — register any HTTP endpoint as an agent tool
- Analytics dashboard + CSV/JSON export
- Web admin dashboard with 7 tabs

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Anthropic API key ([console.anthropic.com](https://console.anthropic.com))
- Voyage AI API key ([dashboard.voyageai.com](https://dashboard.voyageai.com))

### Run Locally

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/VoreeAgent.git
cd VoreeAgent

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Start services
docker compose up -d

# Verify
curl http://localhost:8000/health
```

### Bootstrap Your First API Key

```bash
curl -X POST http://localhost:8000/api/keys/bootstrap \
  -H "Content-Type: application/json" \
  -d '{"name": "admin"}'
```

Save the returned key — it's only shown once.

### Run a Task

```bash
curl -X POST http://localhost:8000/api/task \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"task": "Research the top 3 benefits of PostgreSQL"}'
```

### Open the Dashboard

Visit [http://localhost:8000](http://localhost:8000) and paste your API key in the header field.

## API Reference

### Tasks
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/task` | Run task (sync) |
| POST | `/api/task/stream` | Run task (streaming SSE) |
| POST | `/api/task/async` | Run task (background) |
| GET | `/api/task/async/{id}` | Poll async task status |
| GET | `/api/tasks` | List task history |
| GET | `/api/tasks/{id}` | Task detail + critique |

### Multi-Agent Chains
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chain` | Run agent chain |
| GET | `/api/chain/roles` | List available roles |

### Sessions
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/sessions` | Start conversation |
| POST | `/api/sessions/{id}/reply` | Send follow-up |
| GET | `/api/sessions` | List sessions |
| GET | `/api/sessions/{id}` | Session detail |

### Memory
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/memories` | List memories |
| POST | `/api/memories` | Store memory |
| POST | `/api/memories/search` | Semantic search |
| DELETE | `/api/memories/{id}` | Delete memory |

### Documents (RAG)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/documents` | Upload + embed |
| GET | `/api/documents` | List documents |
| POST | `/api/documents/search` | Search chunks |
| DELETE | `/api/documents/{id}` | Delete document |

### Plugins
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/plugins` | Register custom tool |
| GET | `/api/plugins` | List plugins |
| PUT | `/api/plugins/{name}` | Update plugin |
| DELETE | `/api/plugins/{name}` | Delete plugin |

### Workflows
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/workflows` | List all workflows |
| POST | `/api/workflows` | Create custom workflow |
| PUT | `/api/workflows/{name}` | Update workflow |
| DELETE | `/api/workflows/{name}` | Delete workflow |

### Schedules
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/schedules` | Create schedule |
| GET | `/api/schedules` | List schedules |
| PUT | `/api/schedules/{id}` | Update schedule |
| DELETE | `/api/schedules/{id}` | Delete schedule |
| POST | `/api/schedules/{id}/run` | Trigger manually |

### Webhooks
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/webhooks` | Register webhook |
| GET | `/api/webhooks` | List webhooks |
| PUT | `/api/webhooks/{id}` | Update webhook |
| DELETE | `/api/webhooks/{id}` | Delete webhook |
| POST | `/api/webhooks/{id}/test` | Test delivery |

### API Keys & Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/keys/bootstrap` | Create first key |
| POST | `/api/keys` | Create additional key |
| GET | `/api/keys` | List keys |
| DELETE | `/api/keys/{id}` | Revoke key |
| GET | `/api/keys/{id}/usage` | Usage stats |

### Analytics
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/stats` | Dashboard metrics |
| GET | `/api/export/tasks` | Export tasks (JSON/CSV) |
| GET | `/api/export/memories` | Export memories (JSON/CSV) |

## Tech Stack

- **Python 3.12** + **FastAPI** — async web framework
- **PostgreSQL** + **pgvector** — relational DB with vector similarity search
- **Voyage AI** — text embeddings (voyage-3.5, 1024 dimensions)
- **Anthropic Claude** — reasoning and tool use
- **Docker Compose** — local development
- **Railway** — cloud deployment

## Testing

```bash
docker compose run --rm app python -m pytest tests/ -v
```

## Deploy to Railway

```bash
brew install railway
railway login
railway init --name voree-agent
railway add --database postgres
railway variables set ANTHROPIC_API_KEY=... VOYAGE_API_KEY=... EMBEDDING_MODEL=voyage-3.5 EMBEDDING_DIM=1024 CLAUDE_MODEL=claude-sonnet-4-6
railway up
railway domain
```

## Architecture

```
Request → Workflow Router → Memory Retrieval → Document RAG
    → Agent Core (Claude + Tools/Plugins) → Quality Critic
    → Save Result + Memory → Webhook Notify → Response
```

## License

MIT
