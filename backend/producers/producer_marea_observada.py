"""
Productor de marea observada en tiempo real desde el mareógrafo IOC.

Consulta la estación radar `gyer` (Guayaquil - Río Guayas, lat -2.195, lon
-79.88) y como respaldo la estación `puna`. Publica la altura real observada
en metros.
"""

from __future__ import annotations

import os

import certifi
import requests
from common.kafka_client import build_producer, logger, run_loop
from contracts import TOPIC_MAREA_OBSERVADA, construir_marea_observada

INTERVAL_SECONDS = int(os.environ.get("INTERVALO_MAREA_OBS", 15 * 60))

URL_IOC_GYER = "https://www.ioc-sealevelmonitoring.org/service.php?query=data&code=gyer&format=json"
URL_IOC_PUNA = "https://www.ioc-sealevelmonitoring.org/service.php?query=data&code=puna&format=json"


def fetch_marea_ioc(url: str, estacion_id: str) -> dict | None:
    try:
        resp = requests.get(url, timeout=10, verify=certifi.where())
        if not resp.ok:
            logger.warning("IOC %s respondió %s", estacion_id, resp.status_code)
            return None
        data = resp.json()
        if not isinstance(data, list) or not data:
            logger.warning("IOC %s: sin mediciones", estacion_id)
            return None

        # La última entrada trae la medición de nivel más reciente
        medicion = data[-1]
        if not isinstance(medicion, dict):
            logger.warning("IOC %s: medición con formato inesperado", estacion_id)
            return None

        # slevel es la columna de altura del mareógrafo
        altura = medicion.get("slevel")
        if altura is None:
            logger.warning("IOC %s: medición sin nivel", estacion_id)
            return None

        fecha = medicion.get("stime") or medicion.get("date")
        return construir_marea_observada(
            altura_m=float(altura),
            estacion=estacion_id,
            puerto="Guayaquil - Rio Guayas" if estacion_id == "gyer" else "Isla Puna",
            sensor="radar",
            fecha_utc=str(fecha) if fecha else None,
        )
    except Exception:
        logger.exception("Error consultando marea IOC (%s)", estacion_id)
        return None


def fetch_payloads() -> list[dict]:
    # Primero intentamos la estación principal en Guayaquil (gyer)
    payload = fetch_marea_ioc(URL_IOC_GYER, "gyer")
    if payload:
        logger.info("Marea observada (gyer): %s m", payload["altura_marea_m"])
        return [payload]

    # Respaldo: estación Puná
    logger.warning("Marea observada: gyer sin dato, probando respaldo puna")
    payload = fetch_marea_ioc(URL_IOC_PUNA, "puna")
    if payload:
        logger.info("Marea observada (respaldo puna): %s m", payload["altura_marea_m"])
        return [payload]

    logger.error("Marea observada: sin datos disponibles")
    return []


def run_producer():
    producer = build_producer()
    run_loop(producer, TOPIC_MAREA_OBSERVADA, fetch_payloads, INTERVAL_SECONDS)


if __name__ == "__main__":
    run_producer()
