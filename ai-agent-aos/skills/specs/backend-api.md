---
id: 20260927152002
type: skill-spec
status: evergreen
name: "backend-api"
runtime: python3 / fastapi
entrypoint: "uvicorn api.app:app"
inputs:
  - name: endpoint_path
    type: string
    description: "Ruta del endpoint de FastAPI a desarrollar o mantener"
    required: false
outputs:
  format: "json / OpenAPI / RespuestaAPI[T]"
created: 2026-09-27
updated: 2026-09-27
---

# Skill: Backend FastAPI REST API

> **Propósito**: Guiar el desarrollo, refactorización y mantenimiento del servicio FastAPI REST en [`backend/api/`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/backend/api/), su cliente WebHDFS [`hdfs_client.py`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/backend/api/hdfs_client.py), documentación OpenAPI y envoltura `RespuestaAPI[T]`.

---

## 1. Arquitectura y Responsabilidades Clave

1. **Lectura Directa desde WebHDFS**:
   - Vía `hdfs_client.get_client()` (`InsecureClient` contra `http://namenode:9870`).
   - Sin binarios C nativos ni dependencias de `libhdfs` / JVM en la API.
   - Conversión de Parquets a `pandas.DataFrame` con `io.BytesIO` y `pyarrow`.
2. **Estructura Modular de Routers (`backend/api/routers/`)**:
   - `salud.py`: Healthcheck de operatividad.
   - `riesgo.py`: Riesgo actual por zonas, histórico, simulador what-if y pronóstico a 24h.
   - `enso.py`: Estado macro y telemetría oceánica.
   - `hidrologia.py`: Mareas, embalses y caudales fluviales.
   - `clima.py`: Telemetría meteorológica y proxies seguros hacia OpenWeatherMap.
   - `eventos.py`: Emergencias reportadas por SGR.
   - `capas.py`: GeoJSON estáticos (zonas, sectores, vías, albergues).
   - `alertas.py`: Boletines SNGR.
   - `observabilidad.py`: Auditoría de logs de productores archivados en HDFS.
3. **Envelope Unificado (`RespuestaAPI[T]`)**:
   - Generado con `respuesta_exitosa(data, fuente=...)`:
     ```json
     {
       "status": "success",
       "data": { ... },
       "error": null,
       "meta": {
         "api_version": "1.2.0",
         "timestamp": "2026-08-01T13:20:00Z",
         "fuente": "/enso_data/processed/indice_riesgo",
         "total_registros": 22
       }
     }
     ```
4. **Manejo Estructurado de Errores**:
   - `404` $\rightarrow$ `RECURSO_NO_ENCONTRADO` (`sin_datos(detalle)`).
   - `502` $\rightarrow$ `PROVEEDOR_NO_DISPONIBLE` (fallos en upstream como OpenWeatherMap).
   - `503` $\rightarrow$ `SERVICIO_HDFS_NO_DISPONIBLE` (`hdfs_caido(error)`).

---

## 2. Checklist de Verificación
- [ ] `python ai-agent-aos/skills/bin/run_smoke_test.py` pasa con código de salida 0.
- [ ] Todo nuevo campo devuelto en una respuesta está registrado en el modelo Pydantic en `schemas.py`.
- [ ] Ningún endpoint lanza excepciones no controladas (todas mapean a `HTTPException` o al envelope `RespuestaAPI`).
