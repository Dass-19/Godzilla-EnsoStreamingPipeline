"""
Endpoints de entradas hidrológicas (marea INOCAR, embalse CELEC, caudal GEOGLOWS).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..helpers import leer_telemetria_raw, respuesta_exitosa, ultimo_registro_raw
from ..schemas import EmbalseActual, MareaActual, RespuestaAPI

router = APIRouter(prefix="/api", tags=["hidrologia"])


@router.get(
    "/mareas/actual",
    response_model=RespuestaAPI[MareaActual],
    summary="Última marea astronómica (INOCAR)",
    description="Retorna la lectura de marea en vivo o astronómica predicha por INOCAR.",
    response_description="Última medición de nivel de marea envuelta en RespuestaAPI.",
    responses={
        404: {"model": RespuestaAPI[None], "description": "Sin registros de marea INOCAR."},
        503: {"model": RespuestaAPI[None], "description": "HDFS no disponible."},
    },
)
def marea_actual():
    reg, ruta = ultimo_registro_raw("inocar_mareas", "Aún no hay datos de marea")
    return respuesta_exitosa(reg, fuente=ruta)


@router.get(
    "/embalse/actual",
    response_model=RespuestaAPI[EmbalseActual],
    summary="Nivel del embalse Daule-Peripa (CELEC)",
    description="Obtiene la cota actual en msnm de la represa Daule-Peripa.",
    response_description="Nivel actual del embalse envuelto en RespuestaAPI.",
    responses={
        404: {"model": RespuestaAPI[None], "description": "Sin registros de CELEC."},
        503: {"model": RespuestaAPI[None], "description": "HDFS no disponible."},
    },
)
def embalse_actual():
    reg, ruta = ultimo_registro_raw("celec_embalse", "Aún no hay datos del embalse")
    return respuesta_exitosa(reg, fuente=ruta)


@router.get(
    "/hidrologia/geoglows",
    response_model=RespuestaAPI[dict[str, Any]],
    summary="Caudales de la Cuenca del Guayas (GEOGLOWS ECMWF)",
    description="Obtiene la estimación de caudal simulado del Río Guayas y tributarios principales.",
    response_description="Caudal de ríos envuelto en RespuestaAPI.",
)
def hidrologia_geoglows():
    return leer_telemetria_raw("caudal_geoglows", "Sin caudal GEOGLOWS")
