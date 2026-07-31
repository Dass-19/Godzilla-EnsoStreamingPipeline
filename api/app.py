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

import csv
import logging
import os
import pathlib
import sys
from datetime import date
from functools import lru_cache
from typing import Any

import requests
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from hdfs.util import HdfsError
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

RAIZ_REPO = pathlib.Path(__file__).resolve().parent.parent


def _resolver_directorio_spark() -> pathlib.Path:
    """
    Ubica el paquete de Spark (`risk_index.py` + el CSV de zonas).

    Antes esto era `Path(__file__).parent.parent / "spark"`, que dentro del
    contenedor funcionaba de casualidad (Compose monta `backend/spark` en
    `/spark`) y fuera de Docker resolvía a `<repo>/spark`, un directorio que
    no existe: el flujo de desarrollo documentado devolvía 500.
    """
    candidatos = [
        os.environ.get("SPARK_APP_DIR"),
        "/spark",
        RAIZ_REPO / "backend" / "spark",
    ]
    for candidato in candidatos:
        if not candidato:
            continue
        ruta = pathlib.Path(candidato).resolve()
        if (ruta / "risk_index.py").exists():
            return ruta
    raise RuntimeError(
        "No se encontró risk_index.py. Definí SPARK_APP_DIR apuntando a "
        "backend/spark."
    )


SPARK_APP_DIR = _resolver_directorio_spark()
if str(SPARK_APP_DIR) not in sys.path:
    sys.path.insert(0, str(SPARK_APP_DIR))

# Import a nivel de módulo: antes se hacía dentro del handler, junto con un
# `sys.path.insert`, en cada request.
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

app = FastAPI(
    title="API riesgo de inundación - Guayaquil / El Niño",
    description=(
        "Sirve al dashboard los datos procesados por el pipeline Kafka "
        "+ Spark + HDFS"
    ),
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)

frontend_path = RAIZ_REPO / "frontend"
if not frontend_path.exists():
    # En el contenedor, Compose monta ./frontend en /frontend.
    frontend_path = pathlib.Path("/frontend")
if frontend_path.exists():
    app.mount(
        "/dashboard",
        StaticFiles(directory=str(frontend_path), html=True),
        name="frontend",
    )


# ---------------------------------------------------------------------------
# Modelos de respuesta
# ---------------------------------------------------------------------------

class ZonaRiesgo(BaseModel):
    zona_id: str
    nombre_sector: str | None = None
    lat_centroide: float | None = None
    lon_centroide: float | None = None
    indice_riesgo: float
    nivel_riesgo: str
    precip_acumulada_24h_mm: float | None = None
    altura_marea_m: float | None = None
    nivel_embalse_msnm: float | None = None
    origen_precip: str | None = None
    origen_marea: str | None = None
    origen_embalse: str | None = None
    datos_completos: bool | None = Field(
        None,
        description=(
            "False si alguna entrada del índice se calculó con un valor de "
            "respaldo en vez de un dato real de la fuente."
        ),
    )


class RespuestaZonas(BaseModel):
    actualizado_en: str | None = None
    zonas: list[ZonaRiesgo]


class ParametrosEscenario(BaseModel):
    precip_24h_mm: float
    altura_marea_m: float
    nivel_embalse_msnm: float


class RespuestaEscenario(BaseModel):
    parametros: ParametrosEscenario
    zonas: list[ZonaRiesgo]


class Salud(BaseModel):
    estado: str


# ---------------------------------------------------------------------------
# Utilidades
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
    """Un HDFS inalcanzable es 503, no 404: son problemas distintos."""
    logger.warning("HDFS inaccesible: %s", error)
    return HTTPException(status_code=503, detail="HDFS no disponible")


def _ultimo_por_zona(df):
    """
    Última fila por zona.

    `groupby("zona_id").last()` tomaba el último valor NO NULO de cada
    columna por separado, así que podía mezclar campos de instantes
    distintos. Además, `append` en `foreachBatch` no es idempotente: si Spark
    reintenta un epoch, sus filas se duplican, por eso se deduplica primero
    por (zona_id, epoch_id).
    """
    df = df.sort_values("calculado_en")
    if "epoch_id" in df.columns:
        df = df.drop_duplicates(subset=["zona_id", "epoch_id"], keep="last")
    return df.drop_duplicates(subset=["zona_id"], keep="last")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/salud", response_model=Salud)
def salud():
    return {"estado": "ok"}


