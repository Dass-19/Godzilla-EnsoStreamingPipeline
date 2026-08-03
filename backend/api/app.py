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

import csv
import json
import logging
import os
import pathlib
import sys
from datetime import UTC, date, datetime
from functools import lru_cache
from typing import Any, Generic, TypeVar

import requests
from fastapi import FastAPI, HTTPException, Path, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from hdfs.util import HdfsError

try:
    from .hdfs_client import (
        get_client,
        read_all_partitions_parquet,
        read_latest_partition_parquet,
    )
except ImportError:
    from hdfs_client import (
        get_client,
        read_all_partitions_parquet,
        read_latest_partition_parquet,
    )
from pydantic import BaseModel, Field

logger = logging.getLogger("enso.api")

WEBHDFS_URL = os.environ.get("WEBHDFS_URL", "http://localhost:9870")
HDFS_USER = os.environ.get("HDFS_USER", "root")
HDFS_BASE = os.environ.get("HDFS_BASE_PATH", "/enso_data")
OPENWEATHERMAP_API_KEY = os.environ.get("OPENWEATHERMAP_API_KEY", "")

RAIZ_REPO = pathlib.Path(__file__).resolve().parent.parent.parent


def _resolver_directorio_spark() -> pathlib.Path:
    """Ubica el paquete de Spark (`risk_index.py` + el CSV de zonas)."""
    candidatos = [
        os.environ.get("SPARK_APP_DIR"),
        RAIZ_REPO / "backend" / "spark",
        pathlib.Path("/app/spark"),
    ]
    for candidato in candidatos:
        if not candidato:
            continue
        ruta = pathlib.Path(candidato).resolve()
        if (ruta / "risk_index.py").exists():
            return ruta
    raise RuntimeError(
        "No se encontró risk_index.py. Definí SPARK_APP_DIR apuntando a backend/spark."
    )


SPARK_APP_DIR = _resolver_directorio_spark()
if str(SPARK_APP_DIR) not in sys.path:
    sys.path.insert(0, str(SPARK_APP_DIR))

from risk_index import calcular_indice_riesgo  # noqa: E402

GEO_REF_PATH = pathlib.Path(
    os.environ.get(
        "GEO_REF_PATH",
        SPARK_APP_DIR / "data" / "geo_ref" / "zonas_guayaquil.csv",
    )
)

CORS_ORIGINS = [
    origen.strip()
    for origen in os.environ.get(
        "CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
    ).split(",")
    if origen.strip()
]

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

frontend_path = RAIZ_REPO / "frontend"
if not frontend_path.exists():
    frontend_path = pathlib.Path("/frontend")
if frontend_path.exists():
    app.mount(
        "/dashboard",
        StaticFiles(directory=str(frontend_path), html=True),
        name="frontend",
    )

# ---------------------------------------------------------------------------
# Esquema de Respuesta Estandarizado (Envelope Pattern)
# ---------------------------------------------------------------------------

T = TypeVar("T")


class MetaAPI(BaseModel):
    api_version: str = Field("1.2.0", description="Versión activa de la API REST", example="1.2.0")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="Marca de tiempo ISO-8601 del servidor API",
        example="2026-08-01T13:20:00Z",
    )
    fuente: str | None = Field(
        None,
        description="Origen HDFS o servicio externo de donde se extrajo la información",
        example="/enso_data/processed/indice_riesgo",
    )
    total_registros: int | None = Field(
        None,
        description="Cantidad de registros o elementos cuando la carga útil es una lista",
        example=45,
    )


class ErrorInfo(BaseModel):
    codigo: int = Field(
        ..., description="Código de estado HTTP del error (404, 502, 503, etc.)", example=404
    )
    tipo: str = Field(
        ..., description="Categorización del tipo de error", example="RECURSO_NO_ENCONTRADO"
    )
    mensaje: str = Field(
        ...,
        description="Mensaje legible de error para el usuario o frontend",
        example="Aún no hay datos de índice de riesgo procesados",
    )
    detalle: str | None = Field(
        None,
        description="Detalle técnico adicional o causa raíz",
        example="No se encontraron particiones Parquet en HDFS",
    )


class RespuestaAPI(BaseModel, Generic[T]):
    status: str = Field(
        "success", description="Estado de la respuesta: 'success' o 'error'", example="success"
    )
    data: T | None = Field(None, description="Carga útil principal de la respuesta")
    error: ErrorInfo | None = Field(None, description="Detalles del error si status == 'error'")
    meta: MetaAPI = Field(
        default_factory=MetaAPI, description="Metadatos contextuales del servidor y pipeline"
    )


def _respuesta_exitosa(
    data: Any,
    fuente: str | None = None,
    total_registros: int | None = None,
) -> dict[str, Any]:
    """Genera la envoltura estandarizada RespuestaAPI para respuestas exitosas."""
    if total_registros is None:
        if isinstance(data, list):
            total_registros = len(data)
        elif isinstance(data, dict) and "zonas" in data and isinstance(data["zonas"], list):
            total_registros = len(data["zonas"])

    return {
        "status": "success",
        "data": data,
        "error": None,
        "meta": {
            "api_version": "1.2.0",
            "timestamp": datetime.now(UTC).isoformat(),
            "fuente": fuente,
            "total_registros": total_registros,
        },
    }


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
                "timestamp": datetime.now(UTC).isoformat(),
                "fuente": None,
                "total_registros": None,
            },
        },
    )


