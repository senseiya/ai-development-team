# AI Development Team — Arquitectura del Motor

## Pipeline Completo

```
┌──────────────┐
│   Usuario    │
│  (Request)   │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                             LANGGRAPH STATEGRAPH                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  ┌────────┐  ┌─────────┐ │
│  │Architect │─▶│ Planner  │─▶│  generate_file*   │─▶│ Tester │─▶│ Reviewer│ │
│  └──────────┘  └──────────┘  └────────┬─────────┘  └───┬────┘  └────┬────┘ │
│                                       │                │            │      │
│                              ┌────────┴────────┐       │     ┌──────┴───┐  │
│                              │  Más archivos?  │       │     │ Critical │  │
│                              └────────┬────────┘       │     └────┬─────┘  │
│                                  Sí/No                  │      No  │Si     │
│                                  │  │                   │         │       │
│                                  │  └─── No ────────────┘         │       │
│                                  │            │                   ▼       │
│                                  │            │               ┌────────┐  │
│                                  │            │               │  HITL  │  │
│                                  │            │               │(waiting)│ │
│                                  │            │               └────────┘  │
│                                  │            ▼                           │
│                                  │     ┌──────────────┐                  │
│                                  │     │  Retry loop  │                  │
│                                  │     │(max 3 veces) │                  │
│                                  │     └──────┬───────┘                  │
│                                  │        Si/No                          │
│                                  │         │  │                          │
│                                  └── Sí ───┘  └─── No ──────────────────┘
│                                                                          │
│                                              ┌─────────────────┐        │
│                                              │ Documentation   │◀───────┘
│                                              └────────┬────────┘        │
│                                                       │                  │
│                                                       ▼                  │
│                                                  ┌────────┐             │
│                                                  │  END   │             │
│                                                  └────────┘             │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Flujo de Generación Incremental (Archivo por Archivo)

```
generate_file node
──────────────────
                          ┌──────────────┐
                    ────▶│  File Task   │
                         │  ready[0]    │
                         └──────┬───────┘
                                │
                    ┌───────────▼───────────┐
                    │   ContextBuilder      │
                    │   (blueprint + deps)  │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │    CoderAgent         │
                    │   (LLM: 1 archivo)    │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │  SyntaxValidator      │
                    │  (ast.parse / node)   │
                    └───────────┬───────────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
                    ▼                       ▼
              ┌──────────┐          ┌──────────────┐
              │  Válido  │          │  Inválido    │
              │          │          │              │
              │ DONE +   │          ▼              │
              │ persist  │   ┌──────────────┐      │
              └──────────┘   │ RepairAgent  │      │
                             │ (LLM, max 3) │      │
                             └──────┬───────┘      │
                                    │               │
                            ┌───────┴───────┐       │
                            │               │       │
                            ▼               ▼       │
                     ┌──────────┐    ┌──────────┐   │
                     │ Repaired │    │  FAILED  │   │
                     │  → DONE  │    │  (error) │   │
                     └──────────┘    └──────────┘   │
                                                    │
                                                    │
              DONE ──────────▶ next FileTask ────────┘
                               o tester si todos OK
