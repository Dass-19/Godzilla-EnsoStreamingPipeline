"""
Carga de capas geográficas de Segura EP / SGR.

Excepción arquitectónica deliberada: este script NO publica a Kafka, escribe
GeoJSON directo a HDFS vía WebHDFS. Las capas (zonas inundables, zonas
seguras, vías inundables, puntos vulnerables por marea alta) son referencia
geográfica estática, no un flujo de eventos: se descargan enteras, se
sobrescriben enteras y el dashboard las consume tal cual por
`GET /data/sgr_*.geojson`. Pasarlas por Kafka + Spark solo agregaría una
reserialización a parquet de la que habría que reconstruir el GeoJSON.

Por eso tampoco existe ya el tópico `seguraep-layers`: se creaba en
`init-kafka` y Spark lo suscribía, pero nunca recibía un solo mensaje.

Es un job one-shot: `run_producers.py` lo ejecuta una vez por ciclo largo, no
lo mantiene vivo.
"""

import json
import os
import urllib.parse
import urllib.request

from common.kafka_client import logger
from hdfs import InsecureClient

LAYERS = [
    {
        "title": "sgr_zonas_inundables",
        "url": "https://services1.arcgis.com/ESOnuLz5X3I3J4At/arcgis/rest/services/Zonas_Inundables/FeatureServer/28",
    },
    {
        "title": "sgr_zonas_seguras",
        "url": "https://services1.arcgis.com/ESOnuLz5X3I3J4At/arcgis/rest/services/Zonas_Seguras/FeatureServer/16",
    },
    {
        "title": "sgr_vias_inundables",
        "url": "https://services1.arcgis.com/ESOnuLz5X3I3J4At/arcgis/rest/services/Vías_Inundables/FeatureServer/5",
    },
    {
        "title": "sgr_zonas_vulnerables_marea_alta",
        "url": "https://services7.arcgis.com/NWWHhu45fOJtCgG3/arcgis/rest/services/Puntos_vulnerables_por_marea_alta/FeatureServer/0",
    },
    {
        "title": "sgr_sectores_celestes",
        "url": "https://services7.arcgis.com/NWWHhu45fOJtCgG3/arcgis/rest/services/AGA_FINAL/FeatureServer/0",
    },
    {
        "title": "sgr_parroquias_guayaquil",
        "url_urbanas": "https://geoportalcat.guayaquil.gob.ec/arcgis/rest/services/Geoportal_Actualizado/GEOPORTAL_ACTUALIZADO/MapServer/9",
        "url_rurales": "https://services7.arcgis.com/iFGeGXTAJXnjq0YN/ArcGIS/rest/services/Parroquias_del_Ecuador/FeatureServer/0",
    },
]


def _make_safe_url(url):
    unquoted = urllib.parse.unquote(url)
    parsed = urllib.parse.urlparse(unquoted)
    encoded_path = urllib.parse.quote(parsed.path, safe="/:")
    encoded_query = urllib.parse.quote(parsed.query, safe=":=&?,*")
    return urllib.parse.urlunparse((
        parsed.scheme,
        parsed.netloc,
        encoded_path,
        parsed.params,
        encoded_query,
        parsed.fragment
    ))


