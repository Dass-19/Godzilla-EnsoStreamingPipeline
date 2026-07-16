"""
Script de Ingesta para Open-Meteo.
Descarga variables atmosféricas clave de la región Niño 3.4 (Pacífico Central).
Variables: Temperatura, Precipitación, Vientos Alisios (Velocidad y Dirección) y Presión Superficial.
"""


from common.kafka_client import build_producer, run_loop

import requests
import datetime

ENDPOINT = "https://archive-api.open-meteo.com/v1/archive"

def test_connection():
    print("[*] Probando conexión con Open-Meteo...")
    try:
        # Prueba ligera
        params = {"latitude": 0.0, "longitude": -143.0, "start_date": "2026-01-01", "end_date": "2026-01-02", "daily": "temperature_2m_mean", "timezone": "UTC"}
        response = requests.get(ENDPOINT, params=params, timeout=10)
        if response.status_code == 200:
            print("[+] Conexión exitosa con Open-Meteo (Status 200)")
            return True
        else:
            print(f"[-] Error de conexión con Open-Meteo: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"[-] Fallo de conexión con Open-Meteo: {e}")
        return False

def ingest_data():
    print("[*] Descargando variables atmosféricas predictivas de Open-Meteo...")
    params = {
        "latitude": 0.0,
        "longitude": -143.0, # Centro de la región Niño 3.4
        "start_date": "2026-01-01",
        "end_date": "2026-01-15",
        "daily": "temperature_2m_mean,precipitation_sum,wind_speed_10m_max,wind_direction_10m_dominant,shortwave_radiation_sum",
        "timezone": "UTC"
    }
    try:
        response = requests.get(ENDPOINT, params=params, timeout=15)
        if response.status_code != 200:
            return None
        
        raw_data = response.json()
        
        records = []
        if "daily" in raw_data:
            daily = raw_data["daily"]
            for i, date_str in enumerate(daily.get("time", [])):
                record = {
                    "date": date_str,
                    "mean_air_temp_c": daily.get("temperature_2m_mean", [])[i],
                    "precipitation_sum_mm": daily.get("precipitation_sum", [])[i],
                    "max_wind_speed_ms": daily.get("wind_speed_10m_max", [])[i],
                    "dominant_wind_direction_deg": daily.get("wind_direction_10m_dominant", [])[i],
                    "shortwave_radiation_mj_m2": daily.get("shortwave_radiation_sum", [])[i]
                }
                records.append(record)
                
        return {
            "metadata": {
                "source": "Open-Meteo Archive API",
                "region": "Niño 3.4 (Lat 0.0, Lon -143.0)",
                "variables": [
                    "temperature_2m_mean (Coupling océano-atmósfera)",
                    "precipitation_sum (Lluvias ecuatoriales)",
                    "wind_speed_10m_max (Fuerza de los Vientos Alisios)",
                    "wind_direction_10m_dominant (Dirección del viento)",
                    "shortwave_radiation_sum (Cobertura de nubes)"
                ],
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat()
            },
            "data": records
        }
    except Exception as e:
        print(f"[-] Error al descargar/procesar datos de Open-Meteo: {e}")
        return None


def run_producer():
    producer = build_producer()
    def _fetch():
        data = ingest_data()
        if data:
            return [data]
        return []
    run_loop(producer, "open-meteo-data", _fetch, interval_seconds=3600)

if __name__ == "__main__":
    run_producer()
