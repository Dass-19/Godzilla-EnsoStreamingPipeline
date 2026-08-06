"""
Endpoints de telemetría climática y proxies en vivo (OpenWeatherMap, GEE, INAMHI, etc.).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Path, Query, Response

from ..helpers import (
    OPENWEATHERMAP_API_KEY,
    leer_telemetria_raw,
    obtener_http_client,
    respuesta_exitosa,
    sin_datos,
)
from ..schemas import ClimaPuntoResponse, DatoTelemetriaRaw, RespuestaAPI

logger = logging.getLogger("enso.api")

router = APIRouter(prefix="/api", tags=["clima"])

CAPAS_TILES_OWM = {"precipitation_new", "clouds_new"}


@router.get(
    "/clima/punto",
    response_model=RespuestaAPI[ClimaPuntoResponse],
    tags=["clima_proxy"],
    summary="Proxy de clima puntual (OpenWeatherMap)",
    description="Consulta la temperatura, humedad y estado del clima en vivo para cualquier coordenada puntual.",
    response_description="Resumen de condiciones meteorológicas envuelto en RespuestaAPI.",
    responses={
        502: {
            "model": RespuestaAPI[None],
            "description": "Error o falla en la respuesta de OpenWeatherMap.",
        },
        503: {"model": RespuestaAPI[None], "description": "OPENWEATHERMAP_API_KEY no configurada."},
    },
)
async def clima_punto(
    lat: float = Query(..., ge=-90, le=90, description="Latitud de la ubicación", example=-2.167),
    lon: float = Query(
        ..., ge=-180, le=180, description="Longitud de la ubicación", example=-79.916
    ),
):
    if not OPENWEATHERMAP_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="OPENWEATHERMAP_API_KEY no configurada en el servidor",
        )

    try:
        http_client = await obtener_http_client()
        respuesta = await http_client.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={
                "lat": lat,
                "lon": lon,
                "appid": OPENWEATHERMAP_API_KEY,
                "units": "metric",
                "lang": "es",
            },
        )
        respuesta.raise_for_status()
    except httpx.HTTPError as error:
        logger.warning("OpenWeatherMap no respondió: %s", error)
        raise HTTPException(
            status_code=502,
            detail="OpenWeatherMap no disponible",
        ) from error

    datos = respuesta.json()
    clima_info = {
        "temperatura_c": datos.get("main", {}).get("temp"),
        "humedad_pct": datos.get("main", {}).get("humidity"),
        "viento_ms": datos.get("wind", {}).get("speed"),
        "descripcion": (datos.get("weather") or [{}])[0].get("description"),
    }
    return respuesta_exitosa(clima_info, fuente="api.openweathermap.org")


@router.get(
    "/clima/tiles/{capa}/{z}/{x}/{y}.png",
    tags=["clima_proxy"],
    summary="Proxy de tiles raster meteorológicos",
    description="Retorna una imagen PNG con la capa de precipitación o nubes para mapas interactivos (MapLibre/Leaflet).",
    response_description="Imagen PNG del tile solicitado.",
    responses={
        400: {"model": RespuestaAPI[None], "description": "Nivel de zoom fuera de rango (0-20)."},
        404: {"model": RespuestaAPI[None], "description": "Capa no reconocida."},
        502: {
            "model": RespuestaAPI[None],
            "description": "Error al consultar tile de OpenWeatherMap.",
        },
        503: {"model": RespuestaAPI[None], "description": "OPENWEATHERMAP_API_KEY no configurada."},
    },
)
async def clima_tile(
    capa: str = Path(
        ...,
        description="Nombre de la capa raster (precipitation_new|clouds_new)",
        example="precipitation_new",
    ),
    z: int = Path(..., description="Nivel de zoom (0 a 20)", example=10),
    x: int = Path(..., description="Coordenada X del tile", example=284),
    y: int = Path(..., description="Coordenada Y del tile", example=514),
):
    if capa not in CAPAS_TILES_OWM:
        raise sin_datos("Capa no reconocida") from None
    if not (0 <= z <= 20):
        raise HTTPException(status_code=400, detail="Zoom fuera de rango")
    if not OPENWEATHERMAP_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="OPENWEATHERMAP_API_KEY no configurada en el servidor",
        )

    try:
        http_client = await obtener_http_client()
        respuesta = await http_client.get(
            f"https://tile.openweathermap.org/map/{capa}/{z}/{x}/{y}.png",
            params={"appid": OPENWEATHERMAP_API_KEY},
        )
        respuesta.raise_for_status()
    except httpx.HTTPError as error:
        logger.warning("tile %s/%s/%s/%s no disponible: %s", capa, z, x, y, error)
        raise HTTPException(
            status_code=502,
            detail="OpenWeatherMap no disponible",
        ) from error

    return Response(
        content=respuesta.content,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=600"},
    )


@router.get(
    "/clima/gee",
    response_model=RespuestaAPI[DatoTelemetriaRaw],
    summary="Datos satelitales Google Earth Engine (CHIRPS / GPM)",
    description="Obtiene la última lectura de precipitación satelital calculada desde GEE.",
    response_description="Objeto JSON con datos satelitales envuelto en RespuestaAPI.",
)
def clima_gee():
    return leer_telemetria_raw("gee", "Sin datos satelitales GEE")


@router.get(
    "/clima/open-meteo",
    response_model=RespuestaAPI[DatoTelemetriaRaw],
    summary="Pronóstico climático horario (Open-Meteo)",
    description="Retorna la última predicción horaria de precipitación y humedad de Open-Meteo.",
    response_description="Pronóstico horario envuelto en RespuestaAPI.",
)
def clima_open_meteo():
    return leer_telemetria_raw("open_meteo", "Sin datos de Open-Meteo")


@router.get(
    "/clima/nasa-power",
    response_model=RespuestaAPI[DatoTelemetriaRaw],
    summary="Parámetros agrometeorológicos (NASA POWER)",
    description="Obtiene radiación solar, humedad y viento desde la API de NASA POWER.",
    response_description="Datos meteorológicos NASA POWER envueltos en RespuestaAPI.",
)
def clima_nasa_power():
    return leer_telemetria_raw("nasa_power", "Sin datos de NASA POWER")


@router.get(
    "/clima/inamhi",
    response_model=RespuestaAPI[dict[str, Any]],
    summary="Boletín de pronóstico oficial (INAMHI)",
    description="Retorna las alertas y temperaturas estimadas por INAMHI para Guayaquil.",
    response_description="Boletín INAMHI envuelto en RespuestaAPI.",
)
def clima_inamhi():
    return leer_telemetria_raw("inamhi", "Sin datos de pronóstico INAMHI")


@router.get(
    "/clima/openweathermap",
    response_model=RespuestaAPI[DatoTelemetriaRaw],
    summary="Condiciones meteorológicas en tiempo real (OpenWeatherMap)",
    description="Obtiene temperatura actual, humedad y nubosidad para Guayaquil.",
    response_description="Clima actual envuelto en RespuestaAPI.",
)
def clima_openweathermap():
    return leer_telemetria_raw("openweathermap", "Sin datos de OpenWeatherMap")


@router.get(
    "/boyas/ndbc",
    response_model=RespuestaAPI[dict[str, Any]],
    summary="Telemetría de boyas oceánicas (NOAA NDBC)",
    description="Obtiene observaciones mar adentro de boyas meteorológicas del Pacífico Este.",
    response_description="Datos de boyas envueltos en RespuestaAPI.",
)
def boyas_ndbc():
    return leer_telemetria_raw("ndbc_buoys", "Sin datos de boyas NDBC")
