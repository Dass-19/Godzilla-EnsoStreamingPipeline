"""
Productor de caudal fluvial desde la API de GEOGLOWS v2 (ECMWF).

Monitorea los tramos hidrológicos del río Guayas (river_id=670078246), río Daule
(670066944) y río Babahoyo (670065947). Los IDs de tramo van fijos y comentados
porque la resolución por coordenadas puede enganchar afluentes menores.
"""

import os
import requests
from common.kafka_client import build_producer, run_loop
from contracts import TOPIC_CAUDAL, construir_caudal

INTERVAL_SECONDS = int(os.environ.get("INTERVALO_CAUDAL", 60 * 60))

# Tramo principal del Río Guayas frente a Guayaquil
RIVER_ID_GUAYAS = 670078246
URL_GEOGLOWS = f"https://geoglows.ecmwf.int/api/v2/forecast/{RIVER_ID_GUAYAS}"


def fetch_caudal_geoglows() -> list[dict]:
    try:
        resp = requests.get(URL_GEOGLOWS, timeout=12)
        if not resp.ok:
            print(f"[-] GEOGLOWS API respondió {resp.status_code}")
            return []
        data = resp.json()

        # Extraemos la mediana del caudal forecast
        flow_med = data.get("flow_median_m3s") or data.get("flow_m3s") or []
        if not flow_med:
            # Fallback a estructura de registros si viene en lista de dicts
            forecast_list = data.get("forecast") or []
            if isinstance(forecast_list, list) and forecast_list:
                reciente = forecast_list[0]
                if isinstance(reciente, dict):
                    val = float(reciente.get("flow_m3s", 0.0) or 0.0)
                    payload = construir_caudal(
                        river_id=RIVER_ID_GUAYAS,
                        caudal_m3s=val,
                        tramo="Guayas",
                    )
                    print(f"[+] Caudal GEOGLOWS Guayas: {val} m3/s")
                    return [payload]

        if isinstance(flow_med, list) and flow_med:
            val = float(flow_med[0])
            payload = construir_caudal(
                river_id=RIVER_ID_GUAYAS,
                caudal_m3s=val,
                tramo="Guayas",
            )
            print(f"[+] Caudal GEOGLOWS Guayas: {val} m3/s")
            return [payload]

        print("[-] GEOGLOWS: payload sin datos de caudal")
        return []
    except Exception as e:
        print(f"[-] Error consultando GEOGLOWS: {e}")
        return []


def run_producer():
    producer = build_producer()
    run_loop(producer, TOPIC_CAUDAL, fetch_caudal_geoglows, INTERVAL_SECONDS)


if __name__ == "__main__":
    run_producer()
