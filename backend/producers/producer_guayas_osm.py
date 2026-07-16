
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.kafka_client import build_producer, send_record

# -*- coding: utf-8 -*-
"""
Script de Ingesta Geoespacial para OSM (Guayas).
Extrae cuerpos de agua principales (ríos, esteros) y calles principales
usando la API de Overpass para la provincia del Guayas.
"""

import requests
import json
import traceback
import os

OUTPUT_FILE = "guayas_osm.geojson"

# overpass-api.de está devolviendo 406 a clientes "tipo bot" (requests, curl, QGIS)
# desde 2024-2026 por un filtro anti-scraping. Usamos mirrors como alternativa.
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter"
]

HEADERS = {
    "User-Agent": "GuayasGeoIngest/1.0 (contacto@ejemplo.com)"
}

FALLBACK_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[-79.88, -2.18], [-79.89, -2.19], [-79.90, -2.20]]},
            "properties": {"name": "Río Guayas (Fallback)"}
        }
    ]
}


def fetch_osm_data():
    print("[*] Conectando a Overpass API para extraer datos del Guayas...")

    bbox = "-2.3,-80.1,-2.0,-79.8"

    overpass_query = f"""
    [out:json][timeout:25];
    (
      way["waterway"="river"]({bbox});
      way["natural"="water"]({bbox});
    );
    out body;
    >;
    out skel qt;
    """

    response = None
    last_error = None

    for url in OVERPASS_URLS:
        try:
            print(f"[*] Probando endpoint: {url}")
            response = requests.post(
                url,
                data={'data': overpass_query},
                headers=HEADERS,
                timeout=60,  # timeout del cliente > timeout de la query, margen de red
            )
            if response.status_code == 200:
                break  # este mirror funcionó
            else:
                print(f"[-] {url} devolvió HTTP {response.status_code}. Probando siguiente mirror...")
                last_error = f"HTTP {response.status_code}"
                response = None
        except requests.exceptions.RequestException as e:
            print(f"[-] Falló {url}: {e}. Probando siguiente mirror...")
            last_error = str(e)
            response = None

    if response is None:
        print(f"[-] Todos los mirrors fallaron ({last_error}). Generando fallback local.")
        return FALLBACK_GEOJSON

    try:
        data = response.json()

        features = []
        nodes = {node['id']: (node['lon'], node['lat']) for node in data['elements'] if node['type'] == 'node'}

        for element in data['elements']:
            if element['type'] == 'way':
                coords = [nodes[node_id] for node_id in element.get('nodes', []) if node_id in nodes]
                if len(coords) >= 2:
                    is_polygon = coords[0] == coords[-1]
                    features.append({
                        "type": "Feature",
                        "geometry": {
                            "type": "Polygon" if is_polygon else "LineString",
                            "coordinates": [coords] if is_polygon else coords
                        },
                        "properties": element.get('tags', {})
                    })

        if not features:
            print("[-] La consulta no devolvió elementos. Generando fallback local.")
            return FALLBACK_GEOJSON

        return {"type": "FeatureCollection", "features": features}

    except requests.exceptions.RequestException as e:
        # cubre Timeout, ConnectionError, HTTPError, etc.
        print(f"[-] Error de red/timeout contactando Overpass: {e}. Generando fallback local.")
        return FALLBACK_GEOJSON
    except Exception as e:
        print(f"[-] Error fatal extrayendo datos OSM: {e}")
        traceback.print_exc()
        return FALLBACK_GEOJSON


def run_producer():
    producer = build_producer()
    data = fetch_osm_data()
    if data:
        wrapped = {
            "metadata": {"source": "OSM API"},
            "data": data
        }
        send_record(producer, "guayas-osm", wrapped)
        producer.flush()
        print("[+] guayas_osm enviado a Kafka.")

if __name__ == "__main__":
    run_producer()
