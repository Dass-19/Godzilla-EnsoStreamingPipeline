"""
Productor de nivel de río desde estaciones hidrológicas de INAMHI.

Dato de contexto (no alimenta el índice directamente debido a la latencia de
9 a 24 días en la transmisión).
"""

import os

import requests
from common.kafka_client import build_producer, logger, run_loop

INTERVAL_SECONDS = int(os.environ.get("INTERVALO_NIVEL_RIO", 12 * 60 * 60))
TOPIC_NIVEL_RIO = "inamhi-nivel-rio"

URL_ESTACIONES_HIDRO = (
    "https://inamhi.gob.ec/api_visor/station_information/estaciones/?id_provincia=09"
)
URL_NIVEL_RIO = "https://inamhi.gob.ec/api_visor/station_data_automaticas/get_data_hour/"


def fetch_inamhi_nivel_rio() -> list[dict]:
    logger.info("Consultando estaciones hidrológicas de INAMHI en %s", URL_ESTACIONES_HIDRO)
    try:
        resp = requests.get(URL_ESTACIONES_HIDRO, timeout=10)
        if not resp.ok:
            logger.warning("INAMHI nivel de río: catálogo respondió HTTP %s en %s", resp.status_code, URL_ESTACIONES_HIDRO)
            return []
        cat = resp.json()

        cat_hidro = [est for est in cat if isinstance(est, dict) and "HIDRO" in str(est.get("categoria", ""))]
        estaciones_operativas = [est for est in cat_hidro if est.get("estado_estacion") == "OPERATIVA"]

        payloads = []
        for est in estaciones_operativas:
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
                logger.warning("INAMHI nivel de río: falla en estación %s en %s", id_est, URL_NIVEL_RIO)
                continue

        if payloads:
            logger.info("INAMHI nivel de río: %s estaciones hidrológicas con datos desde %s", len(payloads), URL_NIVEL_RIO)
        else:
            logger.warning(
                "INAMHI nivel de río: %s estaciones hidrológicas registradas en Guayas, pero 0 están operativas/transmitiendo mediciones en %s",
                len(cat_hidro),
                URL_NIVEL_RIO,
            )
        return payloads
    except Exception:
        logger.exception("Error INAMHI nivel de río en %s", URL_ESTACIONES_HIDRO)
        return []


def run_producer():
    producer = build_producer()
    run_loop(producer, TOPIC_NIVEL_RIO, fetch_inamhi_nivel_rio, INTERVAL_SECONDS)


if __name__ == "__main__":
    run_producer()
