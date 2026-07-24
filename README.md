# AI Development Team

Plataforma multiagente para desarrollo de software automatizado. Un orquestador coordina cinco agentes de IA especializados (Planner, Coder, Tester, Reviewer, Documentation) que colaboran para desarrollar software automáticamente.

## Fase 1 - MVP

Esta versión incluye:
- **Coder Agent**: Genera código basado en solicitudes del usuario
- **OpenRouter Integration**: Usa modelos gratuitos de OpenRouter para generación de código
- **FastAPI**: API REST con endpoints para crear tareas y consultar runs
- **PostgreSQL**: Base de datos para persistir runs y resultados
- **Docker**: Contenedores para todos los servicios

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

### 3. Levantar servicios

```bash
docker-compose up -d
```

Esto iniciará:
- PostgreSQL (puerto 5432)
- Redis (puerto 6379)
- Ollama (puerto 11434)
- API (puerto 8000)

### 4. Ejecutar migraciones

```bash
# Esperar a que PostgreSQL esté listo
docker-compose exec postgres pg_isready -U ai_team

# Ejecutar migración inicial
alembic revision --autogenerate -m "initial"
alembic upgrade head
```

### 5. Verificar funcionamiento

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
# Formateo de código
ruff format .

# Verificar linting
ruff check .

# Type checking
mypy .
```

## Estructura del Proyecto

```
ai-development-team/
├── apps/
│   ├── api/                  # FastAPI: routers tasks, runs
│   └── worker/               # Workers para ejecución asíncrona
├── core/
│   ├── orchestrator/         # Orquestación de agentes (futuro)
│   ├── agents/               # Agentes de IA
│   │   ├── base.py          # Interfaz base
│   │   └── coder.py         # Coder Agent
│   ├── router/               # Router de modelos
│   │   └── providers/
│   │       └── openrouter.py # Cliente OpenRouter
│   ├── tools/                # Herramientas (futuro)
│   └── memory/               # Memoria (futuro)
├── db/
│   ├── models.py            # Modelos SQLAlchemy
│   ├── session.py           # Sesión de base de datos
│   └── migrations/          # Migraciones Alembic
├── infra/
│   └── docker/
│       └── Dockerfile.api
├── tests/
│   ├── unit/                # Tests unitarios
│   ├── integration/         # Tests de integración
│   └── e2e/                 # Tests end-to-end
└── docs/                    # Documentación
```

## API Endpoints

### Health Check
- `GET /health` - Estado del sistema

### Tasks
- `POST /api/v1/tasks` - Crear y ejecutar una tarea de desarrollo
  - Body: `{"description": "string"}`
  - Headers: `X-API-Key: tu-api-key`
  - Response: RunResponse con el resultado

### Runs
- `GET /api/v1/runs/{id}` - Obtener detalles de un run
  - Headers: `X-API-Key: tu-api-key`
  - Response: RunResponse con el estado

## Variables de Entorno

| Variable | Descripción | Default |
|----------|-------------|---------|
| `DATABASE_URL` | URL de conexión a PostgreSQL | `postgresql+asyncpg://ai_team:ai_team_secret@localhost:5432/ai_development_team` |
| `REDIS_URL` | URL de conexión a Redis | `redis://localhost:6379/0` |
| `OPENROUTER_API_KEY` | API key de OpenRouter | (requerido) |
| `OPENROUTER_MODEL` | Modelo de OpenRouter a usar | `qwen/qwen-2.5-coder-32b-instruct:free` |
| `API_KEY_STATIC` | API key estática para autenticación | `change-me-in-production` |
| `ENVIRONMENT` | Entorno de ejecución | `development` |

## MCP (Model Context Protocol)

The platform exposes all tools via MCP, enabling integration with Claude Desktop, Cursor, and other MCP-compatible clients.

### Available Tools

| Tool | Description | Required Fields |
|------|-------------|-----------------|
| `read_file` | Read file contents from workspace | `file_path`, `workspace_path` |
| `write_file` | Write/create files in workspace | `file_path`, `content`, `workspace_path` |
| `list_files` | List all files in workspace | `workspace_path` |
| `compute_diff` | Compute unified diff between strings | `original`, `modified`, `file_path` |
| `execute_in_sandbox` | Execute command in Docker sandbox | `command`, `timeout`, `memory_limit`, `cpu_quota` |
| `github_create_branch` | Create a GitHub branch | `repo_owner`, `repo_name`, `branch_name`, `base_branch` |
| `github_create_commit` | Create a commit with multiple files | `repo_owner`, `repo_name`, `branch_name`, `message`, `files` |
| `github_create_pr` | Create a Pull Request | `repo_owner`, `repo_name`, `head_branch`, `base_branch`, `title`, `body` |
| `github_exchange_token` | Exchange OAuth code for token | `code`, `client_id`, `client_secret` |
| `db_execute_query` | Execute read-only SQL query | `query`, `database_url` |
| `db_get_schema` | Get database table schemas | `database_url` |

### Claude Desktop Integration

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

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

### Running the MCP Server

```bash
# Stdio mode (for Claude Desktop, Cursor, etc.)
python -m core.tools.mcp_server

# Or as a library
from core.tools.mcp_server import create_mcp_server
server = create_mcp_server()
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
