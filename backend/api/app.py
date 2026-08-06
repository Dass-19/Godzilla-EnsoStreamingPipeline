"""
API de solo lectura sobre los datos que Spark deja en HDFS zona `processed`
(y algunos crudos de `raw` para series de tiempo simples). Es el punto de
consumo único para el dashboard: el frontend nunca habla con HDFS
directamente, ni con APIs de terceros que requieran una clave.

Variables de entorno:
    WEBHDFS_URL             ej. "http://namenode:9870"
    HDFS_USER               usuario HDFS a usar en las peticiones
    HDFS_BASE_PATH          ej. "/enso_data"
    SPARK_APP_DIR           dónde vive `risk_index.py` (por defecto "/spark")
    GEO_REF_PATH            CSV de zonas; por defecto, dentro de SPARK_APP_DIR
    CORS_ORIGINS            orígenes permitidos, separados por coma
    OPENWEATHERMAP_API_KEY  clave para los proxies `/api/clima/punto` y
                            `/api/clima/tiles/...`

Ejecutar en desarrollo (desde la raíz del repo, no desde `api/`):
    SPARK_APP_DIR=backend/spark uvicorn api.app:app --reload --port 8000
"""

from __future__ import annotations

import datetime
import logging
import pathlib
from datetime import UTC

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

try:
    from .helpers import (
        CORS_ORIGINS,
        RAIZ_REPO,
        _CacheTTL,
        _cache_hdfs,
        cerrar_http_client,
        obtener_http_client,
    )
    from .routers import (
        alertas,
        capas,
        clima,
        enso,
        eventos,
        hidrologia,
        observabilidad,
        riesgo,
        salud,
    )
except ImportError:
    from helpers import (
        CORS_ORIGINS,
        RAIZ_REPO,
        _CacheTTL,
        _cache_hdfs,
        cerrar_http_client,
        obtener_http_client,
    )
    from routers import (
        alertas,
        capas,
        clima,
        enso,
        eventos,
        hidrologia,
        observabilidad,
        riesgo,
        salud,
    )


logger = logging.getLogger("enso.api")

# ---------------------------------------------------------------------------
# Configuración de Metadatos OpenAPI / Swagger
# ---------------------------------------------------------------------------

tags_metadata = [
    {
        "name": "salud",
        "description": "Verificación del estado operativo de la API REST.",
    },
    {
        "name": "riesgo",
        "description": (
            "Monitoreo, pronóstico y simulación del índice de riesgo de "
            "inundación por sectores de Guayaquil."
        ),
    },
    {
        "name": "enso",
        "description": (
            "Indicadores oceánicos y atmosféricos del Fenómeno El Niño "
            "(SST NOAA, Anomalías Niño 1+2 / 3.4)."
        ),
    },
    {
        "name": "hidrologia",
        "description": (
            "Entradas hidrológicas reales del índice de riesgo, leídas desde su "
            "último registro archivado en HDFS: marea (INOCAR), embalse "
            "Daule-Peripa (CELEC, solo contexto) y caudal del río Guayas (GEOGLOWS)."
        ),
    },
    {
        "name": "clima",
        "description": (
            "Telemetría climática archivada (GEE, NASA POWER, Open-Meteo, "
            "OpenWeatherMap, INAMHI, boyas NDBC): última lectura conocida desde "
            "HDFS, no una consulta en tiempo real al proveedor."
        ),
    },
    {
        "name": "clima_proxy",
        "description": (
            "Proxies en vivo a OpenWeatherMap — no leen HDFS, consultan al "
            "proveedor en cada request. Pueden devolver 502 si OpenWeatherMap "
            "falla, algo que no le pasa a los endpoints de `clima`."
        ),
    },
    {
        "name": "eventos",
        "description": "Eventos de lluvia e incidentes reportados por la SGR.",
    },
    {
        "name": "capas_geograficas",
        "description": (
            "Capas GeoJSON estáticas o semi-estáticas para el mapa: parroquias, "
            "sectores, vías inundables/vulnerables, zonas seguras/inundables y "
            "el contorno del cantón Guayaquil (OSM)."
        ),
    },
    {
        "name": "alertas",
        "description": (
            "Boletines y alertas oficiales emitidas por la Secretaría Nacional "
            "de Gestión de Riesgos (SNGR)."
        ),
    },
    {
        "name": "observabilidad",
        "description": (
            "Auditoría de los logs que cada producer sube periódicamente a "
            "HDFS (ver HandlerHDFS en backend/producers/common/kafka_client.py)."
        ),
    },
]

