---
name: backend-api
description: 'Use this skill when developing, enhancing, or maintaining the FastAPI REST service in backend/api/app.py or hdfs_client.py. Includes OpenAPI/Swagger documentation best practices, WebHDFS Parquet reading, RespuestaAPI envelope standard, CORS configuration, static mounting, and error handling standards (404, 502, 503). Trigger phrases: "backend api", "fastapi", "rest api", "api endpoint", "openapi docs", "swagger docs", "webhdfs client", "app.py".'
---

# Backend FastAPI REST API Skill

## Overview
This skill governs the development and maintenance of the FastAPI application located in `backend/api/app.py` and its WebHDFS client [`hdfs_client.py`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/backend/api/hdfs_client.py). The API acts as the single-point consumption server for the frontend dashboard, reading processed Parquet datasets from HDFS and proxying external weather APIs.

---

## 1. Architecture & Core Responsibilities

1. **Direct HDFS Integration**: Reads Parquet partitions directly from HDFS using WebHDFS and PyArrow without touching SQL databases.
2. **Unified Envelope Response Standard (`RespuestaAPI`)**: ALL endpoints return a standardized JSON response envelope:
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
3. **OpenAPI / Swagger UI (`/docs`)**: Maintains complete OpenAPI documentation with Markdown summaries, generic `RespuestaAPI[T]` models, and interactive example schemas (`json_schema_extra`).
4. **Structured Error Contract**:
   Any raised `HTTPException` is caught by the exception handler and formatted into `RespuestaAPI`:
   - `404 Not Found`: Returned when requested HDFS partitions, dates, or legacy files do not exist (`tipo: RECURSO_NO_ENCONTRADO`).
   - `502 Bad Gateway`: Returned when an upstream API (e.g., OpenWeatherMap) fails (`tipo: PROVEEDOR_NO_DISPONIBLE`).
   - `503 Service Unavailable`: Returned when WebHDFS is unreachable (`tipo: SERVICIO_HDFS_NO_DISPONIBLE`).

---

## 2. Endpoint Decorator & Pydantic Schema Guidelines

Every route created in [`backend/api/app.py`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/backend/api/app.py) MUST return `_respuesta_exitosa(...)`:

```python
@app.get(
    "/api/recurso/ejemplo",
    response_model=RespuestaAPI[RespuestaModelo],
    tags=["riesgo"],
    summary="Título conciso del endpoint",
    description="Explicación detallada en Markdown de la lógica del endpoint.",
    response_description="Descripción de la respuesta exitosa envuelta en RespuestaAPI.",
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

---

## 3. WebHDFS Reading & Caching Rules

- **Client Re-use**: Access WebHDFS via `_client()` in [`hdfs_client.py`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/backend/api/hdfs_client.py).
- **Process In-Memory Caching**: Use `@lru_cache(maxsize=1)` for static CSV reference files.
- **Deduplicación de Streaming**: Always apply `_ultimo_por_zona(df)` to select the latest `epoch_id` per `zona_id` from PySpark streaming outputs.

---

## 4. Key Files

- **Servidor Principal**: [`backend/api/app.py`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/backend/api/app.py)
- **Cliente WebHDFS**: [`backend/api/hdfs_client.py`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/backend/api/hdfs_client.py)
- **Cliente JavaScript Frontend**: [`frontend/js/api/client.js`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/frontend/js/api/client.js)

---

## 5. Verification Checklist

When adding or modifying API endpoints:
- [ ] Test python route loading: `python -c "from api.app import app"`
- [ ] Verify OpenAPI schema validity: `python -c "from api.app import app; app.openapi()"`
- [ ] Ensure non-200 HTTP responses raise standard `HTTPException` with explicit `detail`.
