"""
Script de Ingesta Geoespacial para OSM (Guayas).
Extrae cuerpos de agua principales (ríos, esteros) y calles principales
usando la API de Overpass para la provincia del Guayas.
"""

import requests
from common.kafka_client import build_producer, logger, send_record

# overpass-api.de está devolviendo 406 a clientes "tipo bot" (requests, curl, QGIS)
# desde 2024-2026 por un filtro anti-scraping. Usamos mirrors como alternativa.
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

HEADERS = {"User-Agent": "GuayasGeoIngest/1.0 (contacto@ejemplo.com)"}

# Si Overpass no responde, este productor no publica nada y se conserva la
# última capa válida en el dashboard.


def fetch_osm_data():
    logger.info("Conectando a Overpass API para extraer datos del Guayas...")

    bbox = "-2.3,-80.1,-2.0,-79.8"

    overpass_query = f"""
    [out:json][timeout:25];
    (
      way["waterway"="river"]({bbox});
      way["natural"="water"]({bbox});
      node["amenity"~"hospital|clinic|school|shelter|fire_station"]({bbox});
      way["amenity"~"hospital|clinic|school|shelter|fire_station"]({bbox});
    );
    out body;
    >;
    out skel qt;
    """

    response = None
    last_error = None

    for url in OVERPASS_URLS:
        try:
            logger.info("Probando endpoint: %s", url)
            response = requests.post(
                url,
                data={"data": overpass_query},
                headers=HEADERS,
                timeout=60,  # timeout del cliente > timeout de la query, margen de red
            )
            if response.status_code == 200:
                break  # este mirror funcionó
            else:
                logger.error(
                    "%s devolvió HTTP %s. Probando siguiente mirror...", url, response.status_code
                )
                last_error = f"HTTP {response.status_code}"
                response = None
        except requests.exceptions.RequestException as e:
            logger.exception("Falló %s. Probando siguiente mirror...", url)
            last_error = str(e)
            response = None

    if response is None:
        logger.error("Todos los mirrors fallaron (%s). No se publica nada.", last_error)
        return None

    try:
        data = response.json()

        features = []
        nodes = {
            node["id"]: (node["lon"], node["lat"])
            for node in data["elements"]
            if node["type"] == "node"
        }

        for element in data["elements"]:
            if element["type"] == "way":
                coords = [
                    nodes[node_id] for node_id in element.get("nodes", []) if node_id in nodes
                ]
                if len(coords) >= 2:
                    is_polygon = coords[0] == coords[-1]
                    features.append(
                        {
                            "type": "Feature",
                            "geometry": {
                                "type": "Polygon" if is_polygon else "LineString",
                                "coordinates": [coords] if is_polygon else coords,
                            },
                            "properties": element.get("tags", {}),
                        }
                    )

        if not features:
            logger.error("La consulta no devolvió elementos. No se publica nada.")
            return None

        return {"type": "FeatureCollection", "features": features}

    except requests.exceptions.RequestException:
        # cubre Timeout, ConnectionError, HTTPError, etc.
        logger.exception("Error de red/timeout contactando Overpass. No se publica nada.")
        return None
    except Exception:
        logger.exception("Error fatal extrayendo datos OSM")
        return None


def run_producer():
    producer = build_producer()
    data = fetch_osm_data()
    if data:
        wrapped = {"metadata": {"source": "OSM API"}, "data": data}
        publicado = send_record(producer, "guayas-osm", wrapped)
        producer.flush()
        # Con el conteo, no solo "enviado": una capa que pasó de miles de
        # features a un puñado (mirror degradado, bbox mal resuelto) daba
        # exactamente el mismo log que una descarga sana. Este productor no
        # pasa por `run_loop`, así que tampoco recibe su resumen por ciclo.
        n = len(data.get("features", []))
        if publicado:
            logger.info("guayas_osm enviado a Kafka (%s features).", n)
        else:
            logger.error("guayas_osm: Kafka no confirmó el envío (%s features).", n)
    else:
        logger.error("guayas_osm sin datos válidos; no se publicó nada.")


if __name__ == "__main__":
    run_producer()