```

---

## Estructura del Código

```
ai-development-team/
│
├── core/                          ← MOTOR PRINCIPAL
│   │
│   ├── agents/                    ← Agentes del pipeline
│   │   ├── base.py                ←   BaseAgent ABC
│   │   ├── architect.py           ←   [NUEVO] Diseña arquitectura
│   │   ├── planner.py             ←   Descompone en tareas
│   │   ├── task_scheduler.py      ←   Planifica archivos + dependencias
│   │   ├── context_builder.py     ←   Contexto mínimo por archivo
│   │   ├── coder.py               ←   Genera código (1 archivo x llamada)
│   │   ├── syntax_validator.py    ←   Valida sintaxis (Python/JS/Go)
│   │   ├── repair_agent.py        ←   Repara errores de sintaxis
│   │   ├── tester.py              ←   Ejecuta tests
│   │   ├── reviewer.py            ←   Revisa calidad/seguridad
│   │   ├── documentation.py       ←   Genera documentación
│   │   └── artifact_manager.py    ←   Persiste artefactos
│   │
│   ├── orchestrator/              ← Orquestación
│   │   ├── state.py               ←   AgentState + dataclasses
│   │   ├── graph.py               ←   LangGraph StateGraph
│   │   └── checkpointer.py        ←   Persistencia en PostgreSQL
│   │
│   ├── router/                    ← Enrutamiento de LLM
│   │   ├── model_router.py        ←   Selección por capacidad
│   │   ├── registry.py            ←   Modelos seed
│   │   └── providers/             ←   Proveedores LLM
│   │       ├── openrouter.py      ←     OpenRouter API
│   │       └── ollama.py          ←     Ollama local
│   │
│   ├── tools/                     ← Herramientas (MCP)
│   │   ├── filesystem_tool.py     ←   File I/O
│   │   ├── sandbox_exec_tool.py   ←   Docker sandbox
│   │   ├── github_tool.py         ←   GitHub API
│   │   ├── db_tool.py             ←   SQL read-only
│   │   ├── mcp_server.py          ←   MCP server
│   │   └── mcp_client.py          ←   MCP client
│   │
│   ├── auth/                      ← Autenticación JWT
│   ├── cost/                      ← Tracking de costos + budget
│   ├── observability/             ← Logging, métricas, tracing
│   ├── middleware/                 ← Rate limiting (SlowAPI)
│   ├── config.py                  ← Settings (pydantic-settings)
│   └── schemas.py                 ← Schemas Pydantic compartidos
│
├── apps/api/                      ← FastAPI REST API
│   ├── main.py                    ←   App FastAPI
│   ├── deps.py                    ←   Dependencias
│   └── routers/                   ←   Endpoints
│       ├── tasks.py               ←     POST /tasks
│       ├── runs.py                ←     GET/POST /runs
│       ├── auth.py                ←     JWT auth
│       ├── costs.py               ←     Cost dashboard
│       └── models.py              ←     Admin modelos
│
├── db/                            ← Base de datos
│   ├── models.py                  ←   SQLAlchemy ORM
│   └── migrations/                ←   Alembic migrations
│
├── tests/                         ← Tests (218+ unit, 35 nuevos)
│
├── scripts/                       ← Scripts de ejecución
│   └── output/crud_full/          ←   Proyecto CRUD generado
│
├── docker-compose.yml             ← Servicios (PG, Redis)
├── Dockerfile.api                 ← Multi-stage build
└── pyproject.toml                 ← Dependencias + config
```

---

## Data Flow Detallado

### 1. Architect → ProjectBlueprint

```
Request: "Create a task CRUD with FastAPI"

ArchitectAgent
  │
  ├── Llama a LLM con system prompt de arquitecto
  │   (sin código, solo decisiones técnicas)
  │
  └── Produce:
      ProjectBlueprint {
          project_name: "task-manager"
          backend: "FastAPI"
          database: "SQLite"
          orm: "SQLAlchemy"
          patterns: ["Repository", "Service Layer"]
          architecture: "layered"
          directory_structure: ["src/", "src/models/", ...]
          ...
      }
```

### 2. Planner → ProjectPlan

```
ProjectBlueprint
  │
  ├── PlannerAgent lee el Blueprint
  │   (NO toma decisiones arquitectónicas)
  │
  ├── TaskScheduler descompone en FileTasks
  │   con dependencias entre archivos
  │
  └── Produce:
      ProjectPlan {
          files: [
              FileTask("requirements.txt", deps=[]),
              FileTask("src/models/task.py", deps=["requirements.txt"]),
              FileTask("src/services/task_service.py", deps=["src/models/task.py"]),
              ...
          ]
      }
```

### 3. generate_file → Código + Validación

```
ProjectPlan
  │
  ├── get_ready_tasks() → tasks sin dependencias pendientes
  │
  ├── ContextBuilder.build_context(task)
  │   ├── filename + description
  │   ├── blueprint rules (framework, ORM, patrones)
  │   ├── contenido de dependencias ya generadas
  │   └── interfaces públicas de dependencias
  │
  ├── CoderAgent.generate_file()
  │   └── LLM produce raw content (sin JSON)
  │
  ├── SyntaxValidator.validate()
  │   ├── Python → ast.parse()
  │   ├── JS/TS → node --check
  │   └── Go → go vet
  │
  ├── [Si inválido] RepairAgent.repair()
  │   └── LLM corrige con contexto del error
  │
  └── ArtifactManager.save()
      └── Persiste en disco + logs