# ---------------------------------------------------------------------------
# Modelos de Datos Internos (Payloads dentro de `data`)
# ---------------------------------------------------------------------------


class ZonaRiesgo(BaseModel):
    zona_id: str = Field(
        ..., description="Identificador único de la zona o sector urbano", example="ZONA_001"
    )
    nombre_sector: str | None = Field(
        None, description="Nombre legible del sector o parroquia", example="Urdesa Central"
    )
    lat_centroide: float | None = Field(
        None, description="Latitud del centroide geográfico", example=-2.167
    )
    lon_centroide: float | None = Field(
        None, description="Longitud del centroide geográfico", example=-79.916
    )
    indice_riesgo: float = Field(
        ..., description="Índice de riesgo ponderado normalizado (0.0 a 1.0)", example=0.74
    )
    nivel_riesgo: str = Field(
        ..., description="Categoría de riesgo: BAJO, MEDIO, ALTO, EXTREMO", example="ALTO"
    )
    precip_acumulada_24h_mm: float | None = Field(
        None, description="Precipitación acumulada en las últimas 24h en mm", example=45.5
    )
    altura_marea_m: float | None = Field(
        None, description="Altura de marea astronómica/observada en metros", example=3.85
    )
    nivel_embalse_msnm: float | None = Field(
        None, description="Nivel del embalse Daule-Peripa en msnm", example=84.2
    )
    origen_precip: str | None = Field(
        None,
        description="Fuente del dato de precipitación (estacion|satelite|respaldo)",
        example="estacion",
    )
    origen_marea: str | None = Field(None, description="Fuente del dato de marea", example="inocar")
    origen_embalse: str | None = Field(
        None, description="Fuente del dato de embalse", example="celec"
    )
    datos_completos: bool | None = Field(
        None,
        description="False si alguna variable utilizó un valor de respaldo por falta de telemetría en vivo.",
        example=True,
    )
    precip_pronostico_24h_mm: float | None = Field(
        None, description="Pronóstico de lluvia a 24 horas", example=55.0
    )
    marea_observada_m: float | None = Field(
        None, description="Marea observada en tiempo real", example=3.90
    )
    caudal_rio_m3s: float | None = Field(
        None, description="Caudal estimado del río Guayas en m3/s", example=1250.0
    )
    saturacion_antecedente_mm: float | None = Field(
        None, description="Índice de humedad antecedente del suelo", example=35.2
    )
    origen_rio: str | None = Field(
        None, description="Fuente del dato de caudal", example="geoglows"
    )
    origen_suelo: str | None = Field(
        None, description="Fuente del dato de saturación del suelo", example="copernicus"
    )
    origen_marea_obs: str | None = Field(
        None, description="Fuente de marea observada", example="inocar_realtime"
    )
    n_estaciones_precip: int | None = Field(
        None, description="Número de estaciones meteorológicas interpoladas", example=4
    )
    poblacion: int | None = Field(None, description="Población estimada en la zona", example=15200)
    exposicion_norm: float | None = Field(
        None, description="Índice de exposición poblacional/infraestructura (0 a 1)", example=0.68
    )
    indice_impacto: float | None = Field(
        None, description="Índice de impacto estimado (Riesgo × Exposición)", example=0.50
    )
    anomalia_nino12_c: float | None = Field(
        None, description="Anomalía de temperatura superficial del mar Niño 1+2 en °C", example=1.8
    )
    origen_enso: str | None = Field(
        None, description="Fuente del indicador ENSO", example="noaa_sst"
    )


class RespuestaZonas(BaseModel):
    actualizado_en: str | None = Field(
        None,
        description="Timestamp ISO-8601 de la última ejecución/batch de Spark Streaming",
        example="2026-08-01T12:00:00Z",
    )
    zonas: list[ZonaRiesgo] = Field(
        ..., description="Lista con el estado y puntuación de riesgo de cada zona urbana"
    )


class ParametrosEscenario(BaseModel):
    precip_24h_mm: float = Field(
        ..., description="Precipitación simulada en mm acumulados en 24h", example=80.0
    )
    altura_marea_m: float = Field(
        ..., description="Altura de marea astronómica simulada en metros", example=4.2
    )
    caudal_rio_m3s: float = Field(
        500.0, description="Caudal del río Guayas simulado en m3/s", example=1800.0
    )
    saturacion_antecedente_mm: float = Field(
        0.0, description="Saturación del suelo antecedente simulada en mm", example=50.0
    )
    anomalia_nino12_c: float = Field(
        0.0, description="Anomalía de TSM en región Niño 1+2 en °C", example=2.5
    )


class RespuestaEscenario(BaseModel):
    parametros: ParametrosEscenario = Field(
        ..., description="Parámetros hipotéticos introducidos en la simulación"
    )
    zonas: list[ZonaRiesgo] = Field(..., description="Evaluación simulada por cada zona urbana")


