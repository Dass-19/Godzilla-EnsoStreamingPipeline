"""
Utilidades auxiliares, clientes de E/S, gestión de caché e integración con HDFS.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import pathlib
import sys
import time
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

import httpx
import requests
from fastapi import HTTPException
from hdfs.util import HdfsError

try:
    from .hdfs_client import (
        es_ruta_inexistente,
        get_client,
        read_latest_partition_parquet,
    )
except ImportError:
    from hdfs_client import (
        es_ruta_inexistente,
        get_client,
        read_latest_partition_parquet,
    )

logger = logging.getLogger("enso.api")

WEBHDFS_URL = os.environ.get("WEBHDFS_URL", "http://localhost:9870")
HDFS_USER = os.environ.get("HDFS_USER", "root")
HDFS_BASE = os.environ.get("HDFS_BASE_PATH", "/enso_data")
OPENWEATHERMAP_API_KEY = os.environ.get("OPENWEATHERMAP_API_KEY", "")

CORS_ORIGINS = [
    origen.strip()
    for origen in os.environ.get(
        "CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
    ).split(",")
    if origen.strip()
]


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

_http_client: httpx.AsyncClient | None = None


async def obtener_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
    return _http_client


async def cerrar_http_client() -> None:
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()


class CacheTTL:
    """Caché en memoria con expiración por tiempo. Thread-safe por el GIL."""

    def __init__(self, ttl_segundos: float = 15.0):
        self._ttl = ttl_segundos
        self._datos: dict[str, tuple[float, Any]] = {}

    def get(self, clave: str) -> Any | None:
        entrada = self._datos.get(clave)
        if entrada is None:
            return None
        ts, valor = entrada
        if time.monotonic() - ts > self._ttl:
            del self._datos[clave]
            return None
        return valor

    def set(self, clave: str, valor: Any) -> None:
        self._datos[clave] = (time.monotonic(), valor)


cache_hdfs = CacheTTL(ttl_segundos=15.0)
_CacheTTL = CacheTTL
_cache_hdfs = cache_hdfs



def _client():
    return get_client(WEBHDFS_URL, HDFS_USER)


@lru_cache(maxsize=1)
def zonas_referencia() -> list[dict[str, Any]]:
    """Zonas de Guayaquil del CSV de referencia, cacheadas por proceso."""
    with open(GEO_REF_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def geo_info() -> dict[str, dict[str, Any]]:
    return {
        fila["zona_id"]: {
            "nombre_sector": fila["nombre_sector"],
            "lat_centroide": float(fila["lat_centroide"]),
            "lon_centroide": float(fila["lon_centroide"]),
        }
        for fila in zonas_referencia()
    }


def sin_datos(detalle: str) -> HTTPException:
    return HTTPException(status_code=404, detail=detalle)


def hdfs_caido(error: Exception) -> HTTPException:
    logger.warning("HDFS inaccesible: %s", error)
    return HTTPException(status_code=503, detail="HDFS no disponible")


def ultimo_por_zona(df):
    if "calculado_en" not in df.columns:
        logger.warning("DataFrame sin columna 'calculado_en', retornando sin deduplicar")
        return df
    df = df.sort_values("calculado_en")
    if "epoch_id" in df.columns:
        df = df.drop_duplicates(subset=["zona_id", "epoch_id"], keep="last")
    return df.drop_duplicates(subset=["zona_id"], keep="last")


def ultimo_registro_raw(fuente: str, detalle_404: str) -> tuple[dict, str]:
    ruta_hdfs = f"{HDFS_BASE}/raw/{fuente}"
    try:
        df = read_latest_partition_parquet(_client(), ruta_hdfs)
    except FileNotFoundError:
        raise sin_datos(detalle_404) from None
    except (HdfsError, requests.RequestException) as error:
        raise hdfs_caido(error) from error

    if df.empty:
        raise sin_datos(detalle_404) from None

    col_orden = "kafka_timestamp" if "kafka_timestamp" in df.columns else None
    if col_orden:
        df = df.sort_values(col_orden)
    return df.iloc[-1].to_dict(), ruta_hdfs


def respuesta_exitosa(
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


def leer_capa_seguraep(filename: str, descripcion_error: str):
    hdfs_path = f"{HDFS_BASE}/raw/seguraep/{filename}"
    try:
        with _client().read(hdfs_path) as reader:
            obj = json.load(reader)
            return respuesta_exitosa(obj, fuente=hdfs_path)
    except HdfsError as error:
        if es_ruta_inexistente(error):
            raise sin_datos(descripcion_error) from None
        raise hdfs_caido(error) from error


def leer_telemetria_raw(fuente: str, descripcion_error: str):
    reg, ruta = ultimo_registro_raw(fuente, descripcion_error)
    try:
        obj = json.loads(reg.get("json_str", "{}"))
    except (ValueError, TypeError) as error:
        raise HTTPException(status_code=500, detail=f"Dato de {fuente} corrupto en HDFS") from error

    if isinstance(obj, dict) and "data" in obj:
        return respuesta_exitosa(obj["data"], fuente=ruta)
    return respuesta_exitosa(obj, fuente=ruta)
