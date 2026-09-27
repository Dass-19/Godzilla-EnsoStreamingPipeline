---
id: 20260927145513
type: skill-spec
status: evergreen
name: "api-smoke-test"
runtime: python3
entrypoint: "ai-agent-aos/skills/bin/run_smoke_test.py"
inputs:
  - name: verbose
    type: boolean
    description: "Modo verboso para imprimir payloads de respuesta"
    required: false
outputs:
  format: "json | stdout | exit-code"
created: 2026-09-27
---

# Skill: API Smoke Test

> **Propósito**: Ejecutar una batería rápida de pruebas de integración HTTP en memoria sobre la API FastAPI utilizando `TestClient`, verificando endpoints clave, enrutamiento, códigos de respuesta y envoltura `RespuestaAPI`.

## Cuándo Usar
Ejecutar antes de comitear cambios en `backend/api/` o al validar la integración con el frontend.

## Comando de Ejecución
```bash
python ai-agent-aos/skills/bin/run_smoke_test.py
```

## Manejo de Errores y Retornos
- **Exit Code 0**: Todos los endpoints evaluados respondieron con el formato esperado.
- **Exit Code 1**: Uno o más endpoints fallaron o rompieron el envelope `RespuestaAPI`.
