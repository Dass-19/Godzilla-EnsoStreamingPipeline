"""
Endpoints de verificación de estado operativo.
"""

from __future__ import annotations

from fastapi import APIRouter

from ..helpers import respuesta_exitosa
from ..schemas import RespuestaAPI, Salud

router = APIRouter(prefix="/api", tags=["salud"])


@router.get(
    "/salud",
    response_model=RespuestaAPI[Salud],
    summary="Estado de salud de la API",
    description="Retorna la disponibilidad operativa del servicio FastAPI envolviendo el estado en RespuestaAPI.",
    response_description="Confirmación del estado 'ok'.",
)
def salud():
    return respuesta_exitosa({"estado": "ok"})
