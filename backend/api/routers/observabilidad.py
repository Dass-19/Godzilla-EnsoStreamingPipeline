"""
Endpoints de auditoría y observabilidad de logs de productores.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import requests
from fastapi import APIRouter, Query
from hdfs.util import HdfsError

try:
    from ..analisis_logs import construir_resumen
    from ..hdfs_client import (
        leer_texto_particiones,
        listar_valores_particion,
        parsear_linea_log,
    )
except ImportError:
    from analisis_logs import construir_resumen
    from hdfs_client import (
        leer_texto_particiones,
        listar_valores_particion,
        parsear_linea_log,
    )

from ..helpers import HDFS_BASE, CacheTTL, _client, hdfs_caido, respuesta_exitosa, sin_datos
from ..schemas import RegistroLog, RespuestaAPI, ResumenLogs

router = APIRouter(prefix="/api", tags=["observabilidad"])

# TTL propio: el resumen recorre los ~21 producers y cuesta segundos, mientras
# que el `cache_hdfs` global es de 15s y el tablero refresca cada minuto.
cache_resumen = CacheTTL(ttl_segundos=60.0)


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
            "description": "El producer no tiene ninguna partición de logs en HDFS.",
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

    # Lista vacía y 200: "este producer no tuvo errores" es una respuesta válida,
    # no un recurso ausente. Con 404 era indistinguible de HDFS caído.
    return respuesta_exitosa(registros, fuente=ruta_hdfs)


@router.get(
    "/logs/resumen",
    response_model=RespuestaAPI[ResumenLogs],
    summary="Indicadores agregados de los logs de producers",
    description=(
        "Salud por producer, degradaciones detectadas, actividad por hora y los "
        "errores más repetidos, agregados desde los logs archivados en HDFS."
    ),
    response_description="Resumen de observabilidad envuelto en RespuestaAPI.",
    responses={
        404: {"model": RespuestaAPI[None], "description": "Aún no hay logs en HDFS."},
        503: {"model": RespuestaAPI[None], "description": "Servidor WebHDFS inalcanzable."},
    },
)
def logs_resumen(
    dias: int = Query(1, ge=1, le=30, description="Particiones diarias a agregar", example=1),
):
    clave = f"logs_resumen:{dias}"
    if (cacheado := cache_resumen.get(clave)) is not None:
        return cacheado

    base = f"{HDFS_BASE}/raw/producer_logs"
    try:
        nombres = listar_valores_particion(_client(), base, "producer")
    except FileNotFoundError:
        raise sin_datos("Aún no hay logs de producers en HDFS") from None
    except (HdfsError, requests.RequestException) as error:
        raise hdfs_caido(error) from error

    por_producer: dict[str, list[dict]] = {}
    for nombre in nombres:
        try:
            lineas = leer_texto_particiones(
                _client(), f"{base}/producer={nombre}", max_particiones=dias
            )
        except FileNotFoundError:
            lineas = []  # sin partición en la ventana: queda como sin_senal
        except (HdfsError, requests.RequestException) as error:
            raise hdfs_caido(error) from error
        por_producer[nombre] = [r for ln in lineas if (r := parsear_linea_log(ln)) is not None]

    # Naive: el `asctime` de los logs no lleva zona y los contenedores corren UTC.
    resumen = construir_resumen(por_producer, ahora=datetime.now(UTC).replace(tzinfo=None))
    respuesta = respuesta_exitosa(resumen, fuente=base, total_registros=len(nombres))
    cache_resumen.set(clave, respuesta)
    return respuesta
