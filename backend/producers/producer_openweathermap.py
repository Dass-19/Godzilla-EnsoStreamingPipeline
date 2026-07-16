# -*- coding: utf-8 -*-
"""
Script de Ingesta para OpenWeatherMap.
Extrae datos meteorológicos actuales (temperatura, viento, nubes).
"""


import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.kafka_client import build_producer, send_record, run_loop

import urllib.request
import json
import datetime
import traceback

API_KEY = os.environ.get("OPENWEATHERMAP_API_KEY", "")
CITY = "Guayaquil"
COUNTRY = "EC"
OUTPUT_FILE = "openweathermap_data.json"


def fetch_weather():
    # URL de Current Weather Data de OpenWeatherMap
    url = f"https://api.openweathermap.org/data/2.5/weather?q={CITY},{COUNTRY}&appid={API_KEY}&units=metric&lang=es"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib.request.urlopen(req, timeout=10)
        data = json.loads(response.read().decode('utf-8'))

        record = {
            "date": datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%d'),
            "temperature_c": data.get("main", {}).get("temp"),
            "humidity": data.get("main", {}).get("humidity"),
            "pressure_hpa": data.get("main", {}).get("pressure"),
            "wind_speed_ms": data.get("wind", {}).get("speed"),
            "weather_description": data["weather"][0]["description"] if data.get("weather") else "N/A",
            "clouds_percent": data.get("clouds", {}).get("all")
        }

        payload = {
            "metadata": {
                "source": "OpenWeatherMap API",
                "location": f"{CITY}, {COUNTRY}",
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat()
            },
            "data": [record]
        }
        return payload

    except Exception as e:
        print(f"[-] Error al descargar datos de OpenWeatherMap: {e}")
        traceback.print_exc()


def run_producer():
    producer = build_producer()

    def _fetch():
        data = fetch_weather()
        if data:
            return [data]
        return []
    run_loop(producer, "openweathermap-data", _fetch, interval_seconds=3600)


if __name__ == "__main__":
    run_producer()
