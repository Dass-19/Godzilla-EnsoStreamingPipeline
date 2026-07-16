# -*- coding: utf-8 -*-
"""
Script de Ingesta para Boyas Oceanográficas (NDBC TAO Array).
Extrae datos para las boyas 32320 (Niño 1+2 / Galápagos) y 32321 (Niño 3).
"""

import sys
import os
import requests
import json
import datetime
import random
from common.kafka_client import build_producer, send_record, run_loop

OUTPUT_FILE = "ndbc_buoys.json"

BUOYS = [
    {"id": "32320", "name": "Boya TAO 95W (Galápagos)", "lat": 0.0, "lon": -95.0},
    {"id": "32321", "name": "Boya TAO 110W (Pacífico Central)", "lat": 0.0, "lon": -110.0}
]

def fetch_buoy_data(buoy):
    """
    Simula la lectura de la NOAA NDBC o utiliza Open-Meteo Marine API para extraer 
    oleaje y corrientes, combinándolo con una simulación térmica de la boya.
    """
    url = f"https://marine-api.open-meteo.com/v1/marine?latitude={buoy['lat']}&longitude={buoy['lon']}&current=wave_height,ocean_current_velocity"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        current = data.get("current", {})
        
        # Simulamos la temperatura del agua (SST) basándonos en patrones ENSO normales
        base_temp = 24.5 if buoy['id'] == "32320" else 26.2
        water_temp = round(base_temp + random.uniform(-0.5, 0.5), 2)
        
        return {
            "buoy_id": buoy["id"],
            "name": buoy["name"],
            "latitude": buoy["lat"],
            "longitude": buoy["lon"],
            "water_temp_c": water_temp,
            "wave_height_m": current.get("wave_height", 0),
            "current_velocity_kmh": current.get("ocean_current_velocity", 0),
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat()
        }
    except Exception as e:
        print(f"[-] Error obteniendo datos para la boya {buoy['id']}: {e}")
        return None

def ingest_data():
    print("[*] Obteniendo datos en tiempo real de boyas oceánicas...")
    records = []
    for buoy in BUOYS:
        data = fetch_buoy_data(buoy)
        if data:
            records.append(data)
    
    if not records:
        return None

    # Guardar copia local de respaldo
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=4)
        
    return records

def run_producer():
    producer = build_producer()
    def _fetch():
        data = ingest_data()
        if data:
            # Empaquetar como un solo mensaje tipo FeatureCollection (para MapLibre)
            features = []
            for r in data:
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [r["longitude"], r["latitude"]]
                    },
                    "properties": {
                        "id": r["buoy_id"],
                        "name": r["name"],
                        "water_temp_c": r["water_temp_c"],
                        "wave_height_m": r["wave_height_m"],
                        "current_velocity_kmh": r["current_velocity_kmh"]
                    }
                })
            
            geojson = {
                "type": "FeatureCollection",
                "features": features
            }
            return [geojson]
        return []
    
    run_loop(producer, "ndbc-buoys", _fetch, interval_seconds=3600)

if __name__ == "__main__":
    run_producer()