def download_layer(layer_info, hdfs_client, hdfs_base_path, fmt="geojson"):
    title = layer_info["title"]
    filename = title

    if title == "sgr_parroquias_guayaquil":
        try:
            logger.info("Descargando parroquias urbanas y rurales...")
            # Urbanas
            u_safe_url = _make_safe_url(
                f"{layer_info['url_urbanas']}/query?where=1=1&outFields=*&outSR=4326&f=geojson"
            )
            u_req = urllib.request.Request(
                u_safe_url,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(u_req) as resp:
                u_data = json.loads(resp.read().decode("utf-8"))

            # Rurales
            r_safe_url = _make_safe_url(
                f"{layer_info['url_rurales']}/query?where=DPA_DESCAN='GUAYAQUIL'&outFields=*&outSR=4326&f=geojson"
            )
            r_req = urllib.request.Request(
                r_safe_url,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(r_req) as resp:
                r_data = json.loads(resp.read().decode("utf-8"))

            combined_features = []
            for f in u_data.get("features", []):
                p = f.get("properties", {})
                p["name"] = p.get("Nam", p.get("PARROQUIA", "Parroquia Urbana"))
                p["tipo"] = "Urbana"
                f["properties"] = p
                combined_features.append(f)

            for f in r_data.get("features", []):
                p = f.get("properties", {})
                p["name"] = p.get("DPA_DESPAR", p.get("PARROQUIA", "Parroquia Rural"))
                p["tipo"] = "Rural"
                f["properties"] = p
                combined_features.append(f)

            if not combined_features:
                logger.error(
                    "Parroquias: ni urbanas ni rurales devolvieron features; "
                    "se conserva la capa anterior"
                )
                return False

            data = {"type": "FeatureCollection", "features": combined_features}

            hdfs_path = f"{hdfs_base_path}/{filename}.{fmt}"
            content = json.dumps(data, separators=(",", ":")).encode("utf-8")
            hdfs_client.write(hdfs_path, data=content, overwrite=True)
            logger.info(
                "Guardado en HDFS: %s (%d parroquias)", hdfs_path, len(combined_features)
            )
            return True
        except Exception:
            logger.exception("Error descargando parroquias")
            return False

    base_url = layer_info["url"]

    # Detectar el campo ID único (OBJECTID, FID, etc.) para ordenar y permitir paginación por offset en ArcGIS
    oid_field = "OBJECTID"
    try:
        meta_url = _make_safe_url(f"{base_url}?f=json")
        req_meta = urllib.request.Request(meta_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req_meta) as resp_meta:
            meta_data = json.loads(resp_meta.read().decode("utf-8"))
            oid_field = meta_data.get("objectIdField", "OBJECTID")
    except Exception:
        pass

    query_url = f"{base_url}/query?where=1=1&outFields=*&outSR=4326&f={fmt}&orderByFields={oid_field}"

    try:
        all_features = []
        offset = 0
        base_data = None

        while True:
            paged_url = query_url + f"&resultOffset={offset}"
            safe_url = _make_safe_url(paged_url)

            req = urllib.request.Request(safe_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as response:
                page_data = json.loads(response.read().decode("utf-8"))
                if base_data is None:
                    base_data = page_data

                features = page_data.get("features", [])
                if not features:
                    break
                all_features.extend(features)

                logger.info("Descargados %d registros para %s...", len(all_features), title)

                if page_data.get("exceededTransferLimit") or len(features) >= 2000:
                    offset += len(features)
                else:
                    break

        data = base_data
        data["features"] = all_features

        # Sin esta guarda, ArcGIS devolviendo error con HTTP 200 sobrescribe la capa buena
        # con una FeatureCollection vacía (`overwrite=True` más abajo).
        if not all_features:
            logger.error("%s: la fuente no devolvió features; se conserva la capa anterior", title)
            return False

        # Post-procesamiento especial en GeoJSON
        if fmt == "geojson":
            if title == "sgr_sectores_celestes":
                for feature in data.get("features", []):
                    if "properties" not in feature:
                        feature["properties"] = {}
                    feature["properties"]["color"] = "#38bdf8"
                    distrito = feature["properties"].get("DISTRITO")
                    if distrito:
                        feature["properties"]["name"] = f"Distrito {distrito}"
            elif title == "sgr_zonas_inundables":
                for feature in data.get("features", []):
                    if "properties" not in feature:
                        feature["properties"] = {}
                    feature["properties"]["color"] = (
                        "rgba(64, 224, 208, 0.5)"  # Turquesa un poco opaco
                    )
            elif title == "sgr_vias_inundables":
                for feature in data.get("features", []):
                    if "properties" not in feature:
                        feature["properties"] = {}
                    feature["properties"]["color"] = "#ef4444"  # Rojo

        # Guardar directamente en HDFS
        hdfs_path = f"{hdfs_base_path}/{filename}.{fmt}"
        content = json.dumps(data, separators=(",", ":")).encode("utf-8")
        hdfs_client.write(hdfs_path, data=content, overwrite=True)
        logger.info("Guardado en HDFS: %s (%d features)", hdfs_path, len(all_features))
        return True

    except Exception:
        logger.exception("Error descargando %s (%s)", title, fmt)
        return False


def run_script():
    webhdfs_url = os.environ.get("WEBHDFS_URL", "http://localhost:9870")
    hdfs_user = os.environ.get("HDFS_USER", "root")
    # `HDFS_BASE_PATH` es la raíz de datos (`/enso_data`), igual que para la API
    # y para el HandlerHDFS. Antes este script la interpretaba como su propio
    # subdirectorio ya resuelto: la misma variable significaba dos cosas dentro
    # del mismo contenedor, y definirla rompía una de las dos.
    hdfs_base = os.environ.get("HDFS_BASE_PATH", "/enso_data")
    hdfs_base_path = f"{hdfs_base}/raw/seguraep"

    logger.info("Conectando a HDFS en %s...", webhdfs_url)
    client = InsecureClient(webhdfs_url, user=hdfs_user)

    logger.info("Iniciando descarga de capas (SeguraEP) a HDFS directamente...")
    guardadas = 0
    for layer in LAYERS:
        for fmt in ["geojson"]:
            if download_layer(layer, client, hdfs_base_path, fmt):
                guardadas += 1

    if guardadas == len(LAYERS):
        logger.info("Proceso finalizado: %s/%s capas guardadas.", guardadas, len(LAYERS))
    else:
        logger.error("Proceso finalizado: solo %s/%s capas guardadas.", guardadas, len(LAYERS))


if __name__ == "__main__":
    run_script()
