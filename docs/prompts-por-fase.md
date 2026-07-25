# PROMPTS.md — Un prompt por fase

> Uso: al inicio de la sesión pegá `CONTEXT.md` (contexto del proyecto). Después pegá el prompt de la fase en la que estás. Cada prompt asume que las fases anteriores ya están hechas y no deben rehacerse, solo extenderse.

---

## Fase 1 — MVP con un único agente

```
Vamos a construir la Fase 1 de AI Development Team: un MVP con un único agente.
Ya tenés el contexto completo del proyecto en CONTEXT.md — respetalo estrictamente,
en particular la estructura de carpetas (sección 4) y las convenciones de código (sección 7).

Objetivo de esta fase: demostrar el flujo end-to-end usuario → API → agente → LLM → respuesta,
con la arquitectura final de carpetas ya montada aunque la mayoría de las carpetas queden vacías.

Entregables concretos que necesito que generes, en este orden:
1. Estructura de carpetas completa según CONTEXT.md sección 4 (con archivos __init__.py donde
   corresponda y placeholders mínimos en las carpetas que todavía no se usan).
2. Un único agente Coder Agent (core/agents/coder.py, heredando de BaseAgent) que reciba la
   solicitud completa del usuario y devuelva código generado, sin Planner/Tester/Reviewer todavía.
3. Cliente OpenRouter (core/router/providers/openrouter.py) implementando la interfaz LLMProvider,
   usando un modelo gratuito de generación de código (buscá cuál está disponible como :free en
   OpenRouter actualmente para la capability code_generation).
4. FastAPI (apps/api/main.py + routers/tasks.py, routers/runs.py) con POST /tasks y GET /runs/{id}.
5. Modelos SQLAlchemy 2.0 async mínimos: tabla runs (según el esquema de CONTEXT.md sección 6,
   podés omitir por ahora las columnas que no usa el MVP) + primera migración Alembic.
6. Autenticación simple: API key estática validada desde variable de entorno (JWT completo es
   de la Fase 4, no lo implementes todavía).
7. Dockerfile.api + docker-compose.yml con servicios api + postgres únicamente.
8. Tests unitarios: del endpoint POST /tasks y del cliente OpenRouter con el LLM mockeado
   (no llames a la API real en los tests).
9. README.md con instrucciones para correr el proyecto localmente con docker-compose up.

Criterio de aceptación: un POST /tasks con una descripción en el body debe generar código real
vía OpenRouter, persistirlo en la tabla runs, y poder consultarse con GET /runs/{id}.
Cobertura de tests objetivo: >60% en agente y API.

Antes de escribir código, mostrame primero el plan de archivos que vas a crear/modificar.
```

---

## Fase 2 — Integración con múltiples modelos

```
Ahora vamos a la Fase 2: integración con múltiples modelos. La Fase 1 ya está funcionando
(un agente + OpenRouter). No la rompas ni la reescribas innecesariamente, extendela.

Objetivo: poder llamar tanto a OpenRouter como a Ollama local desde el mismo agente, sin que
el agente sepa a cuál proveedor está llamando.

Necesito:
1. Confirmar/ajustar la interfaz LLMProvider (Protocol) para que sea realmente común entre
   proveedores (mismo método complete(), mismo formato de LLMResponse).
2. core/router/providers/ollama.py implementando esa interfaz.
3. Agregar el servicio ollama al docker-compose.yml, con un modelo local liviano ya declarado
   para descarga (ej. algo de la familia qwen2.5-coder de tamaño 7B para no exigir demasiada RAM).
4. Config/variables de entorno para declarar qué proveedor usa el agente por defecto, sin tocar
   código de negocio al cambiarlo.
5. Manejo de timeouts y errores de conexión diferenciado por proveedor (Ollama local vs
   OpenRouter remoto tienen modos de falla distintos).
6. Tests de integración que corran contra Ollama local usando testcontainers o el propio
   servicio de docker-compose, sin requerir conexión a internet ni a OpenRouter.

Criterio de aceptación: el mismo agente de la Fase 1 debe poder correr contra OpenRouter o contra
Ollama cambiando solo una variable de entorno, y los tests de integración deben pasar sin red externa.

Mostrame primero qué archivos vas a tocar de la Fase 1 y por qué, antes de modificarlos.
```

---

## Fase 3 — Router automático de modelos