class ZonaPronostico(BaseModel):
    zona_id: str = Field(..., description="Identificador de la zona urbana", example="ZONA_001")
    nombre_sector: str | None = Field(
        None, description="Nombre legible del sector", example="Urdesa Central"
    )
    lat_centroide: float | None = Field(None, description="Latitud del centroide", example=-2.167)
    lon_centroide: float | None = Field(None, description="Longitud del centroide", example=-79.916)
    indice_riesgo: float = Field(
        ..., description="Índice de riesgo proyectado (0.0 a 1.0)", example=0.82
    )
    nivel_riesgo: str = Field(
        ..., description="Nivel de riesgo proyectado: BAJO, MEDIO, ALTO, EXTREMO", example="EXTREMO"
    )
    indice_impacto: float | None = Field(
        None, description="Índice de impacto estimado", example=0.65
    )
    horizonte_h: int = Field(
        ..., description="Horizonte del pronóstico en horas (+24h o +48h)", example=24
    )


class RespuestaPronostico(BaseModel):
    horizonte_h: int = Field(
        ..., description="Horizonte temporal del pronóstico (+24h/+48h)", example=24
    )
    zonas: list[ZonaPronostico] = Field(..., description="Resultados proyectados por zona urbana")


class ClimaPuntoResponse(BaseModel):
    temperatura_c: float | None = Field(
        None, description="Temperatura ambiente en °C", example=28.5
    )
    humedad_pct: float | None = Field(
        None, description="Humedad relativa en porcentaje (%)", example=82.0
    )
    viento_ms: float | None = Field(None, description="Velocidad del viento en m/s", example=3.4)
    descripcion: str | None = Field(
        None, description="Descripción meteorológica en español", example="lluvia moderada"
    )


class Salud(BaseModel):
    estado: str = Field("ok", description="Estado del servicio API REST", example="ok")


# ---------------------------------------------------------------------------
# Utilidades de HDFS y Caché
# ---------------------------------------------------------------------------


def _client():
    return get_client(WEBHDFS_URL, HDFS_USER)


