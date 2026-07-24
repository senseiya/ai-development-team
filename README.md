# AI Development Team

Plataforma multiagente para desarrollo de software automatizado. Un orquestador coordina cinco agentes de IA especializados (Planner, Coder, Tester, Reviewer, Documentation) que colaboran para desarrollar software automáticamente desde solicitudes en lenguaje natural.

## Características

- **5 Agentes de IA**: Planner, Coder, Tester, Reviewer, Documentation
- **Model Router automático**: Fallback chain con múltiples proveedores (OpenRouter, Ollama)
- **HITL (Human-in-the-loop)**: Pausa automática para aprobación en findings críticos
- **MCP (Model Context Protocol)**: 11 herramientas expuestas para Claude Desktop, Cursor, etc.
- **Observabilidad**: Prometheus metrics, structured logging, health checks
- **Cost Optimization**: Budget enforcement por run, LLM response cache (Redis)
- **Production-ready**: Rate limiting, Docker multi-stage, CI/CD, auto-migrations

## Requisitos Previos

- Docker Desktop instalado y ejecutándose
- Python 3.11+
- Cuenta en OpenRouter con API key (modelo gratuito)

## Inicio Rápido

### 1. Clonar el repositorio

```bash
git clone https://github.com/senseiya/ai-development-team.git
cd ai-development-team
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
```

Editar `.env` y agregar tu API key de OpenRouter:
```
OPENROUTER_API_KEY=tu-api-key-aqui
```

### 3. Levantar servicios (desarrollo)

```bash
docker-compose up -d
```

Esto iniciará:
- PostgreSQL (puerto 5432)
- Redis (puerto 6379)
- Ollama (puerto 11434)
- API (puerto 8000, con hot-reload)

### 4. Verificar funcionamiento

```bash
# Health check
curl http://localhost:8000/health

# Crear una tarea
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "X-API-Key: change-me-in-production" \
  -H "Content-Type: application/json" \
  -d '{"description": "Create a Python function that calculates fibonacci numbers"}'

# Consultar el run (usar el ID de la respuesta anterior)
curl http://localhost:8000/api/v1/runs/{run-id} \
  -H "X-API-Key: change-me-in-production"
```

### Despliegue en Producción

```bash
docker compose -f docker-compose.prod.yml up -d
```

Ver `docker-compose.prod.yml` para la configuración completa con resource limits, networks, y secrets.

## Desarrollo Local

### Instalar dependencias (sin Docker)

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

pip install -e ".[dev]"
```

### Ejecutar tests

```bash
# Todos los tests
pytest

# Solo tests unitarios
pytest tests/unit/ -v

# Con cobertura
pytest --cov=core --cov=apps --cov-report=html
```

### Linting y type checking

```bash
ruff format .
ruff check .
mypy .
```

## Estructura del Proyecto

```
ai-development-team/
├── apps/
│   └── api/
│       ├── main.py              # FastAPI app (lifespan, middleware, routers)
│       ├── deps.py              # Auth + DB dependencies
│       └── routers/
│           ├── auth.py          # JWT: register, login, refresh, logout
│           ├── tasks.py         # POST /tasks — run agent pipeline
│           ├── runs.py          # GET /runs/{id}, POST /approve, GET /status
│           ├── costs.py         # GET /costs/summary, GET /costs/runs/{id}
│           ├── models.py        # Admin: model profile CRUD
│           └── ws.py            # WebSocket + Redis pub-sub
├── core/
│   ├── agents/
│   │   ├── base.py             # BaseAgent ABC (call_llm, cache, budget)
│   │   ├── planner.py          # PlannerAgent (REASONING)
│   │   ├── coder.py            # CoderAgent (CODE_GENERATION)
│   │   ├── tester.py           # TesterAgent (CODE_REVIEW)
│   │   ├── reviewer.py         # ReviewerAgent (CODE_REVIEW)
│   │   └── documentation.py    # DocumentationAgent (SUMMARIZATION)
│   ├── orchestrator/
│   │   ├── state.py            # AgentState TypedDict + dataclasses
│   │   ├── graph.py            # LangGraph StateGraph (instrumented)
│   │   └── checkpointer.py     # PostgresCheckpointer
│   ├── router/
│   │   ├── model_router.py     # Automatic ModelRouter with fallback
│   │   ├── registry.py         # SEED_MODELS, seed_model_profiles()
│   │   └── providers/
│   │       ├── base.py         # LLMProvider Protocol
│   │       ├── openrouter.py   # OpenRouterProvider
│   │       └── ollama.py       # OllamaProvider
│   ├── tools/
│   │   ├── mcp_server.py       # MCP server (11 tools)
│   │   ├── mcp_client.py       # In-process MCP client
│   │   ├── filesystem_tool.py  # File read/write/list/diff
│   │   ├── sandbox_exec_tool.py# Docker sandbox execution
│   │   ├── github_tool.py      # GitHub API (branch, commit, PR)
│   │   └── db_tool.py          # Read-only SQL queries
│   ├── auth/
│   │   ├── tokens.py           # JWT create/decode
│   │   └── blacklist.py        # Redis token blacklist
│   ├── observability/
│   │   ├── logging.py          # Structured JSON logging (structlog)
│   │   ├── metrics.py          # Prometheus metrics (12 metrics)
│   │   ├── middleware.py        # HTTP metrics middleware
│   │   ├── health.py           # /health, /health/live, /health/ready
│   │   └── tracing.py          # AgentTracer + RunTracer
│   ├── cost/
│   │   ├── tracker.py          # Cost calculation (tokens × pricing)
│   │   ├── budget.py           # Budget enforcement per run
│   │   └── cache.py            # Redis LLM response cache
│   ├── middleware/
│   │   └── rate_limit.py       # SlowAPI rate limiter
│   ├── db/
│   │   └── migrate.py          # Auto Alembic migration on startup
│   ├── config.py               # Pydantic Settings
│   └── schemas.py              # Shared Pydantic schemas
├── db/
│   ├── models.py               # Run, ModelProfile, RunCheckpoint, User, ApiKey, FileChange
│   ├── session.py              # Async DB session
│   └── migrations/             # Alembic migrations
├── tests/
│   ├── unit/                   # 184 tests (all passing)
│   └── integration/            # Ollama integration tests
├── infra/
│   ├── docker/Dockerfile.api   # Multi-stage, non-root, health check
│   └── prometheus/             # Prometheus scrape config
├── .github/workflows/ci.yml   # GitHub Actions CI (lint + test)
├── docker-compose.yml          # Development
├── docker-compose.prod.yml     # Production
└── pyproject.toml              # Dependencies + tool config
```

## API Endpoints

### Health & Observability

| Method | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/health` | System health (checks PG, Redis, Ollama) |
| GET | `/health/live` | Kubernetes liveness probe |
| GET | `/health/ready` | Kubernetes readiness probe |
| GET | `/metrics` | Prometheus metrics |