@app.get("/api/riesgo/zonas", response_model=RespuestaZonas)
def riesgo_zonas_actual():
    """
    Último índice de riesgo calculado para todas las zonas de Guayaquil.
    Es el endpoint principal que consume el mapa del dashboard: una fila
    por zona con su score y nivel, lista para colorear polígonos.
    """
    try:
        df = read_latest_partition_parquet(
            _client(),
            f"{HDFS_BASE}/processed/indice_riesgo",
        )
    except FileNotFoundError:
        raise _sin_datos("Aún no hay datos de índice de riesgo procesados") from None
    except HdfsError as error:
        raise _hdfs_caido(error) from error

    df_ultimo_por_zona = _ultimo_por_zona(df)

    geo_info = _geo_info()
    zonas = df_ultimo_por_zona.to_dict(orient="records")
    for zona in zonas:
        zona.update(geo_info.get(zona["zona_id"], {}))

    return {
        "actualizado_en": df_ultimo_por_zona["calculado_en"].max().isoformat(),
        "zonas": zonas,
    }


@app.get("/api/riesgo/zonas/{zona_id}/historico")
def riesgo_zona_historico(
    zona_id: str,
    desde: date | None = Query(
        None,
        description="fecha inicial YYYY-MM-DD",
    ),
    hasta: date | None = Query(None, description="fecha final YYYY-MM-DD"),
    max_dias: int = Query(
        7, ge=1, le=90, description="tope de particiones diarias a leer",
    ),
):
    """Serie de tiempo del índice de riesgo de una zona."""
    try:
        df = read_all_partitions_parquet(
            _client(), f"{HDFS_BASE}/processed/indice_riesgo",
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

    return df_zona[presentes].to_dict(orient="records")


def _ultimo_registro_raw(fuente: str, detalle_404: str) -> dict:
    try:
        df = read_latest_partition_parquet(_client(), f"{HDFS_BASE}/raw/{fuente}")
    except FileNotFoundError:
        raise _sin_datos(detalle_404) from None
    except HdfsError as error:
        raise _hdfs_caido(error) from error

    if df.empty:
        raise _sin_datos(detalle_404) from None

    return df.sort_values("kafka_timestamp").iloc[-1].to_dict()


@app.get("/api/enso/estado")
def estado_enso():
    """Último estado ENSO para el panel nacional/regional del dashboard."""
    return _ultimo_registro_raw("noaa", "Aún no hay datos de SST/ENSO")


@app.get("/api/mareas/actual")
def marea_actual():
    return _ultimo_registro_raw("inocar_mareas", "Aún no hay datos de marea")


@app.get("/api/embalse/actual")
def embalse_actual():
    return _ultimo_registro_raw("celec_embalse", "Aún no hay datos del embalse")


@app.get("/api/alertas/recientes")
def alertas_recientes(limite: int = Query(20, ge=1, le=200)):
    """
    Últimas alertas SNGR crudas, para un listado o feed en el dashboard.

    Lee solo la partición más reciente: antes cargaba todo el histórico en
    pandas para devolver 20 filas.
    """
    try:
        df = read_latest_partition_parquet(
            _client(), f"{HDFS_BASE}/raw/sngr_alertas",
        )
    except FileNotFoundError:
        return []
    except HdfsError as error:
        raise _hdfs_caido(error) from error

    if df.empty:
        return []

    return (
        df.sort_values("kafka_timestamp", ascending=False)
        .head(limite)
        .to_dict(orient="records")
    )


@app.get("/api/escenario/simular", response_model=RespuestaEscenario)
def simular_escenario(
    precip_24h_mm: float = Query(..., ge=0),
    altura_marea_m: float = Query(..., ge=0),
    nivel_embalse_msnm: float = Query(
        ...,
        ge=0,
        description=(
            "Cota del embalse Daule-Peripa en metros sobre el nivel del mar. "
            "La fuente (CELEC) publica cota, no caudal de descarga."
        ),
    ),
):
    """
    Recalcula el índice de riesgo para todas las zonas con valores
    hipotéticos de lluvia/marea/embalse, sin tocar HDFS. Pensado para el
    control interactivo del dashboard ("¿y si hay lluvia intensa + marea
    alta?") sin esperar al próximo micro-batch de Spark.
    """
    zonas = []
    for fila in _zonas_referencia():
        resultado = calcular_indice_riesgo(
            precip_24h_mm=precip_24h_mm,
            altura_marea_m=altura_marea_m,
            nivel_embalse_msnm=nivel_embalse_msnm,
            cota_media_msnm=float(fila["cota_media_msnm"]),
            pendiente_clase=fila["pendiente_clase"],
            cercania_estero_m=float(fila["cercania_estero_m"]),
            historicamente_inundable=(
                fila["historicamente_inundable"].lower() == "true"
            ),
        )
        zonas.append({
            "zona_id": fila["zona_id"],
            "nombre_sector": fila["nombre_sector"],
            "lat_centroide": float(fila["lat_centroide"]),
            "lon_centroide": float(fila["lon_centroide"]),
            "precip_acumulada_24h_mm": precip_24h_mm,
            "altura_marea_m": altura_marea_m,
            "nivel_embalse_msnm": nivel_embalse_msnm,
            "indice_riesgo": resultado["indice_riesgo"],
            "nivel_riesgo": resultado["nivel_riesgo"],
            "datos_completos": True,
        })

    return {
        "parametros": {
            "precip_24h_mm": precip_24h_mm,
            "altura_marea_m": altura_marea_m,
            "nivel_embalse_msnm": nivel_embalse_msnm,
        },
        "zonas": zonas,
    }


@app.get("/api/clima/punto")
def clima_punto(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
):
    """
    Proxy del "current weather" de OpenWeatherMap.

    Existe para que la clave viva en el servidor: el dashboard la tenía
    embebida en `app.js`, visible para cualquier visitante.
    """
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
            status_code=502, detail="OpenWeatherMap no disponible",
        ) from error

    datos = respuesta.json()
    # Se devuelve solo lo que consume el dashboard, sin reenviar la respuesta
    # completa del proveedor.
    return {
        "temperatura_c": datos.get("main", {}).get("temp"),
        "humedad_pct": datos.get("main", {}).get("humidity"),
        "viento_ms": datos.get("wind", {}).get("speed"),
        "descripcion": (datos.get("weather") or [{}])[0].get("description"),
    }