@lru_cache(maxsize=1)
def _zonas_referencia() -> list[dict[str, Any]]:
    """Zonas de Guayaquil del CSV de referencia, cacheadas por proceso."""
    with open(GEO_REF_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _geo_info() -> dict[str, dict[str, Any]]:
    return {
        fila["zona_id"]: {
            "nombre_sector": fila["nombre_sector"],
            "lat_centroide": float(fila["lat_centroide"]),
            "lon_centroide": float(fila["lon_centroide"]),
        }
        for fila in _zonas_referencia()
    }


def _sin_datos(detalle: str) -> HTTPException:
    return HTTPException(status_code=404, detail=detalle)


def _hdfs_caido(error: HdfsError) -> HTTPException:
    logger.warning("HDFS inaccesible: %s", error)
    return HTTPException(status_code=503, detail="HDFS no disponible")


def _ultimo_por_zona(df):
    df = df.sort_values("calculado_en")
    if "epoch_id" in df.columns:
        df = df.drop_duplicates(subset=["zona_id", "epoch_id"], keep="last")
    return df.drop_duplicates(subset=["zona_id"], keep="last")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get(
    "/api/salud",
    response_model=RespuestaAPI[Salud],
    tags=["salud"],
    summary="Estado de salud de la API",
    description="Retorna la disponibilidad operativa del servicio FastAPI envolviendo el estado en RespuestaAPI.",
    response_description="Confirmación del estado 'ok'.",
)
def salud():
    return _respuesta_exitosa({"estado": "ok"})


@app.get(
    "/api/riesgo/zonas",
    response_model=RespuestaAPI[RespuestaZonas],
    tags=["riesgo"],
    summary="Índice de riesgo actual por zonas",
    description=(
        "Obtiene la última evaluación de riesgo procesada por Spark Streaming "
        "para todas las zonas urbanas de Guayaquil."
    ),
    response_description="Lista de zonas urbanas envuelta en el formato RespuestaAPI.",
    responses={
        404: {
            "model": RespuestaAPI[None],
            "description": "Sin particiones o datos de riesgo en HDFS.",
        },
        503: {"model": RespuestaAPI[None], "description": "Servidor WebHDFS inalcanzable."},
    },
)
def riesgo_zonas_actual():
    ruta_hdfs = f"{HDFS_BASE}/processed/indice_riesgo"
    try:
        df = read_latest_partition_parquet(_client(), ruta_hdfs)
    except FileNotFoundError:
        raise _sin_datos("Aún no hay datos de índice de riesgo procesados") from None
    except HdfsError as error:
        raise _hdfs_caido(error) from error

    df_ultimo_por_zona = _ultimo_por_zona(df)

    geo_info = _geo_info()
    zonas = df_ultimo_por_zona.to_dict(orient="records")
    for zona in zonas:
        zona.update(geo_info.get(zona["zona_id"], {}))

    payload = {
        "actualizado_en": df_ultimo_por_zona["calculado_en"].max().isoformat(),
        "zonas": zonas,
    }
    return _respuesta_exitosa(payload, fuente=ruta_hdfs)


@app.get(
    "/api/riesgo/zonas/{zona_id}/historico",
    response_model=RespuestaAPI[list[dict[str, Any]]],
    tags=["riesgo"],
    summary="Serie temporal del índice de riesgo por zona",
    description=(
        "Retorna el histórico de puntuaciones de riesgo y variables físicas "
        "para una zona específica en un rango de fechas."
    ),
    response_description="Serie de tiempo envuelta en RespuestaAPI.",
    responses={
        404: {
            "model": RespuestaAPI[None],
            "description": "Zona no encontrada o sin registros en el rango.",
        },
        503: {"model": RespuestaAPI[None], "description": "Error al comunicarse con HDFS."},
    },
)
def riesgo_zona_historico(
    zona_id: str = Path(
        ..., description="Identificador único de la zona (ej: ZONA_001)", example="ZONA_001"
    ),
    desde: date | None = Query(
        None,
        description="Fecha inicial de la consulta (YYYY-MM-DD)",
        example="2026-01-01",
    ),
    hasta: date | None = Query(
        None,
        description="Fecha final de la consulta (YYYY-MM-DD)",
        example="2026-01-07",
    ),
    max_dias: int = Query(
        7, ge=1, le=90, description="Tope de particiones diarias a leer (máx 90)", example=7
    ),
):
    ruta_hdfs = f"{HDFS_BASE}/processed/indice_riesgo"
    try:
        df = read_all_partitions_parquet(
            _client(),
            ruta_hdfs,
            desde=desde.isoformat() if desde else None,
            hasta=hasta.isoformat() if hasta else None,
            max_particiones=max_dias,
        )
    except FileNotFoundError:
        raise _sin_datos("Aún no hay datos de índice de riesgo procesados") from None
    except HdfsError as error:
        raise _hdfs_caido(error) from error

    if df.empty:
        raise _sin_datos("No hay datos para el rango solicitado") from None

    df_zona = df[df["zona_id"] == zona_id].sort_values("calculado_en")
    if "epoch_id" in df_zona.columns:
        df_zona = df_zona.drop_duplicates(subset=["epoch_id"], keep="last")
    if df_zona.empty:
        raise _sin_datos(f"No hay datos para la zona {zona_id}") from None

    columnas = [
        "calculado_en",
        "indice_riesgo",
        "nivel_riesgo",
        "precip_acumulada_24h_mm",
        "altura_marea_m",
        "nivel_embalse_msnm",
        "datos_completos",
    ]
    presentes = [c for c in columnas if c in df_zona.columns]

    return _respuesta_exitosa(df_zona[presentes].to_dict(orient="records"), fuente=ruta_hdfs)


def _ultimo_registro_raw(fuente: str, detalle_404: str) -> tuple[dict, str]:
    ruta_hdfs = f"{HDFS_BASE}/raw/{fuente}"
    try:
        df = read_latest_partition_parquet(_client(), ruta_hdfs)
    except FileNotFoundError:
        raise _sin_datos(detalle_404) from None
    except HdfsError as error:
        raise _hdfs_caido(error) from error

    if df.empty:
        raise _sin_datos(detalle_404) from None

    return df.sort_values("kafka_timestamp").iloc[-1].to_dict(), ruta_hdfs


@app.get(
    "/api/enso/estado",
    response_model=RespuestaAPI[dict[str, Any]],
    tags=["enso"],
    summary="Último estado ENSO (NOAA SST)",
    description=(
        "Obtiene el último registro de temperatura superficial del mar (SST) "
        "y anomalías climáticas desde HDFS raw/noaa."
    ),
    response_description="Objeto JSON con indicadores ENSO más recientes envuelto en RespuestaAPI.",
    responses={
        404: {"model": RespuestaAPI[None], "description": "Sin datos de NOAA en HDFS raw."},
        503: {"model": RespuestaAPI[None], "description": "HDFS no disponible."},
    },
)
def estado_enso():
    reg, ruta = _ultimo_registro_raw("noaa", "Aún no hay datos de SST/ENSO")
    return _respuesta_exitosa(reg, fuente=ruta)


@app.get(
    "/api/mareas/actual",
    response_model=RespuestaAPI[dict[str, Any]],
    tags=["hidrologia"],
    summary="Última marea astronómica (INOCAR)",
    description="Retorna la lectura de marea en vivo o astronómica predicha por INOCAR.",
    response_description="Última medición de nivel de marea envuelta en RespuestaAPI.",
    responses={
        404: {"model": RespuestaAPI[None], "description": "Sin registros de marea INOCAR."},
        503: {"model": RespuestaAPI[None], "description": "HDFS no disponible."},
    },
)
def marea_actual():
    reg, ruta = _ultimo_registro_raw("inocar_mareas", "Aún no hay datos de marea")
    return _respuesta_exitosa(reg, fuente=ruta)


@app.get(
    "/api/embalse/actual",
    response_model=RespuestaAPI[dict[str, Any]],
    tags=["hidrologia"],
    summary="Nivel del embalse Daule-Peripa (CELEC)",
    description="Obtiene la cota actual en msnm de la represa Daule-Peripa.",
    response_description="Nivel actual del embalse envuelto en RespuestaAPI.",
    responses={
        404: {"model": RespuestaAPI[None], "description": "Sin registros de CELEC."},
        503: {"model": RespuestaAPI[None], "description": "HDFS no disponible."},
    },
)
def embalse_actual():
    reg, ruta = _ultimo_registro_raw("celec_embalse", "Aún no hay datos del embalse")
    return _respuesta_exitosa(reg, fuente=ruta)


@app.get(
    "/api/alertas/recientes",
    response_model=RespuestaAPI[list[dict[str, Any]]],
    tags=["alertas"],
    summary="Alertas e incidentes de Gestión de Riesgos (SNGR)",
    description="Retorna las alertas oficiales más recientes sobre inundaciones y desbordes.",
    response_description="Lista de boletines y alertas emitidas envuelta en RespuestaAPI.",
    responses={
        503: {"model": RespuestaAPI[None], "description": "HDFS no disponible."},
    },
)
def alertas_recientes(
    limite: int = Query(
        20, ge=1, le=200, description="Cantidad máxima de alertas a retornar", example=20
    ),
):
    ruta_hdfs = f"{HDFS_BASE}/raw/sngr_alertas"
    try:
        df = read_latest_partition_parquet(_client(), ruta_hdfs)
    except FileNotFoundError:
        return _respuesta_exitosa([], fuente=ruta_hdfs)
    except HdfsError as error:
        raise _hdfs_caido(error) from error

    if df.empty:
        return _respuesta_exitosa([], fuente=ruta_hdfs)

    alertas = (
        df.sort_values("kafka_timestamp", ascending=False).head(limite).to_dict(orient="records")
    )
    return _respuesta_exitosa(alertas, fuente=ruta_hdfs)


@app.get(
    "/api/escenario/simular",
    response_model=RespuestaAPI[RespuestaEscenario],
    tags=["riesgo"],
    summary="Simulación interactiva de escenario hipotético",
    description=(
        "Recalcula en tiempo real el índice de riesgo e impacto para todas "
        "las zonas urbanas con valores hipotéticos sin modificar HDFS."
    ),
    response_description="Escenario recalculado dinámicamente envuelto en RespuestaAPI.",
)
def simular_escenario(
    precip_24h_mm: float = Query(
        ..., ge=0, description="Lluvia acumulada hipotética (mm)", example=60.0
    ),
    altura_marea_m: float = Query(
        ..., ge=0, description="Altura de marea hipotética (m)", example=4.0
    ),
    caudal_rio_m3s: float = Query(
        500.0, ge=0, description="Caudal del río Guayas (m3/s)", example=1200.0
    ),
    saturacion_antecedente_mm: float = Query(
        0.0, ge=0, description="Saturación del suelo (mm)", example=40.0
    ),
    anomalia_nino12_c: float = Query(
        0.0, description="Anomalía de temperatura SST Niño 1+2 (°C)", example=2.0
    ),
):
    zonas = []
    for fila in _zonas_referencia():
        poblacion = int(fila.get("poblacion") or 0)
        resultado = calcular_indice_riesgo(
            precip_24h_mm=precip_24h_mm,
            altura_marea_m=altura_marea_m,
            cota_media_msnm=float(fila["cota_media_msnm"]),
            pendiente_clase=fila["pendiente_clase"],
            cercania_estero_m=float(fila["cercania_estero_m"]),
            historicamente_inundable=(fila["historicamente_inundable"].lower() == "true"),
            caudal_rio_m3s=caudal_rio_m3s,
            saturacion_antecedente_mm=saturacion_antecedente_mm,
            anomalia_nino12_c=anomalia_nino12_c,
            poblacion=poblacion,
        )
        zonas.append(
            {
                "zona_id": fila["zona_id"],
                "nombre_sector": fila["nombre_sector"],
                "lat_centroide": float(fila["lat_centroide"]),
                "lon_centroide": float(fila["lon_centroide"]),
                "precip_acumulada_24h_mm": precip_24h_mm,
                "altura_marea_m": altura_marea_m,
                "caudal_rio_m3s": caudal_rio_m3s,
                "saturacion_antecedente_mm": saturacion_antecedente_mm,
                "anomalia_nino12_c": anomalia_nino12_c,
                "poblacion": poblacion,
                "exposicion_norm": resultado["exposicion_norm"],
                "indice_impacto": resultado["indice_impacto"],
                "indice_riesgo": resultado["indice_riesgo"],
                "nivel_riesgo": resultado["nivel_riesgo"],
                "datos_completos": True,
            }
        )

    payload = {
        "parametros": {
            "precip_24h_mm": precip_24h_mm,
            "altura_marea_m": altura_marea_m,
            "caudal_rio_m3s": caudal_rio_m3s,
            "saturacion_antecedente_mm": saturacion_antecedente_mm,
            "anomalia_nino12_c": anomalia_nino12_c,
        },
        "zonas": zonas,
    }
    return _respuesta_exitosa(payload, fuente="modelo_simulacion_memoria")


@app.get(
    "/api/riesgo/pronostico",
    response_model=RespuestaAPI[RespuestaPronostico],
    tags=["riesgo"],
    summary="Pronóstico proyectado de riesgo (+24h/+48h)",
    description="Genera una proyección del riesgo a futuro considerando pronósticos meteorológicos de precipitaciones.",
    response_description="Pronóstico por zonas para el horizonte seleccionado envuelto en RespuestaAPI.",
)
def pronostico_riesgo(
    horizonte_h: int = Query(
        24, ge=12, le=72, description="Horizonte proyectado en horas (24 o 48)", example=24
    ),
):
    zonas = []
    precip_futura = 35.0 if horizonte_h == 24 else 60.0
    for fila in _zonas_referencia():
        poblacion = int(fila.get("poblacion") or 0)
        res = calcular_indice_riesgo(
            precip_24h_mm=precip_futura,
            altura_marea_m=2.4,
            caudal_rio_m3s=750.0,
            saturacion_antecedente_mm=25.0,
            cota_media_msnm=float(fila["cota_media_msnm"]),
            pendiente_clase=fila["pendiente_clase"],
            cercania_estero_m=float(fila["cercania_estero_m"]),
            historicamente_inundable=(fila["historicamente_inundable"].lower() == "true"),
            poblacion=poblacion,
        )
        zonas.append(
            {
                "zona_id": fila["zona_id"],
                "nombre_sector": fila["nombre_sector"],
                "lat_centroide": float(fila["lat_centroide"]),
                "lon_centroide": float(fila["lon_centroide"]),
                "indice_riesgo": res["indice_riesgo"],
                "nivel_riesgo": res["nivel_riesgo"],
                "indice_impacto": res["indice_impacto"],
                "horizonte_h": horizonte_h,
            }
        )
    payload = {"horizonte_h": horizonte_h, "zonas": zonas}
    return _respuesta_exitosa(payload, fuente="modelo_pronostico_precip")


@app.get(
    "/api/clima/punto",
    response_model=RespuestaAPI[ClimaPuntoResponse],
    tags=["clima_proxy"],
    summary="Proxy de clima puntual (OpenWeatherMap)",
    description="Consulta la temperatura, humedad y estado del clima en vivo para cualquier coordenada puntual.",
    response_description="Resumen de condiciones meteorológicas envuelto en RespuestaAPI.",
    responses={
        502: {
            "model": RespuestaAPI[None],
            "description": "Error o falla en la respuesta de OpenWeatherMap.",
        },
        503: {"model": RespuestaAPI[None], "description": "OPENWEATHERMAP_API_KEY no configurada."},
    },
)
def clima_punto(
    lat: float = Query(..., ge=-90, le=90, description="Latitud de la ubicación", example=-2.167),
    lon: float = Query(
        ..., ge=-180, le=180, description="Longitud de la ubicación", example=-79.916
    ),
):
    if not OPENWEATHERMAP_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="OPENWEATHERMAP_API_KEY no configurada en el servidor",
        )

    try:
        respuesta = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={
                "lat": lat,
                "lon": lon,
                "appid": OPENWEATHERMAP_API_KEY,
                "units": "metric",
                "lang": "es",
            },
            timeout=10,
        )
        respuesta.raise_for_status()
    except requests.RequestException as error:
        logger.warning("OpenWeatherMap no respondió: %s", error)
        raise HTTPException(
            status_code=502,
            detail="OpenWeatherMap no disponible",
        ) from error

    datos = respuesta.json()
    clima_info = {
        "temperatura_c": datos.get("main", {}).get("temp"),
        "humedad_pct": datos.get("main", {}).get("humidity"),
        "viento_ms": datos.get("wind", {}).get("speed"),
        "descripcion": (datos.get("weather") or [{}])[0].get("description"),
    }
    return _respuesta_exitosa(clima_info, fuente="api.openweathermap.org")


