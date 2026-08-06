"""
Endpoints de auditoría y observabilidad de logs de productores.
"""

from __future__ import annotations

from datetime import date

import requests
from fastapi import APIRouter, Query
from hdfs.util import HdfsError

try:
    from ..hdfs_client import (
        leer_texto_particiones,
        listar_valores_particion,
        parsear_linea_log,
    )
except ImportError:
    from hdfs_client import (
        leer_texto_particiones,
        listar_valores_particion,
        parsear_linea_log,
    )

from ..helpers import HDFS_BASE, _client, hdfs_caido, respuesta_exitosa, sin_datos
from ..schemas import RegistroLog, RespuestaAPI

router = APIRouter(prefix="/api", tags=["observabilidad"])


@router.get(
    "/logs/productores",
    response_model=RespuestaAPI[list[str]],
    summary="Producers con logs disponibles en HDFS",
    description=(
        "Lista los nombres de producer con al menos una partición de logs "
        "archivada en HDFS bajo raw/producer_logs."
    ),
    response_description="Lista de nombres de producer envuelta en RespuestaAPI.",
    responses={
        404: {
            "model": RespuestaAPI[None],
            "description": "Aún no hay logs de ningún producer en HDFS.",
        },
        503: {"model": RespuestaAPI[None], "description": "Servidor WebHDFS inalcanzable."},
    },
)
def logs_productores():
    ruta_hdfs = f"{HDFS_BASE}/raw/producer_logs"
    try:
        nombres = listar_valores_particion(_client(), ruta_hdfs, "producer")
    except FileNotFoundError:
        raise sin_datos("Aún no hay logs de producers en HDFS") from None
    except (HdfsError, requests.RequestException) as error:
        raise hdfs_caido(error) from error

    return respuesta_exitosa(nombres, fuente=ruta_hdfs)


@router.get(
    "/logs",
    response_model=RespuestaAPI[list[RegistroLog]],
    summary="Logs de un producer",
    description=(
        "Lee y filtra las líneas de log que un producer subió a HDFS (ver "
        "HandlerHDFS en backend/producers/common/kafka_client.py), "
        "opcionalmente acotadas por fecha y nivel."
    ),
    response_description="Líneas de log parseadas, envueltas en RespuestaAPI.",
    responses={
        404: {
            "model": RespuestaAPI[None],
            "description": "El producer no tiene logs (o ninguno pasa los filtros).",
        },
        503: {"model": RespuestaAPI[None], "description": "Servidor WebHDFS inalcanzable."},
    },
)
def logs_productor(
    producer: str = Query(
        ..., pattern="^[a-z0-9_]+$", description="Nombre del producer (ej: noaa)", example="noaa"
    ),
    desde: date | None = Query(
        None, description="Fecha inicial de la consulta (YYYY-MM-DD)", example="2026-08-01"
    ),
    hasta: date | None = Query(
        None, description="Fecha final de la consulta (YYYY-MM-DD)", example="2026-08-05"
    ),
    nivel: str | None = Query(
        None, pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$", description="Filtra por nivel exacto"
    ),
    max_dias: int = Query(
        7, ge=1, le=90, description="Tope de particiones diarias a leer (máx 90)", example=7
    ),
    limite: int = Query(
        200, ge=1, le=1000, description="Tope de líneas a devolver (más recientes primero)"
    ),
):
    ruta_hdfs = f"{HDFS_BASE}/raw/producer_logs/producer={producer}"
    try:
        lineas = leer_texto_particiones(
            _client(),
            ruta_hdfs,
            desde=desde.isoformat() if desde else None,
            hasta=hasta.isoformat() if hasta else None,
            max_particiones=max_dias,
        )
    except FileNotFoundError:
        raise sin_datos(f"No hay logs para el producer {producer}") from None
    except (HdfsError, requests.RequestException) as error:
        raise hdfs_caido(error) from error

    registros = [r for linea in lineas if (r := parsear_linea_log(linea)) is not None]
    if nivel:
        registros = [r for r in registros if r["nivel"] == nivel]
    registros.sort(key=lambda r: r["fecha"], reverse=True)
    registros = registros[:limite]

    if not registros:
        raise sin_datos(f"No hay logs para producer={producer} con esos filtros") from None

    return respuesta_exitosa(registros, fuente=ruta_hdfs)
