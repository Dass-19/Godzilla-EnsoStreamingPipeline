# https://seguraep.gob.ec/index.php/geoportal/mapadeeventos
# scrapea los datos de la url
import os
import json
import urllib.request
import urllib.parse
from hdfs import InsecureClient
import socket


LAYERS = [
    {
      "title": "sgr_zonas_inundables",
      "url": "https://services1.arcgis.com/ESOnuLz5X3I3J4At/arcgis/rest/services/Zonas_Inundables/FeatureServer/28"
      },
    {
      "title": "sgr_zonas_seguras",
      "url": "https://services1.arcgis.com/ESOnuLz5X3I3J4At/arcgis/rest/services/Zonas_Seguras/FeatureServer/16"
      },
    {
      "title": "sgr_vias_inundables",
      "url": "https://services1.arcgis.com/ESOnuLz5X3I3J4At/arcgis/rest/services/Vías_Inundables/FeatureServer/5"
      },
    {
      "title": "sgr_zonas_vulnerables_marea_alta",
      "url": "https://services7.arcgis.com/NWWHhu45fOJtCgG3/arcgis/rest/services/Puntos_vulnerables_por_marea_alta/FeatureServer/0"
      },
    {
      "title": "sgr_sectores_celestes",
      "url": "https://services7.arcgis.com/NWWHhu45fOJtCgG3/arcgis/rest/services/AGA_FINAL/FeatureServer/0"
      }
]


def download_layer(layer_info, hdfs_client, hdfs_base_path, fmt='geojson'):
    title = layer_info['title']
    base_url = layer_info['url']

    filename = title

    query_url = f"{base_url}/query?where=1=1&outFields=*&outSR=4326&f={fmt}"

    try:
        all_features = []
        offset = 0
        base_data = None

        while True:
            paged_url = query_url + f"&resultOffset={offset}"
            safe_url = urllib.parse.quote(paged_url, safe=':/?=&')

            req = urllib.request.Request(safe_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                page_data = json.loads(response.read().decode('utf-8'))
                if base_data is None:
                    base_data = page_data

                features = page_data.get('features', [])
                if not features:
                    break
                all_features.extend(features)

                print(f"[*] Descargados {len(all_features)} registros para {title}...")

                if page_data.get('exceededTransferLimit') or len(features) >= 2000:
                    offset += len(features)
                else:
                    break

        data = base_data
        data['features'] = all_features

        # Post-procesamiento especial en GeoJSON
        if fmt == 'geojson':
            if title == "sgr_sectores_celestes":
                for feature in data.get('features', []):
                    if 'properties' not in feature:
                        feature['properties'] = {}
                    feature['properties']['color'] = '#38bdf8'
                    distrito = feature['properties'].get('DISTRITO')
                    if distrito:
                        feature['properties']['name'] = f"Distrito {distrito}"
            elif title == "sgr_zonas_inundables":
                for feature in data.get('features', []):
                    if 'properties' not in feature:
                        feature['properties'] = {}
                    feature['properties']['color'] = 'rgba(64, 224, 208, 0.5)'  # Turquesa un poco opaco
            elif title == "sgr_vias_inundables":
                for feature in data.get('features', []):
                    if 'properties' not in feature:
                        feature['properties'] = {}
                    feature['properties']['color'] = '#ef4444'  # Rojo

        # Guardar directamente en HDFS
        hdfs_path = f"{hdfs_base_path}/{filename}.{fmt}"
        content = json.dumps(data).encode('utf-8')
        hdfs_client.write(hdfs_path, data=content, overwrite=True)
        print(f"[+] Guardado en HDFS: {hdfs_path}")

    except Exception as e:
        print(f"[-] Error descargando {title} ({fmt}): {e}")


def run_script():
    webhdfs_url = os.environ.get("WEBHDFS_URL", "http://localhost:9870")
    hdfs_user = os.environ.get("HDFS_USER", "root")
    hdfs_base_path = os.environ.get("HDFS_BASE_PATH", "/enso_data/raw/seguraep")

    print(f"[*] Conectando a HDFS en {webhdfs_url}...")
    client = InsecureClient(webhdfs_url, user=hdfs_user)

    print("[*] Iniciando descarga de capas (SeguraEP) a HDFS directamente...")
    for layer in LAYERS:
        for fmt in ['geojson']:
            download_layer(layer, client, hdfs_base_path, fmt)

    print("[*] Proceso finalizado. Capas de SeguraEP guardadas en HDFS.")


if __name__ == "__main__":
    run_script()