app = FastAPI(
    title="ENSO Godzilla Streaming Pipeline - API REST",
    summary="API de monitoreo y predicción del riesgo de inundación para Guayaquil ante el Fenómeno El Niño.",
    description="""
### 🌊 Plataforma de Monitoreo e Índice de Riesgo ENSO (Guayaquil)

Esta API sirve como el **punto de consumo unificado** para el dashboard interactivo de monitoreo de inundaciones. Todos los endpoints retornan una envoltura estandarizada `RespuestaAPI`, con la única excepción de `clima_proxy` → `/api/clima/tiles/...`, que devuelve una imagen PNG cruda para consumo directo de MapLibre/Leaflet.

#### ⚙️ Arquitectura del Pipeline:
1. **Productores Python (Kafka)**: Ingestan telemetría en vivo desde NOAA, INOCAR, INAMHI, CELEC, OpenWeatherMap y GeoGLOWS.
2. **PySpark Streaming**: Procesa micro-batches, calcula el índice multidimensional de riesgo por zona e interpola datos espaciales.
3. **HDFS (Storage)**: Almacena particiones de datos crudos (`raw`) y procesados (`processed`) en formato Parquet.
4. **FastAPI (REST)**: Lee directamente desde HDFS vía WebHDFS y expone endpoints optimizados para el mapa y tableros.
""",
    version="1.2.0",
    docs_url="/docs",
    redoc_url=None,
    openapi_tags=tags_metadata,
    contact={
        "name": "Equipo de Desarrollo Godzilla ENSO",
        "url": "https://github.com/Dass-19/EnsoStreamingPipeline",
    },
    license_info={
        "name": "MIT License",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _iniciar_http():
    await obtener_http_client()


@app.on_event("shutdown")
async def _cerrar_http():
    await cerrar_http_client()


@app.get(
    "/",
    include_in_schema=False,
    summary="Redirige al dashboard",
)
def raiz():
    """GET / → 302 /dashboard para que el usuario aterrice en el panel."""
    return RedirectResponse(url="/dashboard", status_code=302)


# Registrar routers por dominio
app.include_router(salud.router)
app.include_router(riesgo.router)
app.include_router(enso.router)
app.include_router(hidrologia.router)
app.include_router(clima.router)
app.include_router(eventos.router)
app.include_router(capas.router)
app.include_router(alertas.router)
app.include_router(observabilidad.router)

# Montaje de archivos estáticos del Frontend
frontend_path = RAIZ_REPO / "frontend"
if not frontend_path.exists():
    frontend_path = pathlib.Path("/frontend")
if frontend_path.exists():
    logs_path = frontend_path / "logs"
    if logs_path.exists():
        app.mount(
            "/logs",
            StaticFiles(directory=str(logs_path), html=True),
            name="logs",
        )

    app.mount(
        "/dashboard",
        StaticFiles(directory=str(frontend_path), html=True),
        name="frontend",
    )


TIPO_ERROR_POR_STATUS = {
    400: "SOLICITUD_INVALIDA",
    404: "RECURSO_NO_ENCONTRADO",
    500: "ERROR_INTERNO_SERVIDOR",
    502: "PROVEEDOR_NO_DISPONIBLE",
    503: "SERVICIO_HDFS_NO_DISPONIBLE",
}


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Captura cualquier HTTPException y devuelve el formato unificado RespuestaAPI de error."""
    tipo = TIPO_ERROR_POR_STATUS.get(exc.status_code, "ERROR_HTTP")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "data": None,
            "error": {
                "codigo": exc.status_code,
                "tipo": tipo,
                "mensaje": exc.detail,
                "detalle": str(exc.detail),
            },
            "meta": {
                "api_version": "1.2.0",
                "timestamp": datetime.datetime.now(UTC).isoformat(),
                "fuente": None,
                "total_registros": None,
            },
        },
    )