```
Fase 3: Router automático de modelos. Las Fases 1 y 2 ya están hechas (un agente que puede
usar OpenRouter u Ollama manualmente). Ahora automatizamos la selección.

Objetivo: que el sistema elija el modelo automáticamente según la capacidad requerida
(ModelCapability), con fallback, sin intervención manual, y con el registro de modelos en base
de datos, no en código (ver CONTEXT.md secciones 3.1, 3.2 y 5 para los contratos exactos de
ModelProfile y ModelRouter).

Necesito:
1. Tabla model_profiles en PostgreSQL + migración Alembic.
2. core/router/model_router.py implementando ModelRouter.select() con lógica de filtrado por
   capability, restricción de costo opcional, y fallback chain quede ordenado por priority.
3. core/router/registry.py con un seed inicial: 3-4 modelos gratuitos de OpenRouter poblando
   distintas capabilities (reasoning, code_generation, code_review, summarization), más al menos
   un modelo Ollama como fallback local de cada capability.
4. Endpoints admin: GET /models, POST /models, PATCH /models/{id} (protegidos, podés seguir
   usando la API key estática de la Fase 1 con un flag de admin simple por ahora).
5. Modificar el Coder Agent de la Fase 1 para que deje de llamar directamente a un provider y
   en su lugar pida al Router una capability (code_generation).
6. Registrar en cada llamada modelo usado, tokens y latencia (versión simplificada de
   agent_messages, sin todavía todos los campos del esquema completo).
7. Tests unitarios de ModelRouter.select() con providers mockeados que fallan a propósito, para
   verificar que el fallback chain funciona.

Criterio de aceptación: agregar un modelo nuevo debe ser un INSERT en model_profiles sin tocar
código. Si desactivo (enabled=false) el modelo primario de una capability, el sistema debe seguir
funcionando usando el siguiente de la cadena, de forma transparente para el agente.

Mostrame el diseño de la tabla model_profiles con los datos semilla exactos antes de migrar.
```

---

## Fase 4 — Sistema multiagente

```
Fase 4: Sistema multiagente completo. Es la fase más grande del roadmap. Las Fases 1-3 ya están
hechas: hay un Coder Agent funcionando con Model Router automático. Ahora sumamos los cuatro
agentes restantes y los orquestamos como grafo.

Objetivo: los cinco agentes (Planner, Coder, Tester, Reviewer, Documentation) orquestados con
LangGraph como un StateGraph, con reintentos acotados y HITL para hallazgos críticos.

Necesito, en este orden:
1. core/orchestrator/state.py con el AgentState completo (TypedDict, ver CONTEXT.md sección 5).
2. core/agents/base.py con la interfaz BaseAgent (ver CONTEXT.md sección 5) y refactor del
   Coder Agent existente para que la implemente formalmente.
3. Los cuatro agentes nuevos: planner.py, tester.py, reviewer.py, documentation.py — cada uno
   con su propio prompt de sistema y su capability declarada (Planner→reasoning,
   Tester→code_generation con ejecución real, Reviewer→code_review, Documentation→summarization).
4. core/orchestrator/graph.py: el StateGraph completo con los bordes condicionales:
   Tester→Coder si hay fallos (máx. 3 iteraciones vía iteration_count), Reviewer→HITL si hay
   hallazgo severity=critical, cualquier nodo→error state tras agotar reintentos.
5. core/orchestrator/checkpointer.py: persistir AgentState en run_checkpoints en cada transición
   (usar el checkpointer de Postgres de LangGraph si está disponible, o implementar uno propio
   sobre la tabla ya definida en el esquema).
6. Migrar autenticación de API key estática a JWT completo (access 15min + refresh 7 días,
   blacklist de refresh tokens en Redis) más API keys por usuario, según CONTEXT.md.
7. POST /runs/{id}/approve para desbloquear un run pausado por HITL.
8. WebSocket /ws/runs/{run_id} transmitiendo progreso en tiempo real vía Redis pub-sub.
9. Tests: unitarios por agente (con LLM mockeado), test de integración del grafo completo
   corriendo contra Ollama local (determinista), test específico que fuerce un fallo de Tester
   y verifique el loop de vuelta a Coder, y otro que fuerce un hallazgo crítico y verifique que
   el run queda bloqueado esperando aprobación.

Criterio de aceptación: una solicitud dispara el pipeline completo de cinco agentes y produce
código + tests + review + documentación en un run. El loop Tester→Coder se resuelve o se agota
correctamente. Un hallazgo de seguridad simulado detiene el run hasta la aprobación explícita.

Andá fase por fase dentro de esta lista y mostrame cada entregable antes de pasar al siguiente,
no generes los nueve puntos de una sola vez.
```

---

## Fase 5 — Integración con herramientas (GitHub, archivos, bases de datos)