# Capas raster de OpenWeatherMap que el dashboard puede encender.
CAPAS_TILES_OWM = {"precipitation_new", "clouds_new"}


@app.get("/api/clima/tiles/{capa}/{z}/{x}/{y}.png")
def clima_tile(capa: str, z: int, x: int, y: int):
    """
    Proxy de los tiles raster de OpenWeatherMap.

    Igual que `/api/clima/punto`: si el frontend pidiera los tiles directo, la
    clave viajaría en la URL de cada uno, a la vista de cualquier visitante.
    """
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
            status_code=502, detail="OpenWeatherMap no disponible",
        ) from error

    return Response(
        content=respuesta.content,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=600"},
    )


# ---------------------------------------------------------------------------
# Capa de compatibilidad para el frontend original
# ---------------------------------------------------------------------------

# Allowlist explícita: `filename` viene de la URL y se usaba para construir una
# ruta de HDFS sin validar.
ARCHIVOS_A_FUENTE = {
    "gee_data.json": "gee",
    "noaa_data.json": "noaa",
    "open_meteo_data.json": "open_meteo",
    "nasa_power_data.json": "nasa_power",
    "enso_indexes.json": "enso_indexes",
    "inocar_data.json": "inocar_mareas",
    "inamhi_data.json": "inamhi",
    "openweathermap_data.json": "openweathermap",
    "sgr_eventos.json": "sgr_eventos",
    "guayas_osm.geojson": "guayas_osm",
    "ndbc_buoys.json": "ndbc_buoys",
}

# Capas estáticas que `producer_seguraep.py` escribe directo a HDFS.
CAPAS_SEGURAEP = {
    "sgr_zonas_inundables.geojson",
    "sgr_zonas_seguras.geojson",
    "sgr_vias_inundables.geojson",
    "sgr_zonas_vulnerables_marea_alta.geojson",
    "sgr_sectores_celestes.geojson",
}


@app.get("/data/{filename}")
def get_data_file(filename: str):
    """Capa de compatibilidad para el frontend original de Godzilla."""
    import json

    if filename in ARCHIVOS_A_FUENTE:
        fuente = ARCHIVOS_A_FUENTE[filename]
        try:
            df = read_latest_partition_parquet(
                _client(), f"{HDFS_BASE}/raw/{fuente}",
            )
        except FileNotFoundError:
            raise _sin_datos(f"Aún no hay datos de {fuente}") from None
        except HdfsError as error:
            raise _hdfs_caido(error) from error

        if df.empty:
            raise _sin_datos(f"Aún no hay datos de {fuente}") from None

        ultimo = df.sort_values("kafka_timestamp").iloc[-1]
        try:
            obj = json.loads(ultimo["json_str"])
        except (ValueError, TypeError) as error:
            logger.warning("json_str inválido en raw/%s: %s", fuente, error)
            raise HTTPException(status_code=500, detail="Dato corrupto en HDFS") from error

        # MapLibre necesita el GeoJSON pelado, sin el envoltorio
        # {"metadata": ..., "data": ...} con que lo publica el productor.
        if filename.endswith(".geojson") and isinstance(obj, dict) and "data" in obj:
            return obj["data"]
        return obj

    if filename in CAPAS_SEGURAEP:
        hdfs_path = f"{HDFS_BASE}/raw/seguraep/{filename}"
        try:
            with _client().read(hdfs_path) as reader:
                return json.load(reader)
        except HdfsError as error:
            logger.info("capa SeguraEP no disponible (%s): %s", hdfs_path, error)
            raise _sin_datos(f"Capa {filename} todavía no cargada en HDFS") from None

    raise _sin_datos("Archivo no reconocido") from None
