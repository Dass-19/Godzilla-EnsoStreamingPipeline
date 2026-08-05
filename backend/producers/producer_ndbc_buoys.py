"""
Script de Ingesta para Boyas Oceanográficas (NDBC TAO Array).
Extrae datos para las boyas 32320 (Niño 1+2 / Galápagos) y 32321 (Niño 3).
"""

import datetime
import os

import requests
from common.kafka_client import build_producer, logger, run_loop

INTERVAL_SECONDS = int(os.environ.get("INTERVALO_INDICES", 60 * 60))

BUOYS = [
    {"id": "32320", "name": "Boya TAO 95W (Galápagos)", "lat": 0.0, "lon": -95.0},
    {"id": "32321", "name": "Boya TAO 110W (Pacífico Central)", "lat": 0.0, "lon": -110.0},
]

VARIABLES = "wave_height,ocean_current_velocity,sea_surface_temperature"


def fetch_buoy_data(buoy):
    """
    Lee oleaje, corriente y temperatura superficial del punto de la boya desde
    la Marine API de Open-Meteo. Si la API no la devuelve, el campo va en `null`
    y `fuente_sst` lo marca como no disponible.
    """
    url = (
        "https://marine-api.open-meteo.com/v1/marine"
        f"?latitude={buoy['lat']}&longitude={buoy['lon']}&current={VARIABLES}"
    )
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        current = data.get("current", {})

        water_temp = current.get("sea_surface_temperature")

        return {
            "buoy_id": buoy["id"],
            "name": buoy["name"],
            "latitude": buoy["lat"],
            "longitude": buoy["lon"],
            "water_temp_c": water_temp,
            "fuente_sst": "open_meteo_marine" if water_temp is not None else "no_disponible",
            "wave_height_m": current.get("wave_height"),
            "current_velocity_kmh": current.get("ocean_current_velocity"),
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        }
    except Exception:
        logger.exception("Error obteniendo datos para la boya %s", buoy["id"])
        return None


def ingest_data():
    logger.info("Obteniendo datos en tiempo real de boyas oceánicas...")
    records = []
    for buoy in BUOYS:
        data = fetch_buoy_data(buoy)
        if data:
            records.append(data)

    if not records:
        return None

    return records


def run_producer():
    producer = build_producer()

    def _fetch():
        data = ingest_data()
        if data:
            # Empaquetar como un solo mensaje tipo FeatureCollection (para MapLibre)
            features = []
            for r in data:
                features.append(
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [r["longitude"], r["latitude"]],
                        },
                        "properties": {
                            "id": r["buoy_id"],
                            "name": r["name"],
                            "water_temp_c": r["water_temp_c"],
                            "fuente_sst": r["fuente_sst"],
                            "wave_height_m": r["wave_height_m"],
                            "current_velocity_kmh": r["current_velocity_kmh"],
                        },
                    }
                )

            geojson = {"type": "FeatureCollection", "features": features}
            return [geojson]
        return []

    run_loop(producer, "ndbc-buoys", _fetch, interval_seconds=INTERVAL_SECONDS)


if __name__ == "__main__":
    run_producer()
