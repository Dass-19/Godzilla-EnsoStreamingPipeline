"""
Script de Ingesta para Índices Macro-Climáticos ENSO.
Descarga Presión a Nivel del Mar de Tahití y Darwin para calcular un proxy del SOI.
"""

import datetime
import os

import requests
from common.kafka_client import build_producer, logger, run_loop

INTERVAL_SECONDS = int(os.environ.get("INTERVALO_INDICES", 60 * 60))

# Coordenadas exactas
TAHITI = {"lat": -17.65, "lon": -149.46}
DARWIN = {"lat": -12.46, "lon": 130.84}


def fetch_pressure(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=surface_pressure,pressure_msl&timezone=UTC"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data["current"]["pressure_msl"]
        logger.error("Open-Meteo presión respondió %s para %s,%s", response.status_code, lat, lon)
    except Exception:
        logger.exception("Error obteniendo datos para %s,%s", lat, lon)
    return None


def ingest_data():
    logger.info("Calculando Índice de Oscilación del Sur (SOI)...")
    tahiti_mslp = fetch_pressure(TAHITI["lat"], TAHITI["lon"])
    darwin_mslp = fetch_pressure(DARWIN["lat"], DARWIN["lon"])

    if tahiti_mslp is None or darwin_mslp is None:
        logger.error("Falló la extracción de presión para SOI.")
        return

    soi_proxy = tahiti_mslp - darwin_mslp

    # Evaluar estado rápido
    if soi_proxy < -1.0:
        status = "Fase El Niño (Acoplamiento Atmosférico)"
    elif soi_proxy > 1.0:
        status = "Fase La Niña"
    else:
        status = "Fase Neutra"

    logger.info("SOI proxy=%s estado=%s", soi_proxy, status)

    record = {
        "date": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d"),
        "tahiti_mslp_hpa": tahiti_mslp,
        "darwin_mslp_hpa": darwin_mslp,
        "soi_proxy_diff": soi_proxy,
        "enso_status": status,
    }

    payload = {
        "metadata": {
            "source": "Open-Meteo (Forecast API)",
            "description": "Southern Oscillation Index (Proxy)",
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        },
        "data": [record],
    }
    return payload


def run_producer():
    producer = build_producer()

    def _fetch():
        data = ingest_data()
        if data:
            return [data]
        return []

    run_loop(producer, "enso-indexes", _fetch, interval_seconds=INTERVAL_SECONDS)


if __name__ == "__main__":
    run_producer()
