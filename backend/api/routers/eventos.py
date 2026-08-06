"""
Endpoints de eventos e incidentes reportados por SGR.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..helpers import leer_telemetria_raw
from ..schemas import RespuestaAPI

router = APIRouter(prefix="/api", tags=["eventos"])


@router.get(
    "/eventos/sgr",
    response_model=RespuestaAPI[dict[str, Any]],
    summary="Eventos de lluvia e inundaciones (SGR)",
    description="Obtiene la colección GeoJSON de eventos de lluvia e incidentes reportados por la SGR.",
    response_description="GeoJSON FeatureCollection de eventos envuelto en RespuestaAPI.",
)
def eventos_sgr():
    return leer_telemetria_raw("sgr_eventos", "Sin eventos SGR")
