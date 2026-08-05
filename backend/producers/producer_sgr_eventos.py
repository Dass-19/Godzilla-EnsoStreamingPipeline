"""
Script de Ingesta para SGR Eventos de Lluvia.
Consulta la API de FeatureServer de Gestión de Riesgos para obtener eventos
de lluvia en cantones clave de la cuenca del Guayas (Guayaquil, Daule, etc.).
"""

import json
import os
import urllib.parse
import urllib.request

from common.kafka_client import build_producer, logger, run_loop

INTERVAL_SECONDS = int(os.environ.get("INTERVALO_ALERTAS", 15 * 60))


def fetch_sgr_events():
    logger.info("Descargando eventos de lluvia (SGR)...")

    # Filtramos eventos solo para Guayaquil, Daule, Samborondón y Durán
    where_clause = "canton IN ('GUAYAQUIL', 'DAULE', 'SAMBORONDON', 'DURAN')"
    url = f"https://sgrportal.gestionderiesgos.gob.ec/server/rest/services/Hosted/EVENTOS_X_LLUVIAS/FeatureServer/0/query?where={urllib.parse.quote(where_clause)}&outFields=*&outSR=4326&f=geojson"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))

            features = data.get("features", [])
            if features:
                logger.info("Eventos SGR: %s registros", len(features))
            else:
                logger.error("Eventos SGR: respuesta sin features")

            return data
    except Exception:
        logger.exception("Error descargando eventos SGR")


def run_producer():
    producer = build_producer()

    def _fetch():
        data = fetch_sgr_events()
        if data:
            wrapped = {"metadata": {"source": "SGR Eventos Lluvia"}, "data": data}
            return [wrapped]
        return []

    run_loop(producer, "sgr-eventos", _fetch, interval_seconds=INTERVAL_SECONDS)


if __name__ == "__main__":
    run_producer()
