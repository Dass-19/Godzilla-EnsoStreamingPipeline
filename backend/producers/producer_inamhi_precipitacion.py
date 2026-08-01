"""
Productor de lluvia observada por estaciones automáticas de INAMHI en Guayas.

Consulta el endpoint API Visor de INAMHI para descubrir estaciones en la
provincia de Guayas (provincia 09) y extrae la lluvia acumulada en 24h para
aquellas con datos vigentes. Habilita la interpolación espacial por IDW en el
job de Spark.
"""

import os
import requests
from common.kafka_client import build_producer, run_loop
from contracts import TOPIC_PRECIP_ESTACIONES, construir_lluvia_estacion

INTERVAL_SECONDS = int(os.environ.get("INTERVALO_PRECIPITACION", 15 * 60))

URL_ESTACIONES = "https://inamhi.gob.ec/api_visor/station_information/estaciones/?id_provincia=09"
URL_PRECIPITACION = "https://inamhi.gob.ec/api_visor/station_data_automaticas/get_precipitation/"


def fetch_inamhi_precipitacion() -> dict:
    """Descubre estaciones de Guayas y extrae acumulados recientes."""
    try:
        resp_est = requests.get(URL_ESTACIONES, timeout=10)
        if not resp_est.ok:
            print(f"[-] INAMHI API respondió {resp_est.status_code}")
            return {}
        cat_estaciones = resp_est.json()
    except Exception as e:
        print(f"[-] Error consultando catálogo INAMHI: {e}")
        return {}

    estaciones_validas = []

    for est in cat_estaciones:
        if not isinstance(est, dict):
            continue
        if est.get("estado_transmision") != "TRANSMITIENDO":
            continue

        id_est = est.get("id_estacion")
        if not id_est:
            continue

        lat = est.get("latitud")
        lon = est.get("longitud")
        if lat is None or lon is None:
            continue

        try:
            resp_data = requests.post(
                URL_PRECIPITACION, json={"id_estacion": id_est}, timeout=8
            )
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

    return {"estaciones": estaciones_validas}


def fetch_payloads() -> list[dict]:
    data = fetch_inamhi_precipitacion()
    if data and data.get("estaciones"):
        print(f"[+] INAMHI lluvia: {len(data['estaciones'])} estaciones en Guayas")
        return [data]
    print("[-] INAMHI lluvia: sin datos vigentes")
    return []


def run_producer():
    producer = build_producer()
    run_loop(producer, TOPIC_PRECIP_ESTACIONES, fetch_payloads, INTERVAL_SECONDS)


if __name__ == "__main__":
    run_producer()
