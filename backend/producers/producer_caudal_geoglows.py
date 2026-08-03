"""
Productor de caudal fluvial desde la API de GEOGLOWS v2 (ECMWF).

Consulta el tramo del río Guayas frente a Guayaquil (river_id=670078246), fijo
y comentado en el código porque la resolución por coordenadas puede enganchar
afluentes menores (ver `RIVER_ID_GUAYAS`).
"""

from __future__ import annotations

import csv
import io
import os

import requests
from common.kafka_client import build_producer, run_loop
from contracts import TOPIC_CAUDAL, construir_caudal

INTERVAL_SECONDS = int(os.environ.get("INTERVALO_CAUDAL", 60 * 60))

# Tramo principal del Río Guayas frente a Guayaquil
RIVER_ID_GUAYAS = 670078246
URL_GEOGLOWS = f"https://geoglows.ecmwf.int/api/v2/forecast/{RIVER_ID_GUAYAS}"

# Otros tramos identificados y validados por magnitud de caudal, no ingeridos
# hoy porque el índice solo necesita el Guayas: Daule aguas abajo de
# Daule-Peripa (river_id=670066944) y Babahoyo (river_id=670065947).


def fetch_caudal_geoglows() -> list[dict]:
    try:
        resp = requests.get(URL_GEOGLOWS, params={"format": "json"}, timeout=12)
        if not resp.ok:
            print(f"[-] GEOGLOWS API respondió {resp.status_code}")
            return []

        caudal_val = None

        # 1. Intento de parseo JSON (?format=json)
        try:
            data = resp.json()
            if isinstance(data, dict):
                flow_med = (
                    data.get("flow_median")
                    or data.get("flow_median_m3s")
                    or data.get("flow_m3s")
                    or []
                )
                if isinstance(flow_med, list) and flow_med:
                    caudal_val = float(flow_med[0])
                elif isinstance(flow_med, (int, float)):
                    caudal_val = float(flow_med)
        except Exception:
            pass

        # 2. Fallback a parseo CSV (si la API responde en formato CSV)
        if caudal_val is None:
            try:
                f = io.StringIO(resp.text)
                reader = csv.DictReader(f)
                for row in reader:
                    val_str = (
                        row.get("flow_median") or row.get("flow_median_m3s") or row.get("flow_m3s")
                    )
                    if val_str:
                        caudal_val = float(val_str)
                        break
            except Exception:
                pass

        if caudal_val is not None:
            payload = construir_caudal(
                river_id=RIVER_ID_GUAYAS,
                caudal_m3s=caudal_val,
                tramo="Guayas",
            )
            print(f"[+] Caudal GEOGLOWS Guayas: {caudal_val} m3/s")
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
