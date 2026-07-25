# AI Development Team — Documento Maestro

Plataforma multiagente para desarrollo de software automatizado. Stack 100% gratuito/open-source. Este documento condensa arquitectura + roadmap en una sola referencia para arrancar la construcción.

---

## 1. Qué es el sistema

Un usuario envía una solicitud → un **Orquestador** (LangGraph) coordina siete agentes especializados en secuencia:

```
Usuario → API Gateway → Orchestrator → Architect → Planner → generate_file*
→ Tester → Reviewer → Documentation → Respuesta
```

Cada agente delega en el **Model Router**, que elige el modelo LLM más adecuado según la tarea, con cadenas de respaldo automáticas y backoff exponencial ante errores de provider. Todo el trabajo pasa por pruebas reales (no solo opinión de un LLM) antes de darse por bueno, y cada decisión queda auditada.

## 2. Stack (todo gratuito)

| Necesidad | Elección |
|---|---|
| Modelos | OpenRouter (modelos free-tier) — único proveedor |
| Orquestación de agentes | LangGraph |
| API | FastAPI + Pydantic v2 |
| Base de datos | PostgreSQL + pgvector |
| Cache/colas/pub-sub | Redis |
| Contenedores | Docker + Docker Compose |
| PRs/repos | GitHub API (free tier) |
| Observabilidad | Prometheus + Grafana + Loki + Langfuse (self-hosted) |
| Herramientas | MCP (Model Context Protocol) |

Regla de oro: agregar un modelo de pago después (GPT-5, Claude, Gemini) no cambia la arquitectura — se conecta igual vía el Model Router.

## 3. Componentes del sistema

1. **API Gateway (FastAPI)** — entrada única, auth, validación Pydantic, REST + WebSocket.
2. **AI Orchestrator (LangGraph)** — grafo de estados con bordes condicionales (reintentos, loops, HITL).
3. **Agentes** — cada uno nodo del grafo, con prompt propio, herramientas permitidas y capability declarada.
4. **Model Router** — resuelve `capability + restricciones → modelo`, registro editable en DB, sin hardcode.
5. **Tool/MCP Gateway** — acceso a archivos, ejecución sandboxed, GitHub, base de datos.
6. **Persistencia** — PostgreSQL (estado durable) + Redis (cache, colas, pub-sub).
7. **Observabilidad** — logs estructurados, métricas, trazas LLM.

## 4. Agentes: responsabilidades

| Agente | Entrada | Salida | Herramientas | Capability preferida |
|---|---|---|---|---|
| **Planner** | requerimiento + contexto del repo | plan estructurado (subtareas, dependencias, criterios de aceptación) | lectura de repo, búsqueda semántica | reasoning |
| **Coder** | subtarea | diffs/archivos | FS read/write, linter, git branch | code_generation |
| **Tester** | código generado | reporte pass/fail + cobertura | ejecución sandboxed (pytest/npm test) | code_generation + ejecución real |
| **Reviewer** | diffs + tests | findings (calidad/seguridad) | análisis estático (ruff, bandit, semgrep) | code_review |
| **Documentation** | diffs finales + plan + findings | README/changelog/docs | FS write | summarization |

Bordes condicionales clave: `Tester→Coder` (loop, máx. 3 iteraciones), `Reviewer→HITL` (si hay hallazgo crítico de seguridad), cualquier nodo `→ error state` tras agotar reintentos.

## 5. Estado del grafo (`AgentState`)

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
    status: Literal["planning","coding","testing","reviewing","documenting","done","failed"]
    messages: list[AgentMessage]
    cost_usd: float
    tokens_used: int
```

Se checkpointea en PostgreSQL en cada transición (pausa/reanudación + HITL + recuperación ante caídas).

## 6. Model Router

```python
class ModelCapability(str, Enum):
    REASONING = "reasoning"
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    LONG_CONTEXT = "long_context"
    SUMMARIZATION = "summarization"

class ModelProfile(BaseModel):
    id: str
    provider: Literal["openrouter", "ollama"]
    capabilities: list[ModelCapability]
    cost_per_1k_input: float
    cost_per_1k_output: float
    max_context: int
    priority: int
    enabled: bool = True

class ModelRouter:
    def select(self, capability, max_cost=None, prefer_local=False, fallback_chain=True) -> ModelProfile: ...
