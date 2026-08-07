"""
Endpoints de indicadores oceánicos y atmosféricos de El Niño (ENSO).
"""

from __future__ import annotations

from fastapi import APIRouter

from ..helpers import leer_telemetria_raw, respuesta_exitosa, ultimo_registro_raw
from ..schemas import DatoTelemetriaRaw, EstadoENSO, RespuestaAPI

router = APIRouter(prefix="/api", tags=["enso"])


@router.get(
    "/enso/estado",
    response_model=RespuestaAPI[EstadoENSO],
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
    reg, ruta = ultimo_registro_raw("noaa", "Aún no hay datos de SST/ENSO")
    return respuesta_exitosa(reg, fuente=ruta)


@router.get(
    "/enso/indices",
    response_model=RespuestaAPI[DatoTelemetriaRaw],
    summary="Índices ENSO macro (Niño 1+2, ONI, SOI)",
    description="Obtiene la serie temporal de índices macroclimáticos de El Niño Oscilación del Sur.",
    response_description="Índices macroclimáticos envueltos en RespuestaAPI.",
)
def enso_indices():
    return leer_telemetria_raw("enso_indexes", "Sin índices macro ENSO")
