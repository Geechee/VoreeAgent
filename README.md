# VOREE Agent Framework v1.1

A production-ready AI agent backend powered by Claude. Submit a task and get an intelligent, quality-checked response — with semantic memory, document RAG, multi-agent collaboration, and extensible tool use.

![Python](https://img.shields.io/badge/python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![Tests](https://img.shields.io/badge/tests-120%20passing-brightgreen)
![Deploy](https://img.shields.io/badge/deploy-Railway-purple)
![License](https://img.shields.io/badge/license-MIT-green)

**Live:** [voree-app-production.up.railway.app](https://voree-app-production.up.railway.app)

## Features

### Core Pipeline
- **Workflow routing** — 4 built-in + custom workflows via API
- **Semantic memory** — Voyage AI embeddings + pgvector cosine similarity
- **Document RAG** — upload files, auto-chunk, embed, retrieve relevant context
- **Claude integration** — tool use with up to 5 rounds per request
- **Quality critic** — scores output 1-10, auto-retries if below 7

### 5 Task Execution Modes
- `POST /api/task` — synchronous (blocking)
- `POST /api/task/stream` — streaming via Server-Sent Events
- `POST /api/task/async` — background processing with polling
- `POST /api/chain` — multi-agent collaboration
- Cron-style scheduled tasks

### Multi-Agent Collaboration
- 5 agent roles: researcher, critic, synthesizer, creative, simplifier
- Chain agents sequentially — each builds on prior outputs
- Customizable role order per request

### Agent Personas
- 6 built-in personas: VOREE, Mentor, Architect, Strategist, Devil's Advocate, Creative
- Custom system prompts, tone, and expertise per persona
- Switch persona per task request

### Template Library
- 8 built-in templates: email draft, code review, meeting summary, blog post, pros/cons analysis, concept explainer, user stories, brainstorm
- Variable substitution with `{{placeholders}}`
- Templates can trigger multi-agent chains automatically

### Plugin System
- Register any HTTP endpoint as an agent tool
- Agent auto-discovers and calls plugins during task execution
- Supports GET/POST with custom headers and JSON Schema parameters

### Conversation Memory (Auto-Learning)
- Claude extracts key facts after every task and session
- Facts stored as searchable semantic memories
- Agent gets smarter over time from accumulated context

### Infrastructure
- **API key auth** with SHA-256 hashing
- **Per-key rate limiting** with usage tracking and analytics
- **Webhook notifications** with HMAC-SHA256 signing
- **Cron scheduler** for recurring automated tasks
- **Discord bot** integration (optional)
- **MCP server** — 8 tools for Claude Desktop and compatible clients
- **Input validation** — field-level constraints on all request models
- **Security headers** — X-Content-Type-Options, X-Frame-Options, X-XSS-Protection
- **Response caching** — TTL cache for expensive read endpoints
- **Connection pooling** — optimized PostgreSQL pool settings
- **120 tests** across 12 test files (unit + integration)

### Web Dashboard
7-tab admin interface at `/`:
- Tasks — submit, stream, view history
- Sessions — multi-turn chat
- Memories — store, search, delete
- Documents — upload, search chunks
- Analytics — stat cards, workflow/score charts, export
- API Keys — create, view usage, revoke
- Webhooks — add, test, delete

## Quick Start

### Prerequisites
- Docker & Docker Compose
- [Anthropic API key](https://console.anthropic.com)
- [Voyage AI API key](https://dashboard.voyageai.com)

### Run Locally

```bash
git clone https://github.com/Geechee/VoreeAgent.git
cd VoreeAgent

cp .env.example .env
# Edit .env with your API keys

docker compose up -d
curl http://localhost:8000/health
```

### Bootstrap Your First API Key

```bash
curl -X POST http://localhost:8000/api/keys/bootstrap \
  -H "Content-Type: application/json" \
  -d '{"name": "admin"}'
```

### Run a Task

```bash
curl -X POST http://localhost:8000/api/task \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"task": "Research the top 3 benefits of PostgreSQL"}'
```

### Use a Persona

```bash
curl -X POST http://localhost:8000/api/task \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"task": "Should we add Redis caching?", "persona": "architect"}'
```

### Run a Multi-Agent Chain

```bash
curl -X POST http://localhost:8000/api/chain \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"task": "Analyze microservices vs monoliths", "roles": ["researcher", "critic", "synthesizer"]}'
```

### Open the Dashboard

Visit [http://localhost:8000](http://localhost:8000) and paste your API key in the header.

### API Documentation

- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

## API Reference (58 endpoints)

<details>
<summary>Click to expand full endpoint list</summary>

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

### Personas
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/personas` | List personas |
| POST | `/api/personas` | Create custom persona |
| DELETE | `/api/personas/{name}` | Delete persona |

### Templates
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/templates` | List templates |
| GET | `/api/templates/categories` | List categories |
| POST | `/api/templates` | Create template |
| POST | `/api/templates/{name}/run` | Run template |
| DELETE | `/api/templates/{name}` | Delete template |

### Sessions
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/sessions` | Start conversation |
| POST | `/api/sessions/{id}/reply` | Send follow-up |
| POST | `/api/sessions/{id}/extract` | Extract facts |
| GET | `/api/sessions` | List sessions |
| GET | `/api/sessions/{id}` | Session detail |

### Memory
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/memories` | List memories |
| GET | `/api/memories/auto` | List auto-extracted facts |
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
| POST | `/api/plugins` | Register tool |
| GET | `/api/plugins` | List plugins |
| PUT | `/api/plugins/{name}` | Update plugin |
| DELETE | `/api/plugins/{name}` | Delete plugin |

### Workflows
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/workflows` | List all |
| POST | `/api/workflows` | Create custom |
| PUT | `/api/workflows/{name}` | Update |
| DELETE | `/api/workflows/{name}` | Delete |

### Schedules
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/schedules` | Create |
| GET | `/api/schedules` | List |
| PUT | `/api/schedules/{id}` | Update |
| DELETE | `/api/schedules/{id}` | Delete |
| POST | `/api/schedules/{id}/run` | Trigger now |

### Webhooks
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/webhooks` | Register |
| GET | `/api/webhooks` | List |
| PUT | `/api/webhooks/{id}` | Update |
| DELETE | `/api/webhooks/{id}` | Delete |
| POST | `/api/webhooks/{id}/test` | Test delivery |

### API Keys & Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/keys/bootstrap` | Create first key |
| POST | `/api/keys` | Create key |
| GET | `/api/keys` | List keys |
| DELETE | `/api/keys/{id}` | Revoke key |
| GET | `/api/keys/{id}/usage` | Usage stats |

### Analytics & Export
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/stats` | Dashboard metrics |
| GET | `/api/export/tasks` | Export (JSON/CSV) |
| GET | `/api/export/memories` | Export (JSON/CSV) |

### System
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/docs` | Swagger UI |
| GET | `/redoc` | ReDoc |
| GET | `/` | Web dashboard |

</details>

## MCP Server

Connect VOREE to Claude Desktop as an MCP tool provider. Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "voree": {
      "command": "docker",
      "args": ["compose", "run", "--rm", "app", "python", "mcp_server.py"],
      "cwd": "/path/to/VoreeAgent"
    }
  }
}
```

8 tools: `voree_task`, `voree_chain`, `voree_remember`, `voree_recall`, `voree_search_docs`, `voree_template`, `voree_list_templates`, `voree_list_roles`.

## Tech Stack

- **Python 3.12** + **FastAPI** — async web framework
- **PostgreSQL** + **pgvector** — relational DB with vector similarity search
- **Voyage AI** — text embeddings (voyage-3.5, 1024 dimensions)
- **Anthropic Claude** — reasoning and tool use
- **Docker Compose** — local development
- **Railway** — cloud deployment
- **GitHub Actions** — CI/CD

## Testing

```bash
# Unit tests (no external services needed)
docker compose run --rm app python -m pytest tests/ -v --ignore=tests/test_integration.py

# Full suite including integration tests (requires database)
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
Request → Auth + Rate Limit → Workflow Router → Memory Retrieval → Document RAG
    → Agent Core (Claude + Tools/Plugins) → Quality Critic (retry if <7)
    → Auto-Memory Extraction → Webhook Notify → Save → Response
```

## License

MIT
