"""
Script de Ingesta para SGR Eventos de Lluvia.
Consulta la API de FeatureServer de Gestión de Riesgos para obtener eventos
de lluvia en cantones clave de la cuenca del Guayas (Guayaquil, Daule, etc.).
"""

from common.kafka_client import build_producer, run_loop

import json
import urllib.request
import urllib.parse

def fetch_sgr_events():
    print("[*] Descargando eventos de lluvia (SGR)...")
    
    # Filtramos eventos solo para Guayaquil, Daule, Samborondón y Durán
    where_clause = "canton IN ('GUAYAQUIL', 'DAULE', 'SAMBORONDON', 'DURAN')"
    url = f"https://sgrportal.gestionderiesgos.gob.ec/server/rest/services/Hosted/EVENTOS_X_LLUVIAS/FeatureServer/0/query?where={urllib.parse.quote(where_clause)}&outFields=*&f=geojson"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            return data
    except Exception as e:
        print(f"[-] Error descargando eventos SGR: {e}")


def run_producer():
    producer = build_producer()
    def _fetch():
        data = fetch_sgr_events()
        if data:
            wrapped = {
                "metadata": {"source": "SGR Eventos Lluvia"},
                "data": data
            }
            return [wrapped]
        return []
    run_loop(producer, "sgr-eventos", _fetch, interval_seconds=3600)

if __name__ == "__main__":
    run_producer()
