---
id: 20260927152009
type: index
status: evergreen
title: "AI-AGENT-AOS — Mapa de Contexto y Orquestación Principal"
created: 2026-09-27
updated: 2026-09-27
---

# AI-AGENT-AOS (Agent Operating System)

> **Directorio Canónico Único**: `/ai-agent-aos/`  
> **Proyecto**: Godzilla-EnsoStreamingPipeline  
> **Propósito**: Centralizar y orquestar directrices, sub-agentes, capacidades ejecutables (skills), hooks de ciclo de vida, registros de decisión arquitectónica (ADRs), base de conocimiento viva y planes de trabajo.

---

## 1. Principios Rectores del Repositorio

1. **Integridad y Degradación Explícita**: Si una fuente remota falla, **nunca inventar datos artificiales**. Marcar explícitamente `origen="real"` vs `origen="default"` a través de [`backend/contracts.py`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/backend/contracts.py).
2. **Contrato de Datos Canónico Único**: Cualquier cambio en esquemas debe realizarse en `contracts.py` sin dependencias externas pesadas (`pyspark`, `kafka`).
3. **Zero-Build Step en Frontend**: Frontend basado puramente en ES Modules nativos (`index.html`, `styles.css`, `frontend/js/`) con política estricta de cache-busting `?v=N`.
4. **WebHDFS Puro en Backend**: FastAPI lee archivos Parquet directamente de NameNode vía WebHDFS (`hdfs_client.py`) sin binarios C nativos (`libhdfs`).
5. **Zero HTTP Mocking en Tests**: Se prueban transformaciones puras contra fixtures reales sin simular clientes HTTP.
6. **Política de Commits**: El agente de IA **NUNCA ejecuta `git commit` ni `git push`**. Ejecuta las validaciones automáticas y **sugiere el mensaje de commit** al usuario para su aplicación manual.

---

## 2. Mapa Completo del Sistema AOS

```
ai-agent-aos/
├── 00-INDEX.md                  # Punto de entrada raíz (este archivo)
├── mcp-config.json              # Configuración de MCP Server Filesystem
│
├── knowledge/                   # Base de conocimiento viva
│   ├── backend.md               # FastAPI, WebHDFS, Spark Streaming, Kafka Producers
│   ├── frontend.md              # MapLibre GL, ECharts, Chart.js, ES Modules
│   ├── security.md              # Políticas de seguridad, .env, Service Accounts, CORS
│   ├── testing.md               # Convenciones de testing, zero-mocking y fixtures
│   └── gotchas/                 # Gotchas resueltos y trampas del stack
│       ├── gotcha-datetime-utc-py310.md
│       ├── gotcha-webhdfs-append-vs-chunks.md
│       ├── gotcha-kafka-message-max-bytes.md
│       └── gotcha-inamhi-date-parsing.md
│
├── agents/                      # Perfiles de sub-agentes especializados
│   ├── reviewer.md              # Auditor de código, tipado y seguridad
│   ├── refactorer.md            # Especialista en optimización y modularidad
│   ├── qa-tester.md             # Automatización y pruebas de integración
│   └── data-engineer.md         # Especialista en Spark, Kafka, HDFS y contratos
│
├── skills/                      # Capacidades y herramientas ejecutables
│   ├── specs/                   # Especificaciones de tools para LLMs
│   │   ├── backend-api.md       # Desarrollo y routers de FastAPI
│   │   ├── backend-producers.md # Kafka producers y ciclo run_loop
│   │   ├── backend-spark.md     # Spark Structured Streaming e índice de riesgo
│   │   ├── frontend-design.md   # MapLibre GL, diseño y cache-busting
│   │   ├── testing.md           # Estándares de testing y pruebas pytest
│   │   ├── skill-creator.md     # Meta-skill para estandarizar nuevas tools
│   │   ├── git-atomic-commit.md # Sugerencia de commits atómicos al usuario
│   │   ├── api-smoke-test.md    # Smoke test rápido de endpoints REST
│   │   ├── hdfs-integrity-check.md # Verificación de integridad en HDFS
│   │   └── run-pipeline-tests.md # Ejecución orquestada de pytest
│   └── bin/                     # Scripts ejecutables CLI cross-platform
│       ├── run_smoke_test.py
│       ├── check_lint.py
│       └── verify_contracts.py
│
├── hooks/                       # Automatización del ciclo de vida
│   ├── pre-task.md              # Protocolo previo a edición de código
│   ├── post-task.md             # Protocolo posterior y validaciones obligatorias
│   └── git-hooks/
│       └── pre-commit.sh
│
├── decisions/                   # Architecture Decision Records (ADR)
│   ├── ADR-001-plantilla.md
│   ├── ADR-002-degradacion-explicita-no-mock-datos.md
│   ├── ADR-003-webhdfs-puro-sin-libhdfs.md
│   └── ADR-004-modelo-riesgo-compuesto-no-lineal.md
│
└── plans/                       # Gestión de tareas y backlog
    ├── active/                  # Planes de trabajo en curso
    │   └── plan-001-inicializacion-aos.md
    └── archive/                 # Planes completados y consolidados
```

---

## 3. Protocolo de Ejecución para Agentes

1. **Antes de iniciar cualquier tarea**: Ejecutar el checklist obligatorio de [`hooks/pre-task.md`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/ai-agent-aos/hooks/pre-task.md).
2. **Durante la tarea**:
   - Consultar la base de conocimiento en [`knowledge/`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/ai-agent-aos/knowledge/).
   - Utilizar las especificaciones de skills en [`skills/specs/`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/ai-agent-aos/skills/specs/).
   - Evitar trampas ya documentadas en [`knowledge/gotchas/`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/ai-agent-aos/knowledge/gotchas/).
   - Respetar los ADRs vigentes en [`decisions/`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/ai-agent-aos/decisions/).
3. **Antes de finalizar**: Ejecutar el checklist obligatorio de [`hooks/post-task.md`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/ai-agent-aos/hooks/post-task.md) (incluyendo la sugerencia de commit sin auto-commitear).