```

El registro vive en tabla `model_profiles` — agregar modelo nuevo es un INSERT, no un deploy. Soporta fallback chains (ej. modelo gratis rate-limited → otro modelo gratis → Ollama local).

## 7. Estructura de carpetas

```
ai-development-team/
├── apps/
│   ├── api/            # FastAPI (routers: tasks, runs, auth, ws)
│   └── worker/          # workers que ejecutan el grafo
├── core/
│   ├── orchestrator/    # graph.py, state.py, checkpointer.py
│   ├── agents/           # base.py + planner/coder/tester/reviewer/documentation
│   ├── router/           # model_router.py, registry.py, providers/{openrouter,ollama}.py
│   ├── tools/             # mcp_server.py + filesystem/github/sandbox_exec/db tools
│   └── memory/           # conversation_store.py, vector_store.py
├── db/                    # models.py, migrations/ (Alembic), session.py
├── infra/
│   ├── docker/            # Dockerfiles + docker-compose.yml
│   ├── k8s/                # manifiestos futuros
│   └── observability/    # prometheus.yml, grafana/, loki-config.yml
├── tests/{unit,integration,e2e}/
├── docs/{architecture.md, adr/}
└── pyproject.toml
```

## 8. Patrones de diseño

Strategy (Model Router) · Adapter (providers) · State Machine/Graph (orchestrator) · Chain of Responsibility (pipeline de agentes) · Observer/Pub-Sub (Redis→WebSocket) · Repository (capa `db/`) · Circuit Breaker + Retry (llamadas a LLM/GitHub) · Factory (creación de agentes/tools) · CQRS ligero (lectura vs escritura en API) · Unit of Work (checkpoints transaccionales).

## 9. Esquema de base de datos (resumen)

Tablas: `users`, `api_keys`, `projects`, `runs`, `run_checkpoints`, `tasks`, `agent_messages`, `file_changes`, `test_reports`, `review_findings`, `model_profiles`, `memory_embeddings` (pgvector). El esquema SQL completo con tipos, FKs e índices está en el documento de diseño original — se usa tal cual, sin cambios, como base de las migraciones Alembic.

## 10. APIs REST (resumen)

Auth: `/auth/register`, `/auth/login`, `/auth/refresh`, `/api-keys`.
Proyectos: `/projects`, `/projects/{id}`.
Runs: `POST /tasks`, `GET /runs/{id}`, `/runs/{id}/messages`, `/runs/{id}/diffs`, `/runs/{id}/tests`, `/runs/{id}/review`, `POST /runs/{id}/approve`, `POST /runs/{id}/cancel`.
Streaming: `WS /ws/runs/{run_id}`.
Admin: `GET/POST /models`, `PATCH /models/{id}`.
Sistema: `/health`, `/metrics`.

## 11. Autenticación

JWT (access 15min + refresh 7 días, blacklist en Redis) para UI · API Keys (hash SHA-256) para integraciones · OAuth2 GitHub como login preferido (reutiliza el token para operar la GitHub API) · RBAC simple (`user`/`admin`) · Rate limiting por usuario (Redis + `slowapi`).

## 12. Memoria

Tres capas: **corto plazo** (`AgentState` en ejecución, checkpointeado), **conversacional** (`agent_messages`, historial auditable), **semántica de largo plazo** (`memory_embeddings` con pgvector, indexado por proyecto — el Planner la consulta antes de generar un nuevo plan). Compactación automática cuando el historial supera un umbral de tokens.

## 13. Manejo de errores

Rate limit/timeout LLM → retry con backoff + fallback chain del Router. Salida inválida del modelo → repair prompt, luego escalar a modelo mayor. Tests fallan → loop a Coder (máx. 3 iteraciones) → `failed_partial` si se agota. Hallazgo de seguridad crítico → HITL obligatorio. Infra caída → circuit breaker + colas persistentes (no se pierde el job). Ejecución de código → siempre en sandbox, sin excepciones. Timeout global por run configurable.

## 14. Observabilidad

Logs estructurados (`structlog`, con `run_id`/`agent_name`/`trace_id`) · métricas Prometheus (duración por nodo, tasa de éxito, tokens/costo, cola pendiente) · dashboards Grafana · trazas LLM con Langfuse (prompt, respuesta, tokens, latencia, costo por `run_id`) · logs centralizados Loki+Promtail · alertas (error rate, cola estancada, presupuesto excedido).

## 15. Estrategia de pruebas

Unitarias (agentes aislados con LLM mockeado, Router, validadores Pydantic) · Integración (2-3 nodos con Postgres/Redis en `testcontainers`) · E2E (pipeline completo sobre repo fixture) · Contract testing (esquemas API, `schemathesis`) · LLM-eval (golden dataset, tasa de éxito objetiva) · Carga (`locust`).

## 16. Despliegue

Docker Compose con `api`, `worker` (replicable), `postgres` (pgvector), `redis`, `ollama`, `sandbox-runner` (aislado, sin privilegios), `prometheus`, `grafana`, `loki`. Workers stateless — todo el estado vive en Postgres/Redis, lo que permite escalar horizontalmente sin fricción.

**Evolución a Kubernetes:** Deployments para `api`/`worker` con HPA vía KEDA sobre la cola Redis · StatefulSet u operador (CloudNativePG) para Postgres · sandbox como Job efímero con NetworkPolicy restrictiva · Ingress + cert-manager · Helm charts propios. Es un cambio de plataforma, no de arquitectura, porque el diseño ya es cloud-native desde el día uno.

## 17. Riesgos técnicos transversales

Modelos gratuitos cambian de nombre/tienen rate limits agresivos → registro en DB + fallback chains + Ollama como último recurso. Ejecución de código insegura por naturaleza → sandbox obligatorio. Loops infinitos entre agentes → `max_iterations` + costo máximo por run. Costos ocultos si se suman modelos de pago → tracking de costo en tiempo real + límites configurables. Contexto insuficiente en proyectos grandes → memoria semántica + chunking, no cargar el repo completo. Latencia acumulada del pipeline secuencial → paralelizar subtareas sin dependencias.

---

## 18. Roadmap de construcción — 9 fases

Cada fase es incremental: nunca hay que rehacer lo anterior, solo extenderlo.

| # | Fase | Objetivo | Tiempo | Criterio de cierre |
|---|---|---|---|---|
| 1 | **MVP un solo agente** | Flujo end-to-end usuario→API→agente→LLM→respuesta, con la estructura de carpetas final ya montada | 2 sem | `POST /tasks` genera código real y persiste en DB; corre con `docker-compose up` |
| 2 | **Múltiples modelos** | Mismo agente puede correr contra OpenRouter u Ollama sin tocar código de negocio | 1.5 sem | Cambiar de proveedor es una variable de entorno; tests de integración corren sin red externa |
| 3 | **Router automático** | El sistema elige modelo por capability, con fallback, sin intervención manual | 1.5 sem | Agregar modelo = INSERT en DB; desactivar el primario no rompe el sistema |
| 4 | **Sistema multiagente** | Los 5 agentes orquestados como grafo LangGraph, con reintentos y HITL | 3.5 sem | Pipeline completo produce código+tests+review+docs en un run; loop Tester→Coder funciona; HITL bloquea ante hallazgo crítico |
| 5 | **Herramientas (GitHub/FS/DB)** | Agentes operan sobre un repo real: leen/escriben archivos, abren PRs | 2.5 sem | Un run termina con un PR real abierto en repo de prueba; sandbox verificado (no hay fuga al host) |
| 6 | **MCP** | Herramientas expuestas como servidor MCP estándar, interoperable | 1.5 sem | Mismas tools, ahora vía protocolo MCP; un cliente MCP externo puede listarlas/usarlas |
| 7 | **Observabilidad** | Ver dentro del sistema: métricas, trazas LLM, dashboards | 2 sem | Reconstruir cualquier `run_id` en Grafana/Langfuse sin mirar código; alerta se dispara en escenario simulado |
| 8 | **Optimización de costos** | Reducir gasto de tokens y dejar el sistema listo para modelos de pago eficientemente | 1.5 sem | Cache demuestra ahorro medible; corte automático al superar `max_cost_usd` por run, auditado |
| 9 | **Producción** | Despliegue robusto, documentado, resiliente | 2.5 sem | `git clone` + `docker-compose up` funciona en <15 min siguiendo el README; CI en verde con E2E incluido |

**Total estimado:** ~18.5 semanas trabajando part-time (10-15h/semana).

### Riesgos por fase (los más relevantes)

- **F1:** subestimar el setup inicial de FastAPI+SQLAlchemy async+Pydantic v2; elegir un modelo gratuito con rate limits muy agresivos.
- **F2:** requisitos de hardware para correr Ollama razonablemente rápido; diferencias de formato entre proveedores si la interfaz común no está bien abstraída.
- **F3:** IDs de modelos gratuitos en OpenRouter cambian con frecuencia; mala política de prioridad puede hacer que el sistema use siempre el modelo equivocado por defecto.
- **F4:** loops costosos en tokens si `max_iterations` no está bien acotado; depurar un grafo de estados con IA real es más difícil que depurar código determinista — invertir en logging por nodo desde el inicio.
- **F5:** seguridad del sandbox es crítica, requiere revisión dedicada; rate limits de GitHub API gratuita limitan pruebas frecuentes (mockear en la mayoría de tests).
- **F6:** MCP es una spec relativamente nueva, fijar versiones; la capa de protocolo agrega latencia medible.
- **F7:** instrumentar de más genera overhead; el stack de observabilidad completo (Langfuse+Grafana+Loki+Prometheus) consume recursos considerables en dev.
- **F8:** cache de herramientas mal invalidado puede hacer que el sistema "mienta" sobre el estado del código; paralelizar subtareas requiere bloqueo por archivo para evitar condiciones de carrera.
- **F9:** ser honesto en documentación sobre qué tan "production-ready" está cada componente; manifiestos K8s sin clúster real para probarlos pueden tener errores no detectados.

---

## 19. Próximo paso

Con este documento como referencia única, la construcción arranca directo en la **Fase 1**. Los prompts específicos para ejecutar cada fase con una IA están en el documento complementario `ai-development-team-prompts-por-fase.md`, y el contexto de proyecto para dárselo a cualquier IA que vaya a trabajar en el código está en `ai-development-team-contexto-ia.md`.
