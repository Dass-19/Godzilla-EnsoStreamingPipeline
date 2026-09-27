---
id: 20260927145516
type: hook-spec
status: evergreen
title: "Pre-Task Hook: Protocolo Obligatorio Antes de Editar Código"
created: 2026-09-27
---

# Pre-Task Hook

> **Propósito**: Checklist de ejecución estricta que todo agente o desarrollador debe realizar **antes** de proponer o realizar cualquier cambio en el repositorio.

---

## Checklist Pre-Tarea

- [ ] **1. Consultar el Mapa Raíz**: Leer [`ai-agent-aos/00-INDEX.md`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/ai-agent-aos/00-INDEX.md) para sincronizar directrices y arquitectura general.
- [ ] **2. Identificar el Plan Activo**: Revisar [`ai-agent-aos/plans/active/`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/ai-agent-aos/plans/active/) y tomar únicamente la siguiente tarea pendiente `[ ]` en la fase correspondiente.
- [ ] **3. Consultar la Base de Conocimiento y Gotchas**:
  - Revisar [`ai-agent-aos/knowledge/`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/ai-agent-aos/knowledge/) según el dominio de trabajo (`backend.md`, `frontend.md`, `security.md`).
  - Inspeccionar [`ai-agent-aos/knowledge/gotchas/`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/ai-agent-aos/knowledge/gotchas/) para evitar reincidir en errores conocidos.
- [ ] **4. Validar Existencia y Estado Real de Archivos**:
  - Inspeccionar el código real antes de asumir cambios (mediante `view_file` o herramientas MCP de filesystem).
  - Nunca basarse exclusivamente en recuerdos o supuestos desactualizados.
