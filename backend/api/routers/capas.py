"""
Endpoints de capas geográficas GeoJSON para el mapa.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..helpers import leer_capa_seguraep, leer_telemetria_raw
from ..schemas import RespuestaAPI

router = APIRouter(prefix="/api", tags=["capas_geograficas"])


@router.get(
    "/capas/guayas-osm",
    response_model=RespuestaAPI[dict[str, Any]],
    summary="Polígono del Cantón Guayaquil (OpenStreetMap)",
    description="Retorna el contorno del Cantón Guayaquil derivado de OpenStreetMap.",
    response_description="GeoJSON del cantón Guayaquil envuelto en RespuestaAPI.",
)
def capas_guayas_osm():
    return leer_telemetria_raw("guayas_osm", "Sin mapa OSM del Cantón Guayaquil")


@router.get(
    "/capas/parroquias",
    response_model=RespuestaAPI[dict[str, Any]],
    summary="Parroquias Cantonales de Guayaquil (16 Urbanas + 5 Rurales)",
    description="Retorna el GeoJSON oficial unificado con los límites de las parroquias urbanas y rurales de Guayaquil.",
    response_description="GeoJSON FeatureCollection de parroquias envuelto en RespuestaAPI.",
)
def capas_parroquias():
    return leer_capa_seguraep(
        "sgr_parroquias_guayaquil.geojson", "Sin capa de parroquias de Guayaquil"
    )


@router.get(
    "/capas/sectores",
    response_model=RespuestaAPI[dict[str, Any]],
    summary="Distritos Operativos Segura EP (A01-A18)",
    description="Retorna el GeoJSON de sectores y distritos operativos de respuesta a emergencias de Segura EP.",
    response_description="GeoJSON FeatureCollection de sectores celestes envuelto en RespuestaAPI.",
)
def capas_sectores():
    return leer_capa_seguraep("sgr_sectores_celestes.geojson", "Sin capa de sectores Segura EP")


@router.get(
    "/capas/zonas-inundables",
    response_model=RespuestaAPI[dict[str, Any]],
    summary="Zonas de Riesgo Histórico de Inundación (SGR)",
    description="Retorna polígonos de zonas históricamente vulnerables a anegamientos por precipitaciones.",
    response_description="GeoJSON FeatureCollection de zonas inundables envuelto en RespuestaAPI.",
)
def capas_zonas_inundables():
    return leer_capa_seguraep("sgr_zonas_inundables.geojson", "Sin zonas inundables")


@router.get(
    "/capas/zonas-seguras",
    response_model=RespuestaAPI[dict[str, Any]],
    summary="Zonas Seguras y Albergues Temporales",
    description="Retorna los puntos de refugio y zonas seguras coordinadas por Gestión de Riesgos.",
    response_description="GeoJSON FeatureCollection de zonas seguras envuelto en RespuestaAPI.",
)
def capas_zonas_seguras():
    return leer_capa_seguraep("sgr_zonas_seguras.geojson", "Sin zonas seguras")


@router.get(
    "/capas/vias-inundables",
    response_model=RespuestaAPI[dict[str, Any]],
    summary="Vías Inundables por Lluvia",
    description="Retorna tramos viales urbanos propensos a acumulación de agua durante tormentas.",
    response_description="GeoJSON FeatureCollection de vías inundables envuelto en RespuestaAPI.",
)
def capas_vias_inundables():
    return leer_capa_seguraep("sgr_vias_inundables.geojson", "Sin vías inundables")


@router.get(
    "/capas/vias-vulnerables-marea",
    response_model=RespuestaAPI[dict[str, Any]],
    summary="Vías Vulnerables a Marea Alta",
    description="Retorna arterias viales afectadas cuando la marea del Río Guayas excede cotas críticas.",
    response_description="GeoJSON FeatureCollection de vías vulnerables por marea envuelto en RespuestaAPI.",
)
def capas_vias_vulnerables_marea():
    return leer_capa_seguraep(
        "sgr_vias_vulnerables_marea_alta.geojson", "Sin vías vulnerables por marea"
    )
