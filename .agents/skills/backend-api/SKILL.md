---
name: backend-api
description: 'Use this skill when developing, enhancing, or maintaining the FastAPI REST service in backend/api/app.py or hdfs_client.py. Includes OpenAPI/Swagger documentation, WebHDFS Parquet reading, the RespuestaAPI envelope, and error-handling conventions (404, 502, 503). Trigger phrases: "backend api", "fastapi", "rest api", "api endpoint", "openapi docs", "swagger docs", "webhdfs client", "app.py".'
---

# Backend FastAPI REST API Skill

## Overview
Governs the modular FastAPI REST service package in [backend/api/](../../../backend/api/) (`app.py`, `schemas.py`, `helpers.py`, and `routers/`) and its WebHDFS client [hdfs_client.py](../../../backend/api/hdfs_client.py). Read-only API: it reads processed Parquet from HDFS, imports `risk_index.py`/`zonas_guayaquil.csv` from `backend/spark/` for the in-memory simulator, uses `httpx` async client for OpenWeatherMap proxies, and caches frequent HDFS risk queries in memory (15s TTL).

---

## 1. Architecture & Core Responsibilities

1. **Direct HDFS reads**: via `hdfs_client.get_client()` (WebHDFS, pure-Python `hdfs` package) + pandas —
   no PyArrow/native libhdfs, no SQL database.
2. **Modularized APIRouter structure**:
   - `app.py`: Minimal entrypoint (~220 lines) registering CORS middleware, exception handlers, static mounts, HTTP lifespan lifecycle, and domain routers.
   - `schemas.py`: Unified Pydantic response models (`RespuestaAPI[T]`, `MetaAPI`, `ErrorInfo`) and domain schemas (`EstadoENSO`, `MareaActual`, `RegistroHistoricoZona`, etc.) using `ConfigDict(extra="allow")`.
   - `helpers.py`: Common helpers (`respuesta_exitosa`, `sin_datos`, `hdfs_caido`), HDFS readers (`leer_telemetria_raw`, `leer_capa_seguraep`), in-memory `CacheTTL` (15s), and `httpx.AsyncClient` lifecycle.
   - `routers/`: 9 routers split by domain (`salud.py`, `riesgo.py`, `enso.py`, `hidrologia.py`, `clima.py`, `eventos.py`, `capas.py`, `alertas.py`, `observabilidad.py`).
3. **Unified envelope (`RespuestaAPI[T]`)**: every endpoint returns this shape, built by
   `respuesta_exitosa(data, fuente=...)`:
   ```json
   {
     "status": "success",
     "data": { ... },
     "error": null,
     "meta": {
       "api_version": "1.2.0",
       "timestamp": "2026-08-01T13:20:00Z",
       "fuente": "/enso_data/processed/indice_riesgo",
       "total_registros": 45
     }
   }
   ```
4. **OpenAPI docs**: `response_model=RespuestaAPI[...]`, `summary`/`description` in Markdown, and
   `responses={...}` documenting non-200 cases.
5. **Structured errors**: global `@app.exception_handler(HTTPException)` reformats any raised
   `HTTPException` into the same `RespuestaAPI` envelope, tagging it with a `tipo` string:
   - `404` → `RECURSO_NO_ENCONTRADO` (helper `sin_datos(detalle)`) — requested HDFS path/date/file doesn't exist.
   - `502` → `PROVEEDOR_NO_DISPONIBLE` — upstream API (OpenWeatherMap) failed.
   - `503` → `SERVICIO_HDFS_NO_DISPONIBLE` (helper `hdfs_caido(error)`) — WebHDFS unreachable.

---

## 2. Key Files

- **Configuración y Entrypoint**: [backend/api/app.py](../../../backend/api/app.py)
- **Esquemas y Envelopes Pydantic**: [backend/api/schemas.py](../../../backend/api/schemas.py)
- **Utilidades, Caché y HTTP Async**: [backend/api/helpers.py](../../../backend/api/helpers.py)
- **Cliente WebHDFS**: [backend/api/hdfs_client.py](../../../backend/api/hdfs_client.py)
- **Routers por Dominio**: [backend/api/routers/](../../../backend/api/routers/)
- **Modelo de Riesgo (importado en memoria)**: [backend/spark/risk_index.py](../../../backend/spark/risk_index.py)
- **Cliente JavaScript Frontend**: [frontend/js/api/client.js](../../../frontend/js/api/client.js)


---

## 5. Verification Checklist

- [ ] `SPARK_APP_DIR=backend/spark uvicorn api.app:app --reload --port 8000` boots without import errors.
- [ ] `python -c "from api.app import app; app.openapi()"` — OpenAPI schema builds.
- [ ] Every non-200 path raises `HTTPException` with an explicit `detail` (never a bare exception).
- [ ] A new field on a risk/zone row is added to the matching Pydantic response model, not just to the
      underlying dict — otherwise FastAPI drops it silently.
