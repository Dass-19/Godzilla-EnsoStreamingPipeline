"""
Productor de pronóstico cuantitativo de precipitación (Open-Meteo).

Obtiene el acumulado de lluvia y probabilidad máxima pronosticada para
Guayaquil (-2.19, -79.89) con horizonte a 24h.
"""

import os

import requests
from common.kafka_client import build_producer, run_loop
from contracts import TOPIC_PRECIP_PRONOSTICO, construir_pronostico_precip

INTERVAL_SECONDS = int(os.environ.get("INTERVALO_PRONOSTICO", 30 * 60))
LAT_GUAYAQUIL = -2.19
LON_GUAYAQUIL = -79.89

URL_OPEN_METEO = (
    "https://api.open-meteo.com/v1/forecast"
    f"?latitude={LAT_GUAYAQUIL}&longitude={LON_GUAYAQUIL}"
    "&daily=precipitation_sum,precipitation_probability_max"
    "&timezone=America%2FGuayaquil&past_days=1&forecast_days=7"
)


def fetch_pronostico_precip() -> list[dict]:
    try:
        resp = requests.get(URL_OPEN_METEO, timeout=10)
        if not resp.ok:
            print(f"[-] Open-Meteo pronóstico respondió {resp.status_code}")
            return []
        data = resp.json()

        daily = data.get("daily", {})
        times = daily.get("time", [])
        precip_sums = daily.get("precipitation_sum", [])
        prob_maxs = daily.get("precipitation_probability_max", [])

        if not times or not precip_sums:
            return []

        # Usamos la previsión para hoy/mañana (horizonte 24h)
        idx = 1 if len(times) > 1 else 0
        fecha = times[idx]
        precip = float(precip_sums[idx] or 0.0)
        prob = (
            float(prob_maxs[idx]) if idx < len(prob_maxs) and prob_maxs[idx] is not None else None
        )

        payload = construir_pronostico_precip(
            fecha=fecha,
            lat=LAT_GUAYAQUIL,
            lon=LON_GUAYAQUIL,
            precip_sum_mm=precip,
            precip_probability_max=prob,
            horizonte_h=24,
        )
        print(f"[+] Pronóstico precipitación 24h: {precip} mm")
        return [payload]
    except Exception as e:
        print(f"[-] Error consultando pronóstico Open-Meteo: {e}")
        return []


def run_producer():
    producer = build_producer()
    run_loop(producer, TOPIC_PRECIP_PRONOSTICO, fetch_pronostico_precip, INTERVAL_SECONDS)


if __name__ == "__main__":
    run_producer()