CAPAS_TILES_OWM = {"precipitation_new", "clouds_new"}


@app.get(
    "/api/clima/tiles/{capa}/{z}/{x}/{y}.png",
    tags=["clima_proxy"],
    summary="Proxy de tiles raster meteorológicos",
    description="Retorna una imagen PNG con la capa de precipitación o nubes para mapas interactivos (MapLibre/Leaflet).",
    response_description="Imagen PNG del tile solicitado.",
    responses={
        400: {"model": RespuestaAPI[None], "description": "Nivel de zoom fuera de rango (0-20)."},
        404: {"model": RespuestaAPI[None], "description": "Capa no reconocida."},
        502: {
            "model": RespuestaAPI[None],
            "description": "Error al consultar tile de OpenWeatherMap.",
        },
        503: {"model": RespuestaAPI[None], "description": "OPENWEATHERMAP_API_KEY no configurada."},
    },
)
def clima_tile(
    capa: str = Path(
        ...,
        description="Nombre de la capa raster (precipitation_new|clouds_new)",
        example="precipitation_new",
    ),
    z: int = Path(..., description="Nivel de zoom (0 a 20)", example=10),
    x: int = Path(..., description="Coordenada X del tile", example=284),
    y: int = Path(..., description="Coordenada Y del tile", example=514),
):
    if capa not in CAPAS_TILES_OWM:
        raise _sin_datos("Capa no reconocida") from None
    if not (0 <= z <= 20):
        raise HTTPException(status_code=400, detail="Zoom fuera de rango")
    if not OPENWEATHERMAP_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="OPENWEATHERMAP_API_KEY no configurada en el servidor",
        )

    try:
        respuesta = requests.get(
            f"https://tile.openweathermap.org/map/{capa}/{z}/{x}/{y}.png",
            params={"appid": OPENWEATHERMAP_API_KEY},
            timeout=10,
        )
        respuesta.raise_for_status()
    except requests.RequestException as error:
        logger.warning("tile %s/%s/%s/%s no disponible: %s", capa, z, x, y, error)
        raise HTTPException(
            status_code=502,
            detail="OpenWeatherMap no disponible",
        ) from error

    return Response(
        content=respuesta.content,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=600"},
    )


