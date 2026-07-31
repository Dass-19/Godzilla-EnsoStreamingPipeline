"""
Script de Ingesta para NASA POWER.
Descarga datos meteorológicos y de radiación para medir impactos locales de El Niño.
Variables: Temperatura, Precipitación, Vientos, Presión y Radiación Solar en Guayaquil.
"""


import datetime
import os

import requests
from common.kafka_client import build_producer, run_loop
from contracts import construir_precipitacion_diaria

ENDPOINT = "https://power.larc.nasa.gov/api/temporal/daily/point"

LATITUD_GUAYAQUIL = -2.1
LONGITUD_GUAYAQUIL = -79.9

INTERVAL_SECONDS = int(os.environ.get("INTERVALO_CLIMA", 60 * 60))
# NASA POWER publica la serie diaria con varios días de latencia, así que se
# pide una ventana hacia atrás y `parse_precipitacion` se queda con el día más
# reciente que traiga dato.
VENTANA_DIAS = int(os.environ.get("VENTANA_DIAS_CLIMA", 15))


def _ventana_fechas():
    hoy = datetime.datetime.now(datetime.UTC).date()
    desde = hoy - datetime.timedelta(days=VENTANA_DIAS)
    return desde.strftime("%Y%m%d"), hoy.strftime("%Y%m%d")


def test_connection():
    print("[*] Probando conexión con NASA POWER...")
    try:
        inicio, fin = _ventana_fechas()
        params = {"parameters": "T2M", "community": "AG", "longitude": LONGITUD_GUAYAQUIL, "latitude": LATITUD_GUAYAQUIL, "start": inicio, "end": fin, "format": "JSON"}
        response = requests.get(ENDPOINT, params=params, timeout=10)
        if response.status_code == 200:
            print("[+] Conexión exitosa con NASA POWER (Status 200)")
            return True
        else:
            print(f"[-] Error de conexión con NASA POWER: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"[-] Fallo de conexión con NASA POWER: {e}")
        return False

def ingest_data():
    print("[*] Descargando datos de impactos locales de El Niño desde NASA POWER...")
    # T2M: Temp a 2m, PRECTOTCORR: Lluvia corregida, WS10M: Viento a 10m
    # WD10M: Dirección del viento, ALLSKY_SFC_SW_DWN: Radiación Solar, PS: Presión superficial
    inicio, fin = _ventana_fechas()
    params = {
        "parameters": "T2M,PRECTOTCORR,WS10M,WD10M,ALLSKY_SFC_SW_DWN,PS",
        "community": "AG",
        "longitude": LONGITUD_GUAYAQUIL,  # Guayaquil (Impacto costero de El Niño)
        "latitude": LATITUD_GUAYAQUIL,
        "start": inicio,
        "end": fin,
        "format": "JSON"
    }
    try:
        response = requests.get(ENDPOINT, params=params, timeout=15)
        if response.status_code != 200:
            return None

        raw_data = response.json()
        records = []

        if "properties" in raw_data and "parameter" in raw_data["properties"]:
            params_data = raw_data["properties"]["parameter"]
            if "T2M" in params_data:
                for date_str, t2m_val in params_data["T2M"].items():
                    # El shape de este registro lo define `contracts`: es la
                    # fuente de la que Spark saca `precip_24h_mm` del índice.
                    records.append(construir_precipitacion_diaria(
                        fecha=date_str,
                        precipitacion_mm=params_data.get("PRECTOTCORR", {}).get(date_str, -999),
                        temperature_2m_C=t2m_val,
                        wind_speed_10m_ms=params_data.get("WS10M", {}).get(date_str, -999),
                        wind_direction_10m_deg=params_data.get("WD10M", {}).get(date_str, -999),
                        solar_radiation_MJ_m2=params_data.get("ALLSKY_SFC_SW_DWN", {}).get(date_str, -999),
                        surface_pressure_kPa=params_data.get("PS", {}).get(date_str, -999),
                    ))

        return {
            "metadata": {
                "source": "NASA POWER API",
                "location": f"Guayaquil Costero (Lat {LATITUD_GUAYAQUIL}, Lon {LONGITUD_GUAYAQUIL})",
                "ventana": {"desde": inicio, "hasta": fin},
                "variables": [
                    "T2M (Temperatura del aire)",
                    "PRECTOTCORR (Precipitación total)",
                    "WS10M (Velocidad del Viento)",
                    "WD10M (Dirección del Viento)",
                    "ALLSKY_SFC_SW_DWN (Radiación Solar / Nubosidad)",
                    "PS (Presión Atmosférica Superficial)"
                ],
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat()
            },
            "data": records
        }
    except Exception as e:
        print(f"[-] Error al descargar/procesar datos de NASA POWER: {e}")
        return None


def run_producer():
    producer = build_producer()
    def _fetch():
        data = ingest_data()
        if data:
            return [data]
        return []
    run_loop(producer, "nasa-power-data", _fetch, interval_seconds=INTERVAL_SECONDS)

if __name__ == "__main__":
    run_producer()
