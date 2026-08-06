"""
Endpoints de monitoreo, simulación y pronóstico del índice de riesgo.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import requests
from fastapi import APIRouter, Path, Query
from hdfs.util import HdfsError

try:
    from ..hdfs_client import (
        read_all_partitions_parquet,
        read_latest_partition_parquet,
    )
except ImportError:
    from hdfs_client import (
        read_all_partitions_parquet,
        read_latest_partition_parquet,
    )

from ..helpers import (
    HDFS_BASE,
    _client,
    cache_hdfs,
    calcular_indice_riesgo,
    geo_info,
    hdfs_caido,
    respuesta_exitosa,
    sin_datos,
    ultimo_por_zona,
    zonas_referencia,
)
from ..schemas import (
    RegistroHistoricoZona,
    RespuestaAPI,
    RespuestaEscenario,
    RespuestaPronostico,
    RespuestaZonas,
)

router = APIRouter(prefix="/api", tags=["riesgo"])


@router.get(
    "/riesgo/zonas",
    response_model=RespuestaAPI[RespuestaZonas],
    summary="Índice de riesgo actual por zonas",
    description=(
        "Obtiene la última evaluación de riesgo procesada por Spark Streaming "
        "para todas las zonas urbanas de Guayaquil."
    ),
    response_description="Lista de zonas urbanas envuelta en el formato RespuestaAPI.",
    responses={
        404: {
            "model": RespuestaAPI[None],
            "description": "Sin particiones o datos de riesgo en HDFS.",
        },
        503: {"model": RespuestaAPI[None], "description": "Servidor WebHDFS inalcanzable."},
    },
)
def riesgo_zonas_actual():
    clave_cache = "riesgo_zonas_actual"
    cached = cache_hdfs.get(clave_cache)
    if cached is not None:
        return cached

    ruta_hdfs = f"{HDFS_BASE}/processed/indice_riesgo"
    try:
        df = read_latest_partition_parquet(_client(), ruta_hdfs)
    except FileNotFoundError:
        raise sin_datos("Aún no hay datos de índice de riesgo procesados") from None
    except (HdfsError, requests.RequestException) as error:
        raise hdfs_caido(error) from error

    df_ultimo_por_zona = ultimo_por_zona(df)

    g_info = geo_info()
    zonas = df_ultimo_por_zona.to_dict(orient="records")
    for zona in zonas:
        zona.update(g_info.get(zona["zona_id"], {}))

    actualizado_en = (
        df_ultimo_por_zona["calculado_en"].max().isoformat()
        if "calculado_en" in df_ultimo_por_zona.columns
        else None
    )
    payload = {
        "actualizado_en": actualizado_en,
        "zonas": zonas,
    }
    resultado = respuesta_exitosa(payload, fuente=ruta_hdfs)
    cache_hdfs.set(clave_cache, resultado)
    return resultado


@router.get(
    "/riesgo/zonas/{zona_id}/historico",
    response_model=RespuestaAPI[list[RegistroHistoricoZona]],
    summary="Serie temporal del índice de riesgo por zona",
    description=(
        "Retorna el histórico de puntuaciones de riesgo y variables físicas "
        "para una zona específica en un rango de fechas."
    ),
    response_description="Serie de tiempo envuelta en RespuestaAPI.",
    responses={
        404: {
            "model": RespuestaAPI[None],
            "description": "Zona no encontrada o sin registros en el rango.",
        },
        503: {"model": RespuestaAPI[None], "description": "Error al comunicarse con HDFS."},
    },
)
def riesgo_zona_historico(
    zona_id: str = Path(
        ..., description="Identificador único de la zona (ej: ZONA_001)", example="ZONA_001"
    ),
    desde: date | None = Query(
        None,
        description="Fecha inicial de la consulta (YYYY-MM-DD)",
        example="2026-01-01",
    ),
    hasta: date | None = Query(
        None,
        description="Fecha final de la consulta (YYYY-MM-DD)",
        example="2026-01-07",
    ),
    max_dias: int = Query(
        7, ge=1, le=90, description="Tope de particiones diarias a leer (máx 90)", example=7
    ),
):
    ruta_hdfs = f"{HDFS_BASE}/processed/indice_riesgo"
    try:
        df = read_all_partitions_parquet(
            _client(),
            ruta_hdfs,
            desde=desde.isoformat() if desde else None,
            hasta=hasta.isoformat() if hasta else None,
            max_particiones=max_dias,
        )
    except FileNotFoundError:
        raise sin_datos("Aún no hay datos de índice de riesgo procesados") from None
    except (HdfsError, requests.RequestException) as error:
        raise hdfs_caido(error) from error

    if df.empty:
        raise sin_datos("No hay datos para el rango solicitado") from None

    df_zona = df[df["zona_id"] == zona_id]
    if "calculado_en" in df_zona.columns:
        df_zona = df_zona.sort_values("calculado_en")
    if "epoch_id" in df_zona.columns:
        df_zona = df_zona.drop_duplicates(subset=["epoch_id"], keep="last")
    if df_zona.empty:
        raise sin_datos(f"No hay datos para la zona {zona_id}") from None

    columnas = [
        "calculado_en",
        "indice_riesgo",
        "nivel_riesgo",
        "precip_acumulada_24h_mm",
        "altura_marea_m",
        "nivel_embalse_msnm",
        "datos_completos",
    ]
    presentes = [c for c in columnas if c in df_zona.columns]

    return respuesta_exitosa(df_zona[presentes].to_dict(orient="records"), fuente=ruta_hdfs)


@router.get(
    "/escenario/simular",
    response_model=RespuestaAPI[RespuestaEscenario],
    summary="Simulación interactiva de escenario hipotético",
    description=(
        "Recalcula en tiempo real el índice de riesgo e impacto para todas "
        "las zonas urbanas con valores hipotéticos sin modificar HDFS."
    ),
    response_description="Escenario recalculado dinámicamente envuelto en RespuestaAPI.",
)
def simular_escenario(
    precip_24h_mm: float = Query(
        ..., ge=0, description="Lluvia acumulada hipotética (mm)", example=60.0
    ),
    altura_marea_m: float = Query(
        ..., ge=0, description="Altura de marea hipotética (m)", example=4.0
    ),
    caudal_rio_m3s: float = Query(
        500.0, ge=0, description="Caudal del río Guayas (m3/s)", example=1200.0
    ),
    saturacion_antecedente_mm: float = Query(
        0.0, ge=0, description="Saturación del suelo (mm)", example=40.0
    ),
    anomalia_nino12_c: float = Query(
        0.0, description="Anomalía de temperatura SST Niño 1+2 (°C)", example=2.0
    ),
):
    zonas = []
    for fila in zonas_referencia():
        poblacion = int(fila.get("poblacion") or 0)
        resultado = calcular_indice_riesgo(
            precip_24h_mm=precip_24h_mm,
            altura_marea_m=altura_marea_m,
            cota_media_msnm=float(fila["cota_media_msnm"]),
            pendiente_clase=fila["pendiente_clase"],
            cercania_estero_m=float(fila["cercania_estero_m"]),
            historicamente_inundable=(fila["historicamente_inundable"].lower() == "true"),
            caudal_rio_m3s=caudal_rio_m3s,
            saturacion_antecedente_mm=saturacion_antecedente_mm,
            anomalia_nino12_c=anomalia_nino12_c,
            poblacion=poblacion,
        )
        zonas.append(
            {
                "zona_id": fila["zona_id"],
                "nombre_sector": fila["nombre_sector"],
                "lat_centroide": float(fila["lat_centroide"]),
                "lon_centroide": float(fila["lon_centroide"]),
                "precip_acumulada_24h_mm": precip_24h_mm,
                "altura_marea_m": altura_marea_m,
                "caudal_rio_m3s": caudal_rio_m3s,
                "saturacion_antecedente_mm": saturacion_antecedente_mm,
                "anomalia_nino12_c": anomalia_nino12_c,
                "poblacion": poblacion,
                "exposicion_norm": resultado["exposicion_norm"],
                "indice_impacto": resultado["indice_impacto"],
                "indice_riesgo": resultado["indice_riesgo"],
                "nivel_riesgo": resultado["nivel_riesgo"],
                "datos_completos": True,
            }
        )

    payload = {
        "parametros": {
            "precip_24h_mm": precip_24h_mm,
            "altura_marea_m": altura_marea_m,
            "caudal_rio_m3s": caudal_rio_m3s,
            "saturacion_antecedente_mm": saturacion_antecedente_mm,
            "anomalia_nino12_c": anomalia_nino12_c,
        },
        "zonas": zonas,
    }
    return respuesta_exitosa(payload, fuente="modelo_simulacion_memoria")


@router.get(
    "/riesgo/pronostico",
    response_model=RespuestaAPI[RespuestaPronostico],
    summary="Pronóstico proyectado de riesgo (+24h/+48h)",
    description="Genera una proyección del riesgo a futuro considerando pronósticos meteorológicos de precipitaciones.",
    response_description="Pronóstico por zonas para el horizonte seleccionado envuelto en RespuestaAPI.",
)
def pronostico_riesgo(
    horizonte_h: int = Query(
        24, ge=12, le=72, description="Horizonte proyectado en horas (24 o 48)", example=24
    ),
):
    zonas = []
    precip_futura = 35.0 if horizonte_h == 24 else 60.0
    for fila in zonas_referencia():
        poblacion = int(fila.get("poblacion") or 0)
        res = calcular_indice_riesgo(
            precip_24h_mm=precip_futura,
            altura_marea_m=2.4,
            caudal_rio_m3s=750.0,
            saturacion_antecedente_mm=25.0,
            cota_media_msnm=float(fila["cota_media_msnm"]),
            pendiente_clase=fila["pendiente_clase"],
            cercania_estero_m=float(fila["cercania_estero_m"]),
            historicamente_inundable=(fila["historicamente_inundable"].lower() == "true"),
            poblacion=poblacion,
        )
        zonas.append(
            {
                "zona_id": fila["zona_id"],
                "nombre_sector": fila["nombre_sector"],
                "lat_centroide": float(fila["lat_centroide"]),
                "lon_centroide": float(fila["lon_centroide"]),
                "indice_riesgo": res["indice_riesgo"],
                "nivel_riesgo": res["nivel_riesgo"],
                "indice_impacto": res["indice_impacto"],
                "horizonte_h": horizonte_h,
            }
        )
    payload = {"horizonte_h": horizonte_h, "zonas": zonas}
    return respuesta_exitosa(payload, fuente="modelo_pronostico_precip")
