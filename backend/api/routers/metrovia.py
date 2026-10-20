"""
Router de Monitoreo y Contingencia de la Metrovía (Troncal 4 y Troncales del Sistema).
Responde a los retos de movilidad:
- mov-troncal4: Reorganización del servicio ante anegamiento en el Suburbio Oeste (23.7 km).
- mov-metrovia: Monitor de estado de paradas, alerta de colapso y tiempos de espera para el usuario.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query

from ..helpers import leer_telemetria_raw, respuesta_exitosa
from ..schemas import RespuestaAPI

logger = logging.getLogger("enso.api.metrovia")

router = APIRouter(prefix="/api/metrovia", tags=["metrovia"])

# ---------------------------------------------------------------------------
# Definición Geoespacial Oficial de la Troncal 4 (23 Paradas)
# Recorrido: Batallón del Suburbio ↔ Av. Portete ↔ Av. Venezuela ↔ Centro / Malecón
# ---------------------------------------------------------------------------

PARADAS_TRONCAL_4 = [
    {
        "id": "T4-01",
        "nombre": "Terminal Batallón del Suburbio",
        "lat": -2.2272,
        "lon": -79.9295,
        "cota_msnm": 2.1,
        "sector": "Suburbio Oeste (Batallón)",
        "demanda_hora": 4200,
        "es_terminal": True,
    },
    {
        "id": "T4-02",
        "nombre": "Parada La Chala",
        "lat": -2.2215,
        "lon": -79.9240,
        "cota_msnm": 2.5,
        "sector": "Suburbio Oeste (La Chala)",
        "demanda_hora": 2800,
        "es_terminal": False,
    },
    {
        "id": "T4-03",
        "nombre": "Parada Puerto Lisa",
        "lat": -2.2150,
        "lon": -79.9210,
        "cota_msnm": 2.8,
        "sector": "Suburbio Oeste (Puerto Lisa)",
        "demanda_hora": 3100,
        "es_terminal": False,
    },
    {
        "id": "T4-04",
        "nombre": "Parada Calle 38 / Portete",
        "lat": -2.2100,
        "lon": -79.9185,
        "cota_msnm": 3.1,
        "sector": "Suburbio Oeste",
        "demanda_hora": 2500,
        "es_terminal": False,
    },
    {
        "id": "T4-05",
        "nombre": "Parada Calle 34 / Portete",
        "lat": -2.2070,
        "lon": -79.9150,
        "cota_msnm": 3.4,
        "sector": "Suburbio Oeste",
        "demanda_hora": 2900,
        "es_terminal": False,
    },
    {
        "id": "T4-06",
        "nombre": "Parada Calle 29 / Portete",
        "lat": -2.2045,
        "lon": -79.9110,
        "cota_msnm": 3.8,
        "sector": "Suburbio Oeste (Cristo del Consuelo)",
        "demanda_hora": 3500,
        "es_terminal": False,
    },
    {
        "id": "T4-07",
        "nombre": "Parada Calle 25 / Portete",
        "lat": -2.2025,
        "lon": -79.9075,
        "cota_msnm": 4.2,
        "sector": "Suburbio Oeste",
        "demanda_hora": 3100,
        "es_terminal": False,
    },
    {
        "id": "T4-08",
        "nombre": "Parada Calle 17 / Portete",
        "lat": -2.2005,
        "lon": -79.9025,
        "cota_msnm": 4.8,
        "sector": "Portete Central",
        "demanda_hora": 3600,
        "es_terminal": False,
    },
    {
        "id": "T4-09",
        "nombre": "Estación Calle 11 (Retorno / Transbordo Seguro)",
        "lat": -2.1985,
        "lon": -79.8970,
        "cota_msnm": 5.8,
        "sector": "Portete Alto",
        "demanda_hora": 4500,
        "es_terminal": False,
        "punto_retorno_contingencia": True,
    },
    {
        "id": "T4-10",
        "nombre": "Parada Lizardo García",
        "lat": -2.1970,
        "lon": -79.8935,
        "cota_msnm": 6.0,
        "sector": "Centro Sur",
        "demanda_hora": 3200,
        "es_terminal": False,
    },
    {
        "id": "T4-11",
        "nombre": "Parada Tungurahua",
        "lat": -2.1960,
        "lon": -79.8905,
        "cota_msnm": 6.2,
        "sector": "Centro Sur",
        "demanda_hora": 2800,
        "es_terminal": False,
    },
    {
        "id": "T4-12",
        "nombre": "Parada Carchi",
        "lat": -2.1950,
        "lon": -79.8875,
        "cota_msnm": 6.5,
        "sector": "Centro Sur",
        "demanda_hora": 3000,
        "es_terminal": False,
    },
    {
        "id": "T4-13",
        "nombre": "Parada Hospital del Niño",
        "lat": -2.1940,
        "lon": -79.8845,
        "cota_msnm": 6.5,
        "sector": "Centro Urbano",
        "demanda_hora": 3800,
        "es_terminal": False,
    },
    {
        "id": "T4-14",
        "nombre": "Parada Mercado Central",
        "lat": -2.1930,
        "lon": -79.8815,
        "cota_msnm": 6.0,
        "sector": "Centro Comercial",
        "demanda_hora": 5200,
        "es_terminal": False,
    },
    {
        "id": "T4-15",
        "nombre": "Parada Plaza del Centenario",
        "lat": -2.1915,
        "lon": -79.8860,
        "cota_msnm": 6.2,
        "sector": "Centro Histórico",
        "demanda_hora": 4900,
        "es_terminal": False,
    },
    {
        "id": "T4-16",
        "nombre": "Parada Caja del Seguro",
        "lat": -2.1905,
        "lon": -79.8885,
        "cota_msnm": 6.5,
        "sector": "Centro Cívico",
        "demanda_hora": 4100,
        "es_terminal": False,
    },
    {
        "id": "T4-17",
        "nombre": "Parada San Agustín",
        "lat": -2.1925,
        "lon": -79.8835,
        "cota_msnm": 5.8,
        "sector": "Centro",
        "demanda_hora": 3400,
        "es_terminal": False,
    },
    {
        "id": "T4-18",
        "nombre": "Parada Biblioteca Municipal",
        "lat": -2.1965,
        "lon": -79.8805,
        "cota_msnm": 5.5,
        "sector": "Centro",
        "demanda_hora": 3800,
        "es_terminal": False,
    },
    {
        "id": "T4-19",
        "nombre": "Parada Malecón 2000",
        "lat": -2.1945,
        "lon": -79.8785,
        "cota_msnm": 4.5,
        "sector": "Malecón",
        "demanda_hora": 5100,
        "es_terminal": False,
    },
    {
        "id": "T4-20",
        "nombre": "Parada Calle Cuenca",
        "lat": -2.1990,
        "lon": -79.8830,
        "cota_msnm": 5.9,
        "sector": "Centro Sur Retorno",
        "demanda_hora": 3300,
        "es_terminal": False,
    },
    {
        "id": "T4-21",
        "nombre": "Parada Venezuela / Chimborazo",
        "lat": -2.2010,
        "lon": -79.8865,
        "cota_msnm": 6.0,
        "sector": "Venezuela Retorno",
        "demanda_hora": 3100,
        "es_terminal": False,
    },
    {
        "id": "T4-22",
        "nombre": "Parada Venezuela / Quito",
        "lat": -2.2030,
        "lon": -79.8920,
        "cota_msnm": 5.8,
        "sector": "Venezuela Retorno",
        "demanda_hora": 3600,
        "es_terminal": False,
    },
    {
        "id": "T4-23",
        "nombre": "Terminal Central / Río Guayas",
        "lat": -2.1975,
        "lon": -79.8795,
        "cota_msnm": 4.2,
        "sector": "Ribera Centro",
        "demanda_hora": 5600,
        "es_terminal": True,
    },
]

# Traza geográfica de la Troncal 4 regular
TRAZA_TRONCAL_4_COORDS = [
    [-79.9295, -2.2272],
    [-79.9240, -2.2215],
    [-79.9210, -2.2150],
    [-79.9185, -2.2100],
    [-79.9150, -2.2070],
    [-79.9110, -2.2045],
    [-79.9075, -2.2025],
    [-79.9025, -2.2005],
    [-79.8970, -2.1985],
    [-79.8935, -2.1970],
    [-79.8905, -2.1960],
    [-79.8875, -2.1950],
    [-79.8845, -2.1940],
    [-79.8815, -2.1930],
    [-79.8860, -2.1915],
    [-79.8885, -2.1905],
    [-79.8835, -2.1925],
    [-79.8805, -2.1965],
    [-79.8785, -2.1945],
    [-79.8795, -2.1975],
    [-79.8830, -2.1990],
    [-79.8865, -2.2010],
    [-79.8920, -2.2030],
    [-79.8970, -2.1985],
]

# Traza del Bucle de Contingencia (Centro - Estación Calle 11) + Desvío Elevado
TRAZA_DESVIO_CONTINGENCIA = [
    # Bucle Seguro en Centro / Portete Alto (Cota > 5.8m)
    [-79.8970, -2.1985],  # Estación Calle 11
    [-79.8935, -2.1970],
    [-79.8905, -2.1960],
    [-79.8875, -2.1950],
    [-79.8845, -2.1940],
    [-79.8815, -2.1930],
    [-79.8785, -2.1945],
    [-79.8795, -2.1975],
    [-79.8830, -2.1990],
    [-79.8865, -2.2010],
    [-79.8920, -2.2030],
    [-79.8970, -2.1985],  # Retorno seguro Calle 11
    # Conexión Feeder Cota Alta hacia Av. Barcelona
    [-79.9025, -2.1940],
    [-79.9120, -2.1880],
    [-79.9220, -2.1850],  # Av. Barcelona (Cota 8.5m - Fuera de inundación)
]


def _obtener_marea_y_lluvia_actual() -> tuple[float, float]:
    """Obtiene los valores actuales o predeterminados del pipeline."""
    marea = 2.1
    lluvia = 0.0

    try:
        data_marea = leer_telemetria_raw("inocar", "Sin marea reciente")
        if isinstance(data_marea, dict) and "data" in data_marea:
            marea = float(data_marea["data"].get("altura_m", marea))
    except Exception:
        pass

    try:
        data_meteo = leer_telemetria_raw("open_meteo", "Sin clima reciente")
        if isinstance(data_meteo, dict) and "data" in data_meteo:
            lluvia = float(data_meteo["data"].get("precipitacion_mm", lluvia))
    except Exception:
        pass

    return marea, lluvia


@router.get(
    "/troncal4/estado",
    response_model=RespuestaAPI[dict[str, Any]],
    summary="Estado Operativo y Plan de Contingencia Troncal 4",
    description=(
        "Evalúa en tiempo real o simulado el anegamiento de los 23.7 km de la Troncal 4 "
        "por coincidencia de marea y lluvia en el Suburbio Oeste. Retorna paradas afectadas, "
        "minutos de retraso, plan de desvío y GeoJSON de rutas alternativas."
    ),
)
def estado_troncal_4(
    precip_mm: float | None = Query(None, description="Lluvia simulada o forzada en mm"),
    altura_marea_m: float | None = Query(None, description="Altura de marea simulada en metros"),
):
    marea_real, lluvia_real = _obtener_marea_y_lluvia_actual()
    marea = altura_marea_m if altura_marea_m is not None else marea_real
    lluvia = precip_mm if precip_mm is not None else lluvia_real

    # Umbrales físicos de anegamiento en Suburbio Oeste (Estero Salado)
    hay_aguaje = marea >= 2.5
    hay_represamiento = marea >= 2.3 and lluvia >= 15.0
    hay_tormenta_severa = lluvia >= 35.0

    paradas_resultado = []
    paradas_inundadas = []
    paradas_alerta = []

    for p in PARADAS_TRONCAL_4:
        cota = p["cota_msnm"]
        estado_parada = "OPERATIVA"
        nivel_agua_est_cm = 0
        alerta_parada = ""

        if hay_aguaje or hay_represamiento or hay_tormenta_severa:
            if cota <= 2.6:
                estado_parada = "INUNDADA"
                nivel_agua_est_cm = int(max(20, (marea - cota + (lluvia / 50.0)) * 50))
                alerta_parada = f"Servicio suspendido. Nivel de agua estimado: {nivel_agua_est_cm} cm. Evite la estación."
                paradas_inundadas.append(p["nombre"])
            elif cota <= 3.8:
                if hay_represamiento or hay_tormenta_severa or marea >= 2.7:
                    estado_parada = "INUNDADA"
                    nivel_agua_est_cm = int(max(10, (marea - cota + (lluvia / 60.0)) * 40))
                    alerta_parada = f"Anegamiento severo. Agua acumulada: {nivel_agua_est_cm} cm."
                    paradas_inundadas.append(p["nombre"])
                else:
                    estado_parada = "ALERTA_PREVENTIVA"
                    alerta_parada = "Cota baja. Tránsito lento de articulados."
                    paradas_alerta.append(p["nombre"])
            elif cota <= 4.5 and (lluvia >= 50.0 or marea >= 3.0):
                estado_parada = "ALERTA_PREVENTIVA"
                alerta_parada = "Acumulación moderada de agua sobre el carril exclusivo."
                paradas_alerta.append(p["nombre"])

        paradas_resultado.append({
            **p,
            "estado": estado_parada,
            "nivel_agua_est_cm": nivel_agua_est_cm,
            "alerta": alerta_parada,
        })

    # Diagnóstico y Plan de Reorganización Operativa (mov-troncal4)
    contingencia_activa = len(paradas_inundadas) > 0
    if contingencia_activa:
        estado_general = "DESVIO_CONTINGENCIA"
        demora_min = 25
        alerta_usuario = (
            f"🚨 PLAN DE CONTINGENCIA ACTIVO: {len(paradas_inundadas)} paradas del Suburbio Oeste anegadas "
            f"(Marea: {marea:.2f}m, Lluvia: {lluvia:.1f}mm). La Troncal 4 opera en Bucle Corto Centro-Portete "
            f"con retorno seguro en Estación Calle 11 (Cota 5.8m). Alimentadores desviados por cota alta."
        )
        plan_contingencia = {
            "activo": True,
            "estrategia": "Bucle Troncal Centro-Portete + Transbordo Seguro",
            "estacion_transbordo_seguro": "Estación Calle 11 (Cota 5.8 msnm)",
            "frecuencia_bucle_centro_min": 5,
            "frecuencia_alimentadores_suburbio_min": 14,
            "paradas_suspendidas": paradas_inundadas,
            "paradas_en_alerta": paradas_alerta,
            "ruta_alternativa_sugerida": (
                "Para usuarios del Batallón del Suburbio, abordar unidades de contingencia en "
                "Av. Barcelona hacia el Centro, evitando el tramo anegado de la Calle 34 a la 29."
            ),
        }
    elif len(paradas_alerta) > 0:
        estado_general = "RETRASO_MODERADO"
        demora_min = 10
        alerta_usuario = (
            f"⚠️ SERVICIO CON RETRASOS: Acumulación de agua en sectores bajos de Portete. "
            f"Retraso estimado de {demora_min} minutos. Todas las estaciones abiertas."
        )
        plan_contingencia = {"activo": False, "estrategia": "Operación estándar con reducción de velocidad"}
    else:
        estado_general = "OPERATIVO_NORMAL"
        demora_min = 0
        alerta_usuario = "✅ Servicio regular y fluido en los 23.7 km de la Troncal 4. Las 23 estaciones operativas."
        plan_contingencia = {"activo": False, "estrategia": "Operación regular estándar"}

    geojson_regular = {
        "type": "Feature",
        "properties": {
            "nombre": "Troncal 4 (Regular)",
            "longitud_km": 23.7,
            "color": "#ef4444" if contingencia_activa else "#3b82f6",
        },
        "geometry": {"type": "LineString", "coordinates": TRAZA_TRONCAL_4_COORDS},
    }

    geojson_desvio = {
        "type": "Feature",
        "properties": {
            "nombre": "Troncal 4 - Bucle Contingencia & Cota Alta",
            "activo": contingencia_activa,
            "color": "#22c55e",
        },
        "geometry": {"type": "LineString", "coordinates": TRAZA_DESVIO_CONTINGENCIA},
    }

    geojson_paradas = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [p["lon"], p["lat"]]},
                "properties": {
                    "id": p["id"],
                    "nombre": p["nombre"],
                    "estado": p["estado"],
                    "cota_msnm": p["cota_msnm"],
                    "sector": p["sector"],
                    "nivel_agua_est_cm": p["nivel_agua_est_cm"],
                    "alerta": p["alerta"],
                    "es_transbordo": p.get("punto_retorno_contingencia", False),
                },
            }
            for p in paradas_resultado
        ],
    }

    data_payload = {
        "linea": "Troncal 4: Batallón del Suburbio - Centro",
        "longitud_km": 23.7,
        "usuarios_dia_estimados": 120000,
        "estado_general": estado_general,
        "demora_estimada_min": demora_min,
        "tiempo_total_viaje_min": 40 + demora_min,
        "alerta_pasajero": alerta_usuario,
        "marea_referencia_m": round(marea, 2),
        "lluvia_referencia_mm": round(lluvia, 1),
        "total_paradas": len(paradas_resultado),
        "paradas_inundadas_total": len(paradas_inundadas),
        "paradas_alerta_total": len(paradas_alerta),
        "plan_contingencia": plan_contingencia,
        "geojson_regular": geojson_regular,
        "geojson_desvio": geojson_desvio,
        "geojson_paradas": geojson_paradas,
    }

    return respuesta_exitosa(data_payload, fuente="modelo_vulnerabilidad_metrovia_t4")


@router.get(
    "/troncales/resumen",
    response_model=RespuestaAPI[dict[str, Any]],
    summary="Resumen Operativo de las 4 Troncales de la Metrovía",
    description="Semáforo global para evitar el colapso de estaciones y avisar a los pasajeros.",
)
def resumen_troncales():
    marea, lluvia = _obtener_marea_y_lluvia_actual()

    # Estado de las 4 troncales operativas de Guayaquil
    t4_afectada = (marea >= 2.4 and lluvia >= 10.0) or (marea >= 2.6) or (lluvia >= 30.0)
    t1_afectada = (marea >= 2.7) or (lluvia >= 40.0)  # Guasmo Sur
    t2_afectada = lluvia >= 45.0  # Av. 25 de Julio
    t3_afectada = lluvia >= 50.0  # Bastión / Parque California

    troncales = [
        {
            "id": "T1",
            "nombre": "Troncal 1: Guasmo - Terminal Río Daule",
            "recorrido_km": 28.5,
            "estado": "RETRASO_MODERADO" if t1_afectada else "OPERATIVO",
            "retraso_min": 15 if t1_afectada else 0,
            "alerta": "Puntos de anegamiento en Guasmo Sur (Av. Domingo Comín)" if t1_afectada else "Servicio normal",
            "color": "#facc15" if t1_afectada else "#22c55e",
        },
        {
            "id": "T2",
            "nombre": "Troncal 2: 25 de Julio - Terminal Río Daule",
            "recorrido_km": 26.0,
            "estado": "RETRASO_MODERADO" if t2_afectada else "OPERATIVO",
            "retraso_min": 12 if t2_afectada else 0,
            "alerta": "Congestión por acumulación de agua cerca de Mall del Sur" if t2_afectada else "Servicio normal",
            "color": "#facc15" if t2_afectada else "#22c55e",
        },
        {
            "id": "T3",
            "nombre": "Troncal 3: Bastión Popular - Centro",
            "recorrido_km": 21.0,
            "estado": "RETRASO_MODERADO" if t3_afectada else "OPERATIVO",
            "retraso_min": 18 if t3_afectada else 0,
            "alerta": "Tránsito restringido en Vía a Daule / Parque California" if t3_afectada else "Servicio normal",
            "color": "#facc15" if t3_afectada else "#22c55e",
        },
        {
            "id": "T4",
            "nombre": "Troncal 4: Batallón del Suburbio - Centro",
            "recorrido_km": 23.7,
            "estado": "DESVIO_CONTINGENCIA" if t4_afectada else "OPERATIVO",
            "retraso_min": 25 if t4_afectada else 0,
            "alerta": "Anegamiento por Estero Salado. Bucle contingencia activo en Estación Calle 11." if t4_afectada else "Servicio normal",
            "color": "#ef4444" if t4_afectada else "#22c55e",
        },
    ]

    return respuesta_exitosa({
        "sistema": "Sistema Metrovía Guayaquil",
        "troncales_activas_total": 4,
        "marea_actual_m": round(marea, 2),
        "lluvia_actual_mm": round(lluvia, 1),
        "troncales": troncales,
    }, fuente="control_operativo_metrovia")