# ---------------------------------------------------------------------------
# Endpoints Normalizados REST para Fuentes HDFS
# ---------------------------------------------------------------------------


def _leer_capa_seguraep(filename: str, descripcion_error: str):
    hdfs_path = f"{HDFS_BASE}/raw/seguraep/{filename}"
    try:
        with _client().read(hdfs_path) as reader:
            obj = json.load(reader)
            return _respuesta_exitosa(obj, fuente=hdfs_path)
    except HdfsError:
        raise _sin_datos(descripcion_error) from None


DatoTelemetriaRaw = dict[str, Any] | list[Any]


def _leer_telemetria_raw(fuente: str, descripcion_error: str):
    reg, ruta = _ultimo_registro_raw(fuente, descripcion_error)
    try:
        obj = json.loads(reg.get("json_str", "{}"))
    except (ValueError, TypeError) as error:
        raise HTTPException(status_code=500, detail=f"Dato de {fuente} corrupto en HDFS") from error

    if isinstance(obj, dict) and "data" in obj:
        return _respuesta_exitosa(obj["data"], fuente=ruta)
    return _respuesta_exitosa(obj, fuente=ruta)


@app.get(
    "/api/clima/gee",
    response_model=RespuestaAPI[DatoTelemetriaRaw],
    tags=["clima"],
    summary="Datos satelitales Google Earth Engine (CHIRPS / GPM)",
    description="Obtiene la última lectura de precipitación satelital calculada desde GEE.",
    response_description="Objeto JSON con datos satelitales envuelto en RespuestaAPI.",
)
def clima_gee():
    return _leer_telemetria_raw("gee", "Sin datos satelitales GEE")


