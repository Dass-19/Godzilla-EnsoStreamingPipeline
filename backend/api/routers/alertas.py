"""
Endpoints de alertas e incidentes de Gestión de Riesgos.
"""

from __future__ import annotations

import requests
from fastapi import APIRouter, Query
from hdfs.util import HdfsError

try:
    from ..hdfs_client import read_latest_partition_parquet
except ImportError:
    from hdfs_client import read_latest_partition_parquet

from ..helpers import HDFS_BASE, _client, hdfs_caido, respuesta_exitosa
from ..schemas import RegistroAlerta, RespuestaAPI

router = APIRouter(prefix="/api", tags=["alertas"])


@router.get(
    "/alertas/recientes",
    response_model=RespuestaAPI[list[RegistroAlerta]],
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
        return respuesta_exitosa([], fuente=ruta_hdfs)
    except (HdfsError, requests.RequestException) as error:
        raise hdfs_caido(error) from error

    if df.empty:
        return respuesta_exitosa([], fuente=ruta_hdfs)

    col_orden = "kafka_timestamp" if "kafka_timestamp" in df.columns else df.columns[0]
    alertas = (
        df.sort_values(col_orden, ascending=False).head(limite).to_dict(orient="records")
    )
    return respuesta_exitosa(alertas, fuente=ruta_hdfs)
