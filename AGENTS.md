# AGENTS.md — Contexto de proyecto para OpenCode

## 1. Qué estamos construyendo

**AI Development Team**: una plataforma multiagente en Python donde un orquestador coordina un pipeline de 7 agentes especializados (Architect, Planner, Coder, Tester, Reviewer, Documentation, Repair) que colaboran para desarrollar software automáticamente a partir de una solicitud en lenguaje natural.

Cada agente delega el razonamiento a un LLM elegido dinámicamente por un Model Router, no a un modelo fijo. El sistema debe funcionar completo usando **solo componentes gratuitos/open-source**.

## 2. Stack tecnológico obligatorio

- **Lenguaje:** Python 3.11+
- **API:** FastAPI + Pydantic v2 (no Pydantic v1, no Flask, no Django)
- **Orquestación de agentes:** LangGraph (`StateGraph`), no una máquina de estados custom
- **Base de datos:** PostgreSQL con SQLAlchemy 2.0 async + Alembic para migraciones. Extensión `pgvector` para memoria semántica.
- **Cache/colas:** Redis
- **LLMs:** OpenRouter (modelos free-tier) como único proveedor. No hay soporte para Ollama ni modelos locales. El proveedor se configura vía `DEFAULT_PROVIDER=openrouter` y `OPENROUTER_API_KEY`.
- **Contenedores:** Docker + Docker Compose
- **Testing:** pytest, pytest-asyncio, testcontainers para integración
- **Observabilidad (fases avanzadas):** Prometheus, Grafana, Loki, Langfuse — todos self-hosted, nunca versión SaaS de pago

No introducir dependencias de pago ni servicios que requieran tarjeta de crédito en ningún momento, salvo que se indique explícitamente lo contrario en una fase futura.

## 3. Principios de arquitectura no negociables

1. **Ningún agente conoce el modelo LLM que usa.** Un agente pide una `capability` (`reasoning`, `code_generation`, `code_review`, `summarization`, `long_context`) al Model Router; el Router decide el proveedor/modelo concreto. Nunca hardcodear el nombre de un modelo dentro de la lógica de un agente.
2. **El registro de modelos vive en base de datos**, no en código. Agregar un modelo nuevo debe ser un INSERT en la tabla `model_profiles`, nunca un cambio de código ni un redeploy.
3. **Toda ejecución de código generado ocurre en sandbox** (contenedor Docker aislado, sin privilegios, límites de CPU/memoria/tiempo). Nunca ejecutar código generado por un LLM directamente en el proceso principal ni en el host.
4. **Los workers son stateless.** Todo estado durable vive en PostgreSQL o Redis, nunca en memoria del proceso, para poder escalar horizontalmente sin fricción.
5. **El estado del pipeline se checkpointea en cada transición del grafo** (tabla `run_checkpoints`), permitiendo pausar, reanudar y auditar cualquier run.
6. **Los loops entre agentes tienen límite explícito** (`max_iterations`, default 3). Nunca un loop sin cota.
7. **Hallazgos de seguridad críticos detienen el pipeline** y requieren aprobación humana explícita (HITL) vía `POST /runs/{id}/approve`. Nunca continuar automáticamente ante un hallazgo `severity=critical`.
8. **Todo reintento y toda decisión de fallback queda registrada** en `agent_messages`/logs. Nunca reintentos silenciosos.

## 4. Estructura de carpetas de referencia

```
ai-development-team/
├── apps/
│   ├── api/                  # FastAPI: routers tasks, runs, auth, ws
│   └── worker/                # ejecuta el grafo LangGraph
├── core/
│   ├── orchestrator/          # graph.py, state.py, checkpointer.py
│   ├── agents/                 # base.py + architect, planner, coder, tester, reviewer, documentation, repair, task_scheduler, context_builder, syntax_validator, artifact_manager
│   ├── router/                 # model_router.py, registry.py, providers/openrouter.py
│   ├── validators/             # blueprint_validator.py
│   ├── tools/                   # filesystem/github/sandbox_exec/db tools + mcp
│   └── memory/                 # conversation_store.py, vector_store.py
├── db/                          # models.py (SQLAlchemy), migrations/ (Alembic), session.py
├── infra/
│   ├── docker/                  # Dockerfile.api, Dockerfile.worker, docker-compose.yml
│   ├── k8s/                      # manifiestos futuros (fase 9)
│   └── observability/          # prometheus.yml, grafana/, loki-config.yml
├── tests/{unit,integration,e2e}/
└── docs/{architecture.md, adr/}
```

Respetar esta estructura desde la Fase 1, aunque varias carpetas queden vacías al principio. No inventar una estructura alternativa.

## 5. Contratos clave (no romper sin actualizar este documento)

### `AgentState` (estado compartido del grafo)
```python
class AgentState(TypedDict):
    run_id: str
    user_request: str
    plan: list[SubTask] | None
    current_step: str
    files_changed: list[FileDiff]
    test_results: TestReport | None
    review_findings: list[ReviewFinding]
    documentation: str | None
    iteration_count: int
    status: Literal["planning","coding","testing","reviewing","documenting","done","failed","waiting_approval"]
    run_status: str | None  # derivado: "pending"|"running"|"completed"|"failed"|"partial_success"|"waiting_approval"
    messages: list[AgentMessage]
    cost_usd: float
    tokens_used: int
    project_blueprint: ProjectBlueprint | None
    blueprint_summary: str
    file_tasks: list[FileTask]
    project_plan: ProjectPlan | None
    current_file_index: int
    generated_files: list[str]
    validation_errors: dict[str, str]
```

