---
id: 20260927152001
type: hook-spec
status: evergreen
title: "Post-Task Hook: Protocolo Obligatorio Antes de Cerrar Respuestas"
created: 2026-09-27
updated: 2026-09-27
---

# Post-Task Hook

> **Propósito**: Checklist de validación obligatoria que todo agente debe cumplir **antes** de dar por concluida una interacción o tarea.

---

## Checklist Post-Tarea

- [ ] **1. Ejecución de Tests y Linters**:
  - Ejecutar la suite de pruebas unitarias y de contratos:
    ```bash
    python -m pytest -v
    ```
  - Ejecutar el linter para asegurar estilo y formato limpio:
    ```bash
    python -m ruff check .
    ```

- [ ] **2. Actualizar el Plan Activo**:
  - Marcar con `[x]` las tareas completadas en [`ai-agent-aos/plans/active/`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/ai-agent-aos/plans/active/).
  - Si el plan se completó en su totalidad, moverlo a [`ai-agent-aos/plans/archive/`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/ai-agent-aos/plans/archive/).

- [ ] **3. Documentar Nuevos Gotchas**:
  - Si durante la tarea se descubrió un comportamiento inesperado, bug de librería, limitación de versiones o peculiaridad del stack, redactar inmediatamente una nota atómica en [`ai-agent-aos/knowledge/gotchas/`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/ai-agent-aos/knowledge/gotchas/).

- [ ] **4. Registrar Decisiones Arquitectónicas (ADR)**:
  - Si se tomó una decisión de diseño estructural, agregar un nuevo ADR en [`ai-agent-aos/decisions/`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/ai-agent-aos/decisions/).

- [ ] **5. Sugerir Commits al Usuario (NUNCA Auto-Commitear ni Pushear)**:
  - **PROHIBICIÓN**: El agente jamás debe ejecutar `git commit` ni `git push`.
  - **ACCIÓN**: Sugerir al usuario el comando exacto de `git commit -m "..."` siguiendo la convención Conventional Commits para que él lo ejecute de manera manual e informada.
