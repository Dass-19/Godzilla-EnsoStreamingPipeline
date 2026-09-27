---
id: 20260927145522
type: plan
status: active
priority: high
tags: [plan/aos, plan/architecture]
created: 2026-09-27
---

# Plan: Inicialización y Auditoría del AI-AGENT-AOS

> **Objetivo (Definition of Done)**: Establecer la arquitectura completa del Agent Operating System en `/ai-agent-aos/`, verificando que todos los agentes, skills, hooks, ADRs, base de conocimiento y scripts ejecutables estén sincronizados y probados con éxito.

## Contexto y Archivos Afectados
- Archivos creados:
  - `ai-agent-aos/00-INDEX.md`
  - `ai-agent-aos/mcp-config.json`
  - `ai-agent-aos/knowledge/*.md` (backend, frontend, security, gotchas)
  - `ai-agent-aos/agents/*.md` (reviewer, refactorer, qa-tester, data-engineer)
  - `ai-agent-aos/skills/specs/*.md` y `ai-agent-aos/skills/bin/*.py`
  - `ai-agent-aos/hooks/*.md` y `ai-agent-aos/hooks/git-hooks/*.sh`
  - `ai-agent-aos/decisions/*.md` (ADR-001 a ADR-004)
- ADRs vinculados: [[ADR-001-plantilla]], [[ADR-002-degradacion-explicita-no-mock-datos]], [[ADR-003-webhdfs-puro-sin-libhdfs]], [[ADR-004-modelo-riesgo-compuesto-no-lineal]]
- Gotchas vinculados: [[gotcha-datetime-utc-py310]], [[gotcha-webhdfs-append-vs-chunks]], [[gotcha-kafka-message-max-bytes]], [[gotcha-inamhi-date-parsing]]

## Fases de Ejecución Atómica

- [x] **Fase 1: Estructura Base y Configuración MCP**
  - [x] Crear `ai-agent-aos/mcp-config.json` con servidor filesystem.
  - [x] Crear `ai-agent-aos/00-INDEX.md` como mapa de orquestación raíz.
- [x] **Fase 2: Base de Conocimiento y Gotchas**
  - [x] Redactar `knowledge/backend.md`, `knowledge/frontend.md`, `knowledge/security.md`.
  - [x] Documentar notas atómicas en `knowledge/gotchas/`.
- [x] **Fase 3: Perfiles de Sub-Agentes y Roles**
  - [x] Crear `agents/reviewer.md`, `agents/refactorer.md`, `agents/qa-tester.md`, `agents/data-engineer.md`.
- [x] **Fase 4: Skills y Scripts Ejecutables**
  - [x] Definir especificaciones en `skills/specs/`.
  - [x] Implementar ejecutables cross-platform en `skills/bin/` (`run_smoke_test.py`, `check_lint.py`, `verify_contracts.py`).
- [x] **Fase 5: Hooks de Ciclo de Vida y ADRs**
  - [x] Documentar `hooks/pre-task.md`, `hooks/post-task.md` y `hooks/git-hooks/pre-commit.sh`.
  - [x] Formalizar registros de decisión arquitectónica `decisions/ADR-001` a `ADR-004`.
- [x] **Fase 6: Verificación y Validación Automatizada**
  - [x] Ejecutar `python ai-agent-aos/skills/bin/run_smoke_test.py`.
  - [x] Ejecutar `python ai-agent-aos/skills/bin/verify_contracts.py`.
  - [x] Ejecutar `python -m pytest -v`.
  - [x] Ejecutar `python -m ruff check ai-agent-aos/`.

## Registro de Bloqueos y Decisiones en Ejecución
- Se implementaron los ejecutables de skills como scripts Python (`.py`) para garantizar ejecución transparente tanto en entornos host Windows como en Linux/CI.