### `ProjectBlueprint` (contrato formal Pydantic v2, frozen=True)
```python
class ProjectBlueprint(BaseModel):
    model_config = ConfigDict(frozen=True, use_enum_values=True)
    blueprint_version: int = 1
    schema_version: int = 1
    project_name: str
    project_type: Literal["web_api","cli","library","fullstack","microservice"]
    backend: str                          # validado contra blueprint_options
    backend_language: Literal["python","typescript","go","rust","javascript"]
    frontend: str                         # validado contra blueprint_options
    frontend_language: Literal["typescript","javascript","none"]
    database: str                         # validado contra blueprint_options
    orm: str                              # validado contra blueprint_options
    authentication: str                   # validado contra blueprint_options
    api_style: Literal["REST","GraphQL","gRPC","none"]
    architecture: Literal["layered","hexagonal","clean","modular","monolith"]
    decisions: list[BlueprintDecision]    # rationale de cada elección
    # ... más campos en state.py
```

### `BlueprintDecision`
```python
class BlueprintDecision(BaseModel):
    category: str
    selected: str
    rationale: str
    alternatives: list[str] = []
```

### `RunStatus` (estado público de negocio)
```python
class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
```
Relación: `RunStatus` se deriva de `AgentState.status` en `derive_run_status()` en `graph.py`. Nunca se actualiza independientemente.

### `BaseAgent` (interfaz que implementan todos los agentes)
```python
class BaseAgent(ABC):
    capability: ModelCapability
    tools: list[str]

    @abstractmethod
    async def run(self, state: AgentState) -> AgentState: ...
```

### `BlueprintValidator`
```python
class BlueprintValidator:
    def validate(self, blueprint: ProjectBlueprint) -> None:
        """Valida compatibilidad arquitectónica.
        Lanza BlueprintValidationError si hay combinaciones inválidas
        (ej: FastAPI + Entity Framework).
        """
```

### Pipeline completo
```
Architect → BlueprintValidator → Planner → TaskScheduler → generate_file*
(Coder → SyntaxValidator → RepairAgent?) → Tester → Reviewer → Documentation
```

## 6. Esquema de base de datos (tablas principales)

`users`, `api_keys`, `projects`, `runs`, `run_checkpoints`, `tasks`, `agent_messages`, `file_changes`, `test_reports`, `review_findings`, `model_profiles`, `memory_embeddings` (con columna `VECTOR(1024)`, requiere `CREATE EXTENSION vector`).

Toda migración de esquema se hace con Alembic, nunca modificando la base directamente ni con `create_all()` en producción.

## 7. Convenciones de código

- Tipado estricto con type hints en todo el código Python; `mypy` limpio como objetivo.
- Todos los modelos de datos que cruzan una frontera (API, mensajes entre agentes, respuestas de tools) son clases Pydantic v2, no dicts sueltos.
- Nombres de archivos y módulos en `snake_case`, clases en `PascalCase`.
- Cada agente vive en su propio archivo dentro de `core/agents/`, hereda de `BaseAgent`, y no importa directamente ningún cliente de proveedor LLM — solo usa `ModelRouter`.
- Los tests van junto a la estructura de `core/`/`apps/` reflejada en `tests/unit/`, `tests/integration/`, `tests/e2e/` — no tests dispersos junto al código fuente.
- Variables de entorno documentadas en `.env.example`, nunca credenciales reales commiteadas.
- Commits y PRs en español o inglés consistente (elegir uno al principio del proyecto y mantenerlo).

## 8. Qué NO hacer

- No usar Flask, Django, ni ningún framework de agentes propietario/de pago (ej. no usar el SDK de OpenAI Agents si implica lock-in a un proveedor pago; usar LangGraph).
- No ejecutar `pip install` de paquetes que requieran licencia comercial.
- No hardcodear API keys, ni de OpenRouter ni de GitHub, en ningún archivo versionado.
- No saltarse el sandbox "por simplicidad" en ninguna fase, ni siquiera en el MVP — si el MVP no ejecuta código todavía, no aplica, pero en cuanto el Tester ejecute algo, va en sandbox desde el primer commit que lo introduzca.
- No implementar loops entre agentes sin límite de iteraciones.
- No usar `localStorage`/`sessionStorage` si en algún momento se construye una UI en el navegador (usar estado de la app o el backend).
- No mezclar responsabilidades entre agentes (ej. que el Coder también decida si algo es seguro — eso es del Reviewer).
- No hacer que el Planner tome decisiones arquitectónicas (eso es del Architect).
- No reasignar campos de un `ProjectBlueprint` después de creado (es `frozen=True`).
- No reintentar llamadas a proveedor LLM sin backoff exponencial (ver `MAX_FILE_RETRIES` en graph.py).
- No modificar `RunStatus` manualmente — siempre usar `derive_run_status()`.

## 9. Cómo pedirle ayuda a la IA fase por fase

Este documento se complementa con `ai-development-team-prompts-por-fase.md`, que tiene un prompt ya armado para cada una de las 9 fases del roadmap. El flujo recomendado es:

1. Pegar este `CONTEXT.md` al inicio de la sesión (una sola vez, o cada vez que se abra un chat nuevo).
2. Pegar el prompt de la fase correspondiente desde el documento de prompts.
3. Si la IA propone desviarse de algún contrato de la sección 5, o de la estructura de carpetas de la sección 4, señalarlo explícitamente citando este documento antes de aceptar el cambio.

## 10. Documento de referencia completo

Para el detalle completo de arquitectura (diagrama de componentes, flujo entre agentes, esquema SQL completo con tipos e índices, APIs REST completas, estrategia de pruebas, despliegue) consultar `ai-development-team-documento-maestro.md`. Este `CONTEXT.md` es un resumen operativo pensado para caber en el contexto de una IA sin saturarlo; el documento maestro es la fuente de verdad cuando haya dudas de detalle.