```

### 4. Tester → Reviewer → Documentation

```
Todos los archivos generados
         │
         ▼
   TesterAgent
   ├── Ejecuta tests (si existen)
   └── Reporta TestSuiteReport

         │
         ▼
   ReviewerAgent
   ├── Revisa calidad, seguridad, estilo
   ├── Si severidad=critical → HITL (waiting_approval)
   └── Produce ReviewFinding[]

         │
         ▼
   DocumentationAgent
   └── Genera README, documentación
```

---

## State (AgentState TypedDict)

```python
class AgentState(TypedDict):
    # Identidad
    run_id: str
    user_request: str

    # Arquitectura (NUEVO)
    project_blueprint: ProjectBlueprint | None
    blueprint_summary: str

    # Planificación
    plan: list[SubTask] | None
    file_tasks: list[FileTask]
    project_plan: ProjectPlan | None

    # Generación incremental
    current_file_index: int
    generated_files: list[str]
    validation_errors: dict[str, str]

    # Ejecución
    current_step: str
    files_changed: list[FileDiff]
    test_results: TestSuiteReport | None
    review_findings: list[ReviewFinding]
    documentation: str | None
    iteration_count: int
    status: str

    # Tracking
    messages: list[AgentMessage]
    cost_usd: float
    tokens_used: int

    # Workspace
    workspace_path: str
    model_used: str
    provider_used: str
```

---

## ProjectBlueprint

```python
@dataclass
class ProjectBlueprint:
    # Identity
    project_name: str
    project_type: str          # "web_api" | "cli" | "fullstack"
    description: str

    # Backend
    backend: str               # "FastAPI" | "Django" | "Express"
    backend_language: str      # "python" | "typescript" | "go"

    # Frontend
    frontend: str              # "React" | "HTML+CSS" | "HTMX" | "none"
    frontend_language: str

    # Data layer
    database: str              # "PostgreSQL" | "SQLite" | "MongoDB"
    orm: str                   # "SQLAlchemy" | "Prisma" | "GORM"
    cache: str                 # "Redis" | "none"

    # Auth
    authentication: str        # "JWT" | "OAuth2" | "API_KEY"
    authorization: str         # "RBAC" | "none"

    # API
    api_style: str             # "REST" | "GraphQL" | "gRPC"
    api_versioning: str

    # Architecture
    patterns: list[str]        # ["Repository", "Service Layer"]
    architecture: str          # "layered" | "hexagonal" | "clean"
    directory_structure: list[str]

    # Dependencies
    dependencies: list[str]
    dev_dependencies: list[str]

    # Quality
    testing: list[str]         # ["pytest", "httpx"]
    linting: list[str]         # ["ruff"]
    formatter: list[str]
    type_checker: list[str]    # ["mypy"]

    # Infrastructure
    docker: bool
    ci_cd: str
    environment_variables: dict
    deployment_target: str

    # Rules
    quality_rules: list[str]
    coding_conventions: list[str]
    security_requirements: list[str]
    performance_requirements: list[str]
```

---

## Model Router (LLM Selection)

```
Agent (capability: code_generation)
         │
         ▼
   ModelRouter.call(capability, prompt)
         │
         ├── 1. Busca modelos habilitados con esa capability
         ├── 2. Ordena por priority
         ├── 3. Prueba en orden hasta éxito
         │
         ├── ✅ OpenRouter (primary)
         │   └── google/gemma-4-26b-a4b-it:free
         │
         └── ⚠️ Ollama (fallback)
             └── qwen3.5:9b (local)
```

---

## Tecnologías

| Componente | Tecnología |
|-----------|-----------|
| Lenguaje | Python 3.14+ |
| Framework web | FastAPI + Pydantic v2 |
| Orquestación | LangGraph (StateGraph) |
| Base de datos | PostgreSQL + pgvector |
| Cache | Redis |
| LLM Provider | OpenRouter (free-tier) + Ollama (fallback) |
| Modelo principal | `google/gemma-4-26b-a4b-it:free` |
| Auth | JWT (access 15min + refresh 7d) |
| Sandbox | Docker (contenedores efímeros) |
| Testing | pytest (218+ unit tests) |
| Linting | Ruff (line-length=100) |
| Type checking | mypy strict |
| CI/CD | GitHub Actions |
| Contenedores | Docker multi-stage + docker-compose |
