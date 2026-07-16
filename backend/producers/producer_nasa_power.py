"""
Script de Ingesta para NASA POWER.
Descarga datos meteorológicos y de radiación para medir impactos locales de El Niño.
Variables: Temperatura, Precipitación, Vientos, Presión y Radiación Solar en Guayaquil.
"""


from common.kafka_client import build_producer, run_loop

import requests
import datetime

ENDPOINT = "https://power.larc.nasa.gov/api/temporal/daily/point"

def test_connection():
    print("[*] Probando conexión con NASA POWER...")
    try:
        params = {"parameters": "T2M", "community": "AG", "longitude": -79.9, "latitude": -2.1, "start": "20260101", "end": "20260102", "format": "JSON"}
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
    params = {
        "parameters": "T2M,PRECTOTCORR,WS10M,WD10M,ALLSKY_SFC_SW_DWN,PS",
        "community": "AG",
        "longitude": -79.9,  # Guayaquil (Impacto costero de El Niño)
        "latitude": -2.1,
        "start": "20260101",
        "end": "20260115",
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
                    record = {
                        "date": date_str,
                        "temperature_2m_C": t2m_val,
                        "precipitation_mm": params_data.get("PRECTOTCORR", {}).get(date_str, -999),
                        "wind_speed_10m_ms": params_data.get("WS10M", {}).get(date_str, -999),
                        "wind_direction_10m_deg": params_data.get("WD10M", {}).get(date_str, -999),
                        "solar_radiation_MJ_m2": params_data.get("ALLSKY_SFC_SW_DWN", {}).get(date_str, -999),
                        "surface_pressure_kPa": params_data.get("PS", {}).get(date_str, -999)
                    }
                    records.append(record)
                    
        return {
            "metadata": {
                "source": "NASA POWER API",
                "location": "Guayaquil Costero (Lat -2.1, Lon -79.9)",
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
    run_loop(producer, "nasa-power-data", _fetch, interval_seconds=3600)

if __name__ == "__main__":
    run_producer()
