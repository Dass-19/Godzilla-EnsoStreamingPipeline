---
name: backend-api
description: 'Use this skill when developing, enhancing, or maintaining the FastAPI REST service in backend/api/app.py or hdfs_client.py. Includes OpenAPI/Swagger documentation, WebHDFS Parquet reading, the RespuestaAPI envelope, and error-handling conventions (404, 502, 503). Trigger phrases: "backend api", "fastapi", "rest api", "api endpoint", "openapi docs", "swagger docs", "webhdfs client", "app.py".'
---

# Backend FastAPI REST API Skill

## Overview
Governs [backend/api/app.py](../../../backend/api/app.py) and its WebHDFS client
[hdfs_client.py](../../../backend/api/hdfs_client.py). Read-only API: it reads processed Parquet from
HDFS, imports `risk_index.py`/`zonas_guayaquil.csv` from `backend/spark/` for the in-memory simulator, and
proxies OpenWeatherMap so the API key never reaches the frontend.

---

## 1. Architecture & Core Responsibilities

1. **Direct HDFS reads**: via `hdfs_client.get_client()` (WebHDFS, pure-Python `hdfs` package) + pandas —
   no PyArrow/native libhdfs, no SQL database.
2. **Unified envelope (`RespuestaAPI[T]`)**: every endpoint returns this shape, built by
   `_respuesta_exitosa(data, fuente=...)`:
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
3. **OpenAPI docs**: `response_model=RespuestaAPI[...]`, `summary`/`description` in Markdown, and
   `responses={...}` documenting the non-200 cases.
4. **Structured errors**: the global `@app.exception_handler(HTTPException)` reformats any raised
   `HTTPException` into the same `RespuestaAPI` envelope, tagging it with a `tipo` string:
   - `404` → `RECURSO_NO_ENCONTRADO` (helper `_sin_datos(detalle)`) — requested HDFS path/date/legacy
     file doesn't exist.
   - `502` → `PROVEEDOR_NO_DISPONIBLE` — an upstream API (OpenWeatherMap) failed.
   - `503` → `SERVICIO_HDFS_NO_DISPONIBLE` (helper `_hdfs_caido(error)`) — WebHDFS unreachable.

---

## 2. Endpoint pattern

```python
@app.get(
    "/api/recurso/ejemplo",
    response_model=RespuestaAPI[RespuestaModelo],
    tags=["riesgo"],
    summary="Título conciso del endpoint",
    description="Explicación detallada en Markdown de la lógica del endpoint.",
    responses={
        404: {"model": RespuestaAPI[None], "description": "Recurso ausente."},
        503: {"model": RespuestaAPI[None], "description": "HDFS inalcanzable."},
    },
)
def mi_endpoint(
    parametro_id: str = Path(..., description="ID del parámetro", example="ZONA_001"),
    limite: int = Query(10, ge=1, le=100, description="Límite de resultados", example=10),
):
    data = fetch_datos(parametro_id, limite)
    return _respuesta_exitosa(data, fuente="/enso_data/ejemplo")
```

`ZonaRiesgo` (and any other response model) is a **filter on output**: a field not declared there is
silently dropped by FastAPI even if the underlying dict has it — when the risk row gains a new field
upstream, add it to the response model too, or it never reaches the frontend.

---

## 3. WebHDFS Reading & Caching Rules

- **Client reuse**: `_client()` in `app.py` is a thin wrapper over `get_client(webhdfs_url, user)` from
  [hdfs_client.py](../../../backend/api/hdfs_client.py), which is itself `@lru_cache(maxsize=1)`.
- **Static reference data**: `_zonas_referencia()` (reads `zonas_guayaquil.csv`) is also
  `@lru_cache(maxsize=1)` — editing the CSV requires an API restart to see the change.
- **Streaming dedup**: always apply `_ultimo_por_zona(df)` to PySpark streaming output before returning
  it — it sorts by `calculado_en`, drops duplicate `(zona_id, epoch_id)` (an `append` retry from
  `foreachBatch` isn't idempotent), then keeps the latest row per `zona_id`.
- `hdfs_client.py`'s own job is narrower than `app.py`'s usage of it: it translates "path doesn't exist"
  into `FileNotFoundError` and caps how many date partitions get read — the response envelope and error
  codes live in `app.py`, not there.

---

## 4. Key Files

- **Servidor Principal**: [backend/api/app.py](../../../backend/api/app.py)
- **Cliente WebHDFS**: [backend/api/hdfs_client.py](../../../backend/api/hdfs_client.py)
- **Modelo de Riesgo (importado en memoria)**: [backend/spark/risk_index.py](../../../backend/spark/risk_index.py)
- **Cliente JavaScript Frontend**: [frontend/js/api/client.js](../../../frontend/js/api/client.js)

---

## 5. Verification Checklist

- [ ] `SPARK_APP_DIR=backend/spark uvicorn api.app:app --reload --port 8000` boots without import errors.
- [ ] `python -c "from api.app import app; app.openapi()"` — OpenAPI schema builds.
- [ ] Every non-200 path raises `HTTPException` with an explicit `detail` (never a bare exception).
- [ ] A new field on a risk/zone row is added to the matching Pydantic response model, not just to the
      underlying dict — otherwise FastAPI drops it silently.