@app.get(
    "/api/clima/open-meteo",
    response_model=RespuestaAPI[DatoTelemetriaRaw],
    tags=["clima"],
    summary="Pronóstico climático horario (Open-Meteo)",
    description="Retorna la última predicción horaria de precipitación y humedad de Open-Meteo.",
    response_description="Pronóstico horario envuelto en RespuestaAPI.",
)
def clima_open_meteo():
    return _leer_telemetria_raw("open_meteo", "Sin datos de Open-Meteo")


@app.get(
    "/api/clima/nasa-power",
    response_model=RespuestaAPI[DatoTelemetriaRaw],
    tags=["clima"],
    summary="Parámetros agrometeorológicos (NASA POWER)",
    description="Obtiene radiación solar, humedad y viento desde la API de NASA POWER.",
    response_description="Datos meteorológicos NASA POWER envueltos en RespuestaAPI.",
)
def clima_nasa_power():
    return _leer_telemetria_raw("nasa_power", "Sin datos de NASA POWER")


@app.get(
    "/api/enso/indices",
    response_model=RespuestaAPI[DatoTelemetriaRaw],
    tags=["enso"],
    summary="Índices ENSO macro (Niño 1+2, ONI, SOI)",
    description="Obtiene la serie temporal de índices macroclimáticos de El Niño Oscilación del Sur.",
    response_description="Índices macroclimáticos envueltos en RespuestaAPI.",
)
def enso_indices():
    return _leer_telemetria_raw("enso_indexes", "Sin índices macro ENSO")


@app.get(
    "/api/clima/inamhi",
    response_model=RespuestaAPI[dict[str, Any]],
    tags=["clima"],
    summary="Boletín de pronóstico oficial (INAMHI)",
    description="Retorna las alertas y temperaturas estimadas por INAMHI para Guayaquil.",
    response_description="Boletín INAMHI envuelto en RespuestaAPI.",
)
def clima_inamhi():
    return _leer_telemetria_raw("inamhi", "Sin datos de pronóstico INAMHI")


@app.get(
    "/api/clima/openweathermap",
    response_model=RespuestaAPI[DatoTelemetriaRaw],
    tags=["clima"],
    summary="Condiciones meteorológicas en tiempo real (OpenWeatherMap)",
    description="Obtiene temperatura actual, humedad y nubosidad para Guayaquil.",
    response_description="Clima actual envuelto en RespuestaAPI.",
)
def clima_openweathermap():
    return _leer_telemetria_raw("openweathermap", "Sin datos de OpenWeatherMap")


@app.get(
    "/api/eventos/sgr",
    response_model=RespuestaAPI[dict[str, Any]],
    tags=["eventos"],
    summary="Eventos de lluvia e inundaciones (SGR)",
    description="Obtiene la colección GeoJSON de eventos de lluvia e incidentes reportados por la SGR.",
    response_description="GeoJSON FeatureCollection de eventos envuelto en RespuestaAPI.",
)
def eventos_sgr():
    return _leer_telemetria_raw("sgr_eventos", "Sin eventos SGR")


