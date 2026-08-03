"""
Productor de nivel de río desde estaciones hidrológicas de INAMHI.

Dato de contexto (no alimenta el índice directamente debido a la latencia de
9 a 24 días en la transmisión).
"""

import os

import requests
from common.kafka_client import build_producer, run_loop

INTERVAL_SECONDS = int(os.environ.get("INTERVALO_NIVEL_RIO", 12 * 60 * 60))
TOPIC_NIVEL_RIO = "inamhi-nivel-rio"

URL_ESTACIONES_HIDRO = (
    "https://inamhi.gob.ec/api_visor/station_information/estaciones/?id_provincia=09"
)
URL_NIVEL_RIO = "https://inamhi.gob.ec/api_visor/station_data_automaticas/get_data_hour/"


def fetch_inamhi_nivel_rio() -> list[dict]:
    try:
        resp = requests.get(URL_ESTACIONES_HIDRO, timeout=10)
        if not resp.ok:
            return []
        cat = resp.json()

        payloads = []
        for est in cat:
            if not isinstance(est, dict) or est.get("tipo") != "HIDROLOGICA":
                continue
            id_est = est.get("id_estacion")
            if not id_est:
                continue

            try:
                r_n = requests.post(
                    URL_NIVEL_RIO,
                    json={"id_estacion": id_est, "id_parametro": 14},
                    timeout=8,
                )
                if not r_n.ok:
                    continue
                d_n = r_n.json()
                if isinstance(d_n, list) and d_n:
                    reciente = d_n[-1]
                    payloads.append(
                        {
                            "id_estacion": str(id_est),
                            "codigo": str(est.get("codigo_estacion", "")),
                            "nivel_m": float(reciente.get("valor", 0.0) or 0.0),
                            "fecha": str(reciente.get("fecha_observacion", "")),
                        }
                    )
            except Exception:
                continue

        if payloads:
            print(f"[+] INAMHI nivel de río: {len(payloads)} estaciones hidrológicas")
        return payloads
    except Exception as e:
        print(f"[-] Error INAMHI nivel de río: {e}")
        return []


def run_producer():
    producer = build_producer()
    run_loop(producer, TOPIC_NIVEL_RIO, fetch_inamhi_nivel_rio, INTERVAL_SECONDS)


if __name__ == "__main__":
    run_producer()