```
Fase 5: herramientas reales. El pipeline de 5 agentes de la Fase 4 ya funciona pero opera "en
el vacío" (sin tocar archivos reales ni GitHub). Ahora lo conectamos a un repositorio real.

Necesito:
1. core/tools/filesystem_tool.py: lectura/escritura de archivos dentro de un workspace
   controlado, con validación estricta de que nunca se sale de ese directorio (path traversal
   prevention explícito, con tests que lo verifiquen).
2. core/tools/sandbox_exec_tool.py: ejecución de comandos (tests, linters) en un contenedor
   Docker efímero, sin red o con red restringida, con límites de CPU/memoria/tiempo de
   ejecución. Este es el componente de seguridad más sensible del sistema — priorizalo.
3. core/tools/github_tool.py: OAuth2 con GitHub (reusando el flujo de login si ya existe),
   creación de ramas, commits y apertura de Pull Requests con la descripción generada por
   Documentation Agent.
4. core/tools/db_tool.py: consultas de solo lectura a bases de datos del proyecto del usuario
   cuando el Planner lo requiera.
5. Conectar estas tools a los agentes correspondientes: Coder y Tester usan filesystem +
   sandbox_exec; Documentation usa github_tool para el PR final.
6. Poblar la tabla file_changes con diffs reales generados durante cada run.
7. Repositorio de prueba dedicado (fixture, no un repo real de producción) para los tests de
   integración de esta fase.
8. Un test específico que intente "escapar" del sandbox (ej. acceder al filesystem del host o
   hacer una llamada de red no permitida) y verifique que falla como se espera.

Criterio de aceptación: un run completo termina con un Pull Request real abierto en el
repositorio de prueba, con código, tests y descripción generada. El test de fuga de sandbox
debe fallar (es decir, el sandbox debe contener el intento de escape).

Empezá por el sandbox_exec_tool y su test de seguridad antes que cualquier otra cosa de esta fase.
```

---

## Fase 6 — MCP (Model Context Protocol)

```
Fase 6: migrar las herramientas de la Fase 5 a un servidor MCP estándar.

Objetivo: que filesystem_tool, github_tool, sandbox_exec_tool y db_tool se expongan como tools
MCP con esquemas declarados, y que los agentes las consuman vía cliente MCP en lugar de llamarlas
directamente. Esto reduce el acoplamiento y prepara el sistema para que cualquier cliente
compatible con MCP (no solo nuestros agentes) pueda usarlas.

Necesito:
1. core/tools/mcp_server.py: servidor MCP que expone las cuatro herramientas de la Fase 5 con
   sus esquemas de entrada/salida declarados explícitamente.
2. Adaptar los agentes (Coder, Tester, Documentation) para que llamen a las tools vía cliente
   MCP en vez de importar las funciones directamente.
3. Tests de contrato: verificar que cada tool responde exactamente al esquema MCP declarado,
   sin campos extra ni faltantes.
4. Documentación de cómo conectar un cliente MCP externo (ej. Claude Desktop) a este servidor,
   como demostración de interoperabilidad.
5. Medir y dejar registrado en docs/architecture.md el overhead de latencia que introduce la
   capa MCP frente a la llamada directa de la Fase 5.

Criterio de aceptación: el comportamiento de las herramientas no cambia respecto a la Fase 5,
pero ahora están expuestas vía protocolo MCP. Un cliente MCP externo debe poder listar y usar
al menos una de las tools exitosamente como prueba de interoperabilidad real.

Antes de tocar los agentes existentes, mostrame el esquema MCP propuesto para cada una de las
cuatro tools para que lo revise.
```

---

## Fase 7 — Observabilidad

```
Fase 7: observabilidad. El sistema multiagente con herramientas y MCP ya funciona (Fases 1-6).
Ahora necesito poder ver qué pasa adentro sin leer logs crudos.

Necesito:
1. Logging estructurado con structlog en toda la plataforma (API, worker, cada agente, cada
   tool), incluyendo siempre run_id, agent_name y trace_id en cada línea.
2. Instrumentación Prometheus: duración por nodo del grafo, tasa de éxito/fallo por agente,
   tokens y costo por modelo (usando los datos que el Model Router ya registra desde la Fase 3),
   tamaño de la cola de jobs pendientes.
3. docker-compose.yml actualizado con prometheus, grafana, loki, promtail y langfuse
   (self-hosted, no la versión cloud).
4. Dashboards iniciales de Grafana: salud del sistema, costo acumulado por proyecto/usuario,
   modelos más usados, tiempo medio de un run end-to-end.
5. Integrar Langfuse en el Model Router: cada llamada a un modelo debe trazarse con prompt,
   respuesta, tokens, latencia y costo, vinculada al run_id correspondiente.
6. Al menos dos alertas configuradas en Grafana: tasa de error por encima de un umbral, y cola
   de jobs estancada por más de X minutos.

Criterio de aceptación: tomar cualquier run_id y poder reconstruir en Grafana/Langfuse
exactamente qué pasó, en qué orden, con qué modelos y a qué costo, sin mirar código ni logs
crudos. Forzar una tasa de error alta en un entorno de prueba debe disparar la alerta
correspondiente.

Priorizá que la instrumentación no degrade el rendimiento de forma perceptible — medilo antes y
después de instrumentar y reportalo.
```

