---
id: 20260927145515
type: skill-spec
status: evergreen
name: "run-pipeline-tests"
runtime: python3 / pytest
entrypoint: "pytest -v"
inputs:
  - name: test_filter
    type: string
    description: "Filtro de nombres de test o archivo específico (ej: tests/test_contracts.py)"
    required: false
outputs:
  format: "stdout | exit-code"
created: 2026-09-27
---

# Skill: Run Pipeline Tests

> **Propósito**: Ejecutar la suite automatizada de pruebas con pytest para verificar contratos, interpolación, cálculo de riesgo y endpoints.

## Cuándo Usar
Obligatorio durante el `post-task.md` y antes de cualquier commit o merge.

## Comando de Ejecución
```bash
python -m pytest -v
```

O para un archivo específico:
```bash
python -m pytest tests/test_contracts.py -v
```