### Auth (rate limited: 10/min)

| Method | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register new user |
| POST | `/api/v1/auth/login` | Login → JWT tokens |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| POST | `/api/v1/auth/logout` | Blacklist refresh token |

### Tasks (rate limited: 5/min)

| Method | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/v1/tasks` | Create and execute a development task |

### Runs

| Method | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/runs/{id}` | Get run details |
| GET | `/api/v1/runs/{id}/status` | Per-agent timing breakdown |
| POST | `/api/v1/runs/{id}/approve` | Approve/reject HITL pause |

### Costs

| Method | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/costs/summary` | Aggregated token/cost summary |
| GET | `/api/v1/costs/runs/{id}` | Cost breakdown for a run |

### WebSocket

| Protocol | Endpoint | Descripción |
|----------|----------|-------------|
| WS | `/ws/runs/{run_id}` | Real-time run progress (Redis pub-sub) |

## Variables de Entorno

| Variable | Descripción | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection URL | `postgresql+asyncpg://ai_team:ai_team_secret@localhost:5432/ai_development_team` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `OPENROUTER_API_KEY` | OpenRouter API key | (requerido) |
| `OPENROUTER_MODEL` | OpenRouter model ID | `qwen/qwen-2.5-coder-32b-instruct:free` |
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `OLLAMA_MODEL` | Ollama model name | `qwen2.5-coder:7b` |
| `DEFAULT_PROVIDER` | Default LLM provider | `openrouter` |
| `API_KEY_STATIC` | Static API key for auth | `change-me-in-production` |
| `JWT_SECRET_KEY` | JWT signing secret | `change-me-in-production` |
| `GITHUB_TOKEN` | GitHub personal access token | (opcional) |
| `SANDBOX_IMAGE` | Docker image for sandbox | `python:3.12-slim` |
| `SANDBOX_TIMEOUT` | Sandbox command timeout (sec) | `120` |
| `SANDBOX_MEM_LIMIT` | Sandbox memory limit | `256m` |
| `BUDGET_MAX_COST_USD` | Max cost per run in USD | `1.0` |
| `BUDGET_MAX_TOKENS` | Max tokens per run | `100000` |
| `ENVIRONMENT` | Environment (development/production) | `development` |
| `LOG_LEVEL` | Logging level | `INFO` |

## MCP (Model Context Protocol)

La plataforma expone 11 herramientas via MCP para integración con Claude Desktop, Cursor, y otros clientes compatibles.

### Herramientas disponibles

| Tool | Descripción |
|------|-------------|
| `read_file` | Leer contenido de archivo |
| `write_file` | Escribir/crear archivos |
| `list_files` | Listar archivos del workspace |
| `compute_diff` | Calcular diff unificado |
| `execute_in_sandbox` | Ejecutar comando en contenedor Docker |
| `github_create_branch` | Crear branch en GitHub |
| `github_create_commit` | Crear commit con múltiples archivos |
| `github_create_pr` | Crear Pull Request |
| `github_exchange_token` | Intercambiar código OAuth por token |
| `db_execute_query` | Ejecutar query SQL (solo lectura) |
| `db_get_schema` | Obtener schema de tablas |

### Integración con Claude Desktop

Agregar a `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ai-development-team": {
      "command": "python",
      "args": ["-m", "core.tools.mcp_server"],
      "env": {
        "DATABASE_URL": "postgresql+asyncpg://ai_team:ai_team_secret@localhost:5432/ai_development_team",
        "GITHUB_TOKEN": "ghp_your_token"
      }
    }
  }
}
```

## Roadmap

- [x] **Fase 1**: MVP con Coder Agent
- [x] **Fase 2**: Integración con múltiples modelos (Ollama)
- [x] **Fase 3**: Router automático de modelos
- [x] **Fase 4**: Sistema multiagente completo
- [x] **Fase 5**: Integración con herramientas (GitHub, archivos)
- [x] **Fase 6**: MCP (Model Context Protocol)
- [x] **Fase 7**: Observabilidad
- [x] **Fase 8**: Optimización de costos
- [x] **Fase 9**: Producción

## Licencia

MIT
