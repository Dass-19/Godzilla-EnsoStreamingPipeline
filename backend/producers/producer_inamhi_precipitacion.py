"""
Productor de lluvia observada por estaciones automáticas de INAMHI en Guayas.

Consulta el endpoint API Visor de INAMHI para descubrir estaciones en la
provincia de Guayas (provincia 09) y extrae la lluvia acumulada en 24h para
aquellas con datos vigentes. Habilita la interpolación espacial por IDW en el
job de Spark.
"""

import os

import requests
from common.kafka_client import build_producer, logger, run_loop
from contracts import TOPIC_PRECIP_ESTACIONES, construir_lluvia_estacion

INTERVAL_SECONDS = int(os.environ.get("INTERVALO_PRECIPITACION", 15 * 60))

URL_ESTACIONES = "https://inamhi.gob.ec/api_visor/station_information/estaciones/?id_provincia=09"
URL_PRECIPITACION = "https://inamhi.gob.ec/api_visor/station_data_automaticas/get_precipitation/"


def fetch_inamhi_precipitacion() -> dict:
    """Descubre estaciones de Guayas y extrae acumulados recientes."""
    logger.info("Consultando catálogo INAMHI en %s", URL_ESTACIONES)
    try:
        resp_est = requests.get(URL_ESTACIONES, timeout=10)
        if not resp_est.ok:
            logger.warning("INAMHI API respondió HTTP %s en %s", resp_est.status_code, URL_ESTACIONES)
            return {}
        cat_estaciones = resp_est.json()
    except Exception:
        logger.exception("Error consultando catálogo INAMHI en %s", URL_ESTACIONES)
        return {}

    estaciones_operativas = [est for est in cat_estaciones if isinstance(est, dict) and est.get("estado_estacion") == "OPERATIVA"]
    estaciones_validas = []

    for est in estaciones_operativas:
        id_est = est.get("id_estacion")
        if not id_est:
            continue

        lat = est.get("latitud")
        lon = est.get("longitud")
        if lat is None or lon is None:
            continue

        try:
            resp_data = requests.post(URL_PRECIPITACION, json={"id_estacion": id_est}, timeout=8)
            if not resp_data.ok:
                continue
            data = resp_data.json()
        except Exception:
            continue

        precip_24h = 0.0
        fecha_ultimo = ""
        serie_15d = []

        if isinstance(data, list) and data:
            # Tomamos la lectura más reciente
            lectura_reciente = data[-1]
            precip_24h = float(lectura_reciente.get("valor", 0.0) or 0.0)
            fecha_ultimo = str(lectura_reciente.get("fecha_observacion", ""))

            # Construimos la serie diaria de los últimos 15 días si existe
            for d in data[-15:]:
                if isinstance(d, dict):
                    val = float(d.get("valor", 0.0) or 0.0)
                    fecha_d = str(d.get("fecha_observacion", ""))
                    serie_15d.append({"fecha": fecha_d, "precip_mm": val})

            estaciones_validas.append(
                construir_lluvia_estacion(
                    id_estacion=str(id_est),
                    codigo=str(est.get("codigo_estacion", id_est)),
                    lat=float(lat),
                    lon=float(lon),
                    precip_24h_mm=precip_24h,
                    fecha_ultimo_dato=fecha_ultimo,
                    serie_diaria_15d=serie_15d,
                )
            )

    return {"estaciones": estaciones_validas, "total_operativas": len(estaciones_operativas)}


def fetch_payloads() -> list[dict]:
    data = fetch_inamhi_precipitacion()
    if data and data.get("estaciones"):
        logger.info(
            "INAMHI lluvia: %s de %s estaciones operativas en Guayas enviaron datos desde %s",
            len(data["estaciones"]),
            data.get("total_operativas", 0),
            URL_PRECIPITACION,
        )
        return [data]
    total_op = data.get("total_operativas", 0) if data else 0
    logger.warning(
        "INAMHI lluvia: %s estaciones operativas encontradas en Guayas, pero 0 tienen transmisiones recientes en %s",
        total_op,
        URL_PRECIPITACION,
    )
    return []


def run_producer():
    producer = build_producer()
    run_loop(producer, TOPIC_PRECIP_ESTACIONES, fetch_payloads, INTERVAL_SECONDS)


if __name__ == "__main__":
    run_producer()