---

## Fase 8 — Optimización de costos

```
Fase 8: optimización de costos. El sistema es funcional y observable (Fases 1-7). Ahora lo
hacemos más eficiente en tokens y lo dejamos listo para operar con modelos de pago si hace falta.

Necesito:
1. Compactación automática de contexto: cuando el historial de mensajes de un run supera un
   umbral de tokens configurable, resumirlo automáticamente (usando la capability summarization
   del Model Router) y reemplazarlo por el resumen + los últimos N mensajes crudos.
2. Cache de resultados de herramientas en Redis con TTL — en particular, no re-ejecutar tests si
   el código no cambió desde el último run. Tiene que invalidarse correctamente ante cualquier
   cambio de archivo relevante; priorizá la correctitud de la invalidación sobre la agresividad
   del cache.
3. Selección cost-aware en ModelRouter.select(): usar el modelo más barato que cumpla la
   capability primero, escalando a uno más caro solo si el resultado no pasa validación (por
   ejemplo, JSON malformado repetido, o tests que siguen fallando tras varios intentos con el
   modelo barato).
4. Límite de costo configurable por run (max_cost_usd), que corte la ejecución de forma
   controlada (no un crash) si se supera, dejando el estado parcial auditado.
5. Endpoint de reporte de costos por proyecto/usuario, y su correspondiente panel en Grafana.
6. Paralelizar en el Planner las subtareas que no tengan dependencias entre sí, con un mecanismo
   de bloqueo por archivo/subtarea para evitar condiciones de carrera cuando dos agentes tocan
   el mismo archivo a la vez.

Criterio de aceptación: un run que reutiliza resultados cacheados debe ser medible y
demostrablemente más rápido/barato que uno sin cache (mostralo con un benchmark simple). Un run
que supera max_cost_usd debe cortarse de forma controlada y quedar auditado en run_checkpoints.

Empezá por el mecanismo de invalidación de cache antes que por la paralelización — es el más
riesgoso si sale mal.
```

---

## Fase 9 — Producción

```
Fase 9: producción. El sistema está completo funcionalmente (Fases 1-8). Ahora lo llevamos a un
estado desplegable, seguro y bien documentado.

Necesito:
1. Hardening de seguridad: revisión de que ningún secreto esté commiteado, rotación de API keys
   implementada, rate limiting por usuario activo en todos los endpoints relevantes, y correr
   pip-audit sobre las dependencias actuales del proyecto, resolviendo lo que aparezca.
2. Pipeline de CI con GitHub Actions: lint, tests unitarios e integración en cada PR, build de
   las imágenes Docker, y un job E2E que corra el pipeline completo contra el repo fixture de
   la Fase 5 en un schedule nocturno.
3. Manifiestos Kubernetes iniciales en infra/k8s/: Deployments para api y worker, HPA vía KEDA
   sobre la profundidad de la cola de Redis, como demostración de la ruta de evolución (no hace
   falta desplegarlos contra un clúster real si no hay uno disponible, pero deben ser válidos
   sintácticamente y documentar cómo probarlos con kind o minikube).
4. docs/architecture.md final consolidando todas las decisiones, más ADRs en docs/adr/ para las
   decisiones clave que tomamos fase a fase (por ejemplo: "por qué LangGraph y no un grafo
   custom", "por qué pgvector y no una base vectorial dedicada").
5. Checklist de resiliencia ejecutado y documentado: qué pasa si cae Postgres, qué pasa si cae
   Redis, qué pasa si se agotan los rate limits de todos los proveedores LLM a la vez. El sistema
   debe fallar de forma controlada en los tres casos, nunca silenciosamente.
6. README.md final: instalación completa, arquitectura resumida con referencia al documento
   maestro, y sección honesta de qué partes están realmente listas para producción y cuáles son
   un diseño validado pero no probado a fondo (por ejemplo, si Kubernetes no se probó contra un
   clúster real, decirlo explícitamente).

Criterio de aceptación: clonar el repo desde cero y levantar todo con docker-compose up debe
funcionar en menos de 15 minutos siguiendo únicamente el README. El pipeline de CI debe pasar en
verde en un PR real, incluyendo el job E2E.

Empezá por el checklist de resiliencia (punto 5) antes que por la documentación — quiero
encontrar los problemas reales antes de escribir que el sistema es robusto.
```
