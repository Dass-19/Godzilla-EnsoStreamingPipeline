"""
Script de Ingesta para INAMHI.
Descarga datos reales desde los endpoints del Visor Hidro-Meteorológico
y del servicio de Pronósticos de INAMHI.
"""
 

from common.kafka_client import build_producer, run_loop

import requests
import datetime

# Endpoints REALES confirmados (no ArcGIS, no requieren login para GET público)
ESTACIONES_URL = (
    "https://inamhi.gob.ec/api_visor/station_information/estaciones/visores/"
    "?id_aplicacion=vs_1h_inh"
    "&id_provincia=09"
)
PRONOSTICO_URL_TPL = (
    "https://inamhi.gob.ec/api_pronos/forecast/daily_forecast/list_by_date_now/"
    "?date={fecha}"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; INAMHI-Ingestor/1.0)",
    "Accept": "application/json",
}


def get_json(url, timeout=20):
    """Hace un GET y devuelve el JSON parseado, o lanza excepción con detalle."""
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()  # lanza si no es 2xx
    return resp.json(), resp.status_code


def ingest_estaciones():
    print("[*] Descargando catálogo de estaciones (Visor Hidro-Meteorológico)...")
    try:
        data, status = get_json(ESTACIONES_URL)
        print(f"[+] {len(data)} estaciones obtenidas (HTTP {status}).")
        return {
            "endpoint": ESTACIONES_URL,
            "http_status": status,
            "total_estaciones": len(data),
            "estaciones": data,
        }
    except requests.exceptions.RequestException as e:
        print(f"[-] Error al obtener estaciones: {e}")
        return {"endpoint": ESTACIONES_URL, "error": str(e)}


def ingest_pronostico(fecha=None):
    if fecha is None:
        fecha = datetime.date.today().isoformat()
    url = PRONOSTICO_URL_TPL.format(fecha=fecha)
    print(f"[*] Descargando pronóstico diario para {fecha}...")
    try:
        data, status = get_json(url)
        print(f"[+] Pronóstico de {len(data)} localidades obtenido (HTTP {status}).")
        return {
            "endpoint": url,
            "http_status": status,
            "fecha": fecha,
            "total_localidades": len(data),
            "pronostico": data,
        }
    except requests.exceptions.RequestException as e:
        print(f"[-] Error al obtener pronóstico: {e}")
        return {"endpoint": url, "fecha": fecha, "error": str(e)}


def ingest_data():
    estaciones = ingest_estaciones()
    pronostico = ingest_pronostico()

    return {
        "metadata": {
            "source": "INAMHI (Instituto Nacional de Meteorología e Hidrología)",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
        "estaciones": estaciones,
        "pronostico_diario": pronostico,
    }


def run_producer():
    producer = build_producer()
    def _fetch():
        data = ingest_data()
        if data:
            return [data]
        return []
    run_loop(producer, "inamhi-data", _fetch, interval_seconds=3600)


if __name__ == "__main__":
    run_producer()