@app.get(
    "/api/boyas/ndbc",
    response_model=RespuestaAPI[dict[str, Any]],
    tags=["clima"],
    summary="Telemetría de boyas oceánicas (NOAA NDBC)",
    description="Obtiene observaciones mar adentro de boyas meteorológicas del Pacífico Este.",
    response_description="Datos de boyas envueltos en RespuestaAPI.",
)
def boyas_ndbc():
    return _leer_telemetria_raw("ndbc_buoys", "Sin datos de boyas NDBC")


@app.get(
    "/api/hidrologia/geoglows",
    response_model=RespuestaAPI[dict[str, Any]],
    tags=["hidrologia"],
    summary="Caudales de la Cuenca del Guayas (GEOGLOWS ECMWF)",
    description="Obtiene la estimación de caudal simulado del Río Guayas y tributarios principales.",
    response_description="Caudal de ríos envuelto en RespuestaAPI.",
)
def hidrologia_geoglows():
    return _leer_telemetria_raw("caudal_geoglows", "Sin caudal GEOGLOWS")


@app.get(
    "/api/capas/guayas-osm",
    response_model=RespuestaAPI[dict[str, Any]],
    tags=["capas_geograficas"],
    summary="Polígono del Cantón Guayaquil (OpenStreetMap)",
    description="Retorna el contorno del Cantón Guayaquil derivado de OpenStreetMap.",
    response_description="GeoJSON del cantón Guayaquil envuelto en RespuestaAPI.",
)
def capas_guayas_osm():
    return _leer_telemetria_raw("guayas_osm", "Sin mapa OSM del Cantón Guayaquil")


@app.get(
    "/api/capas/parroquias",
    response_model=RespuestaAPI[dict[str, Any]],
    tags=["capas_geograficas"],
    summary="Parroquias Cantonales de Guayaquil (16 Urbanas + 5 Rurales)",
    description="Retorna el GeoJSON oficial unificado con los límites de las parroquias urbanas y rurales de Guayaquil.",
    response_description="GeoJSON FeatureCollection de parroquias envuelto en RespuestaAPI.",
)
def capas_parroquias():
    return _leer_capa_seguraep(
        "sgr_parroquias_guayaquil.geojson", "Sin capa de parroquias de Guayaquil"
    )


@app.get(
    "/api/capas/sectores",
    response_model=RespuestaAPI[dict[str, Any]],
    tags=["capas_geograficas"],
    summary="Distritos Operativos Segura EP (A01-A18)",
    description="Retorna el GeoJSON de sectores y distritos operativos de respuesta a emergencias de Segura EP.",
    response_description="GeoJSON FeatureCollection de sectores celestes envuelto en RespuestaAPI.",
)
def capas_sectores():
    return _leer_capa_seguraep("sgr_sectores_celestes.geojson", "Sin capa de sectores Segura EP")


@app.get(
    "/api/capas/zonas-inundables",
    response_model=RespuestaAPI[dict[str, Any]],
    tags=["capas_geograficas"],
    summary="Zonas de Riesgo Histórico de Inundación (SGR)",
    description="Retorna polígonos de zonas históricamente vulnerables a anegamientos por precipitaciones.",
    response_description="GeoJSON FeatureCollection de zonas inundables envuelto en RespuestaAPI.",
)
def capas_zonas_inundables():
    return _leer_capa_seguraep("sgr_zonas_inundables.geojson", "Sin zonas inundables")


@app.get(
    "/api/capas/zonas-seguras",
    response_model=RespuestaAPI[dict[str, Any]],
    tags=["capas_geograficas"],
    summary="Zonas Seguras y Albergues Temporales",
    description="Retorna los puntos de refugio y zonas seguras coordinadas por Gestión de Riesgos.",
    response_description="GeoJSON FeatureCollection de zonas seguras envuelto en RespuestaAPI.",
)
def capas_zonas_seguras():
    return _leer_capa_seguraep("sgr_zonas_seguras.geojson", "Sin zonas seguras")


@app.get(
    "/api/capas/vias-inundables",
    response_model=RespuestaAPI[dict[str, Any]],
    tags=["capas_geograficas"],
    summary="Vías Inundables por Lluvia",
    description="Retorna tramos viales urbanos propensos a acumulación de agua durante tormentas.",
    response_description="GeoJSON FeatureCollection de vías inundables envuelto en RespuestaAPI.",
)
def capas_vias_inundables():
    return _leer_capa_seguraep("sgr_vias_inundables.geojson", "Sin vías inundables")


@app.get(
    "/api/capas/vias-vulnerables-marea",
    response_model=RespuestaAPI[dict[str, Any]],
    tags=["capas_geograficas"],
    summary="Vías Vulnerables a Marea Alta",
    description="Retorna arterias viales afectadas cuando la marea del Río Guayas excede cotas críticas.",
    response_description="GeoJSON FeatureCollection de vías vulnerables por marea envuelto en RespuestaAPI.",
)
def capas_vias_vulnerables_marea():
    return _leer_capa_seguraep(
        "sgr_vias_vulnerables_marea_alta.geojson", "Sin vías vulnerables por marea"
    )
