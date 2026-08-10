"""
Script de Ingesta para Open-Meteo.
Descarga variables atmosféricas clave de la región Niño 3.4 (Pacífico Central).
Variables: Temperatura, Precipitación, Vientos Alisios (Velocidad y Dirección) y Presión Superficial.
"""

import datetime
import os

import requests
from common.kafka_client import build_producer, logger, run_loop

ENDPOINT = "https://archive-api.open-meteo.com/v1/archive"

# Centro de la región Niño 3.4 (Pacífico central). OJO: no es Guayaquil; estos
# datos describen el estado del ENSO, no la lluvia local. La precipitación que
# alimenta el índice de riesgo sale de NASA POWER, que sí consulta Guayaquil.
LATITUD_NINO34 = 0.0
LONGITUD_NINO34 = -143.0

INTERVAL_SECONDS = int(os.environ.get("INTERVALO_CLIMA", 60 * 60))
VENTANA_DIAS = int(os.environ.get("VENTANA_DIAS_CLIMA", 15))


def _ventana_fechas():
    hoy = datetime.datetime.now(datetime.UTC).date()
    desde = hoy - datetime.timedelta(days=VENTANA_DIAS)
    return desde.isoformat(), hoy.isoformat()


def ingest_data():
    logger.info("Descargando variables atmosféricas predictivas de Open-Meteo desde %s...", ENDPOINT)
    inicio, fin = _ventana_fechas()
    params = {
        "latitude": LATITUD_NINO34,
        "longitude": LONGITUD_NINO34,
        "start_date": inicio,
        "end_date": fin,
        "daily": "temperature_2m_mean,precipitation_sum,wind_speed_10m_max,wind_direction_10m_dominant,shortwave_radiation_sum",
        "timezone": "UTC",
    }
    try:
        response = requests.get(ENDPOINT, params=params, timeout=15)
        if response.status_code != 200:
            logger.error("Open-Meteo respondió %s en %s", response.status_code, ENDPOINT)
            return None

        raw_data = response.json()

        records = []
        if "daily" in raw_data:
            daily = raw_data["daily"]
            for i, date_str in enumerate(daily.get("time", [])):
                record = {
                    "date": date_str,
                    "mean_air_temp_c": daily.get("temperature_2m_mean", [])[i],
                    "precipitation_sum_mm": daily.get("precipitation_sum", [])[i],
                    "max_wind_speed_ms": daily.get("wind_speed_10m_max", [])[i],
                    "dominant_wind_direction_deg": daily.get("wind_direction_10m_dominant", [])[i],
                    "shortwave_radiation_mj_m2": daily.get("shortwave_radiation_sum", [])[i],
                }
                records.append(record)

        if not records:
            logger.error("Open-Meteo: respuesta sin bloque diario desde %s", ENDPOINT)
        else:
            logger.info("Open-Meteo: %s registros diarios desde %s", len(records), ENDPOINT)

        return {
            "metadata": {
                "source": "Open-Meteo Archive API",
                "region": f"Niño 3.4 (Lat {LATITUD_NINO34}, Lon {LONGITUD_NINO34})",
                "ventana": {"desde": inicio, "hasta": fin},
                "variables": [
                    "temperature_2m_mean (Coupling océano-atmósfera)",
                    "precipitation_sum (Lluvias ecuatoriales)",
                    "wind_speed_10m_max (Fuerza de los Vientos Alisios)",
                    "wind_direction_10m_dominant (Dirección del viento)",
                    "shortwave_radiation_sum (Cobertura de nubes)",
                ],
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            },
            "data": records,
        }
    except Exception:
        logger.exception("Error al descargar/procesar datos de Open-Meteo desde %s", ENDPOINT)
        return None


def run_producer():
    producer = build_producer()

    def _fetch():
        data = ingest_data()
        if data:
            return [data]
        return []

    run_loop(producer, "open-meteo-data", _fetch, interval_seconds=INTERVAL_SECONDS)


if __name__ == "__main__":
    run_producer()
