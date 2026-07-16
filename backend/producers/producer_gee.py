"""
Script de Ingesta para Google Earth Engine (GEE).
Extrae datos reales de temperatura promedio (SST) y Anomalías Térmicas (ANOM)
para las regiones clave de El Niño:
- Niño 3.4 (Pacífico Central - El Niño global)
- Niño 1+2 (Costas de Ecuador y Perú - El Niño costero)
Requiere autenticación previa (earthengine authenticate).
"""


import os
from common.kafka_client import build_producer, run_loop
import json
import datetime
import traceback

try:
    # pyrefly: ignore [missing-import]
    import ee
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False


def test_connection():
    print("[*] Verificando entorno GEE...")
    if not EE_AVAILABLE:
        print("[-] earthengine-api no está instalado.")
        return False

    try:
        print("[*] Intentando inicializar Google Earth Engine...")
        credentials_path = os.environ.get("GEE_CREDENTIALS_PATH")
        if credentials_path and os.path.exists(credentials_path):
            with open(credentials_path, 'r') as f:
                creds_json = json.load(f)
            credentials = ee.ServiceAccountCredentials(creds_json['client_email'], credentials_path)
            ee.Initialize(credentials, project='ensostreamingpipeline')
        else:
            ee.Initialize(project='ensostreamingpipeline')
        print("[+] Google Earth Engine inicializado correctamente.")
        return True
    except Exception as e:
        print(f"[-] Error al inicializar GEE (¿Falta autenticación?): {e}")
        return False

def ingest_data():
    print("[*] Descargando y procesando datos satelitales de GEE (NOAA OISST)...")
    try:
        # Regiones Clave para predicción de El Niño
        nino4 = ee.Geometry.Rectangle([160, -5, 180, 5]).union(ee.Geometry.Rectangle([-180, -5, -150, 5]))
        nino3 = ee.Geometry.Rectangle([-150, -5, -90, 5])
        nino34 = ee.Geometry.Rectangle([-170, -5, -120, 5])
        nino12 = ee.Geometry.Rectangle([-90, -10, -80, 0])

        # Consultamos OISST para enero de 2026 (ejemplo temporal)
        oisst_collection = ee.ImageCollection("NOAA/CDR/OISST/V2_1")\
                            .filterDate('2026-01-01', '2026-01-15')

        # Consultamos GPM (Precipitación) para el mismo periodo
        gpm_collection = ee.ImageCollection("NASA/GPM_L3/IMERG_V07")\
                            .filterDate('2026-01-01', '2026-01-15')\
                            .select('precipitation')

        # Convertimos a listas
        img_list = oisst_collection.toList(15)
        size = img_list.length().getInfo()
        # Para simplificar, obtenemos la precipitación promedio de toda la colección
        # y la aplicamos al último registro, o calculamos un valor diario.
        # Aquí calcularemos la precipitación diaria promedio en mm/hr

        records = []
        for i in range(size):
            img = ee.Image(img_list.get(i))

            date_ms = img.get('system:time_start').getInfo()
            date_str = datetime.datetime.fromtimestamp(date_ms/1000.0, datetime.UTC).strftime('%Y-%m-%d')

            # Promediamos variables (sst y anom) en Niño 3.4
            stats_34 = img.select(['sst', 'anom']).reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=nino34,
                scale=25000,
                maxPixels=1e9
            ).getInfo()

            # Promediamos variables (sst y anom) en Niño 1+2 (Impacto Sudamérica)
            stats_12 = img.select(['sst', 'anom']).reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=nino12,
                scale=25000,
                maxPixels=1e9
            ).getInfo()
            
            # Promediamos en Niño 3 y Niño 4
            stats_3 = img.select(['sst', 'anom']).reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=nino3,
                scale=25000,
                maxPixels=1e9
            ).getInfo()
            stats_4 = img.select(['sst', 'anom']).reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=nino4,
                scale=25000,
                maxPixels=1e9
            ).getInfo()

            # Obtenemos precipitación de GPM para la misma fecha (aprox)
            # Filtramos GPM para este día específico
            gpm_daily = gpm_collection.filterDate(
                date_str,
                datetime.datetime.strptime(date_str, '%Y-%m-%d') + datetime.timedelta(days=1)
                )

            precip_stats = {"precipitation": 0}
            if gpm_daily.size().getInfo() > 0:
                # Sumamos la precipitación del día y sacamos el promedio espacial en la costa
                precip_img = gpm_daily.sum() # suma de las medias horas
                precip_val = precip_img.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=nino12, # Usamos Niño 1+2 (Costa EC/PE) para precipitación
                    scale=10000,
                    maxPixels=1e9
                ).getInfo()

                if precip_val and precip_val.get('precipitation') is not None:
                    # GPM está en mm/hr, al sumar 48 medias horas (24 hrs * 2)
                    # debemos dividir para que tenga sentido o simplemente usar el valor directo.
                    # Simplificación: tomar el valor crudo retornado (sum(mm/hr))
                    precip_stats["precipitation"] = precip_val['precipitation'] / 2.0 # aprox mm/dia

            # Extraemos valores, manejando el factor de escala de OISST (* 0.01)
            record = {"date": date_str}

            if stats_34.get('sst') is not None:
                record["nino34_mean_sst"] = stats_34['sst'] / 100.0
                record["nino34_mean_anomaly"] = stats_34['anom'] / 100.0

            if stats_12.get('sst') is not None:
                record["nino12_mean_sst"] = stats_12['sst'] / 100.0
                record["nino12_mean_anomaly"] = stats_12['anom'] / 100.0

            if stats_3.get('sst') is not None:
                record["nino3_mean_sst"] = stats_3['sst'] / 100.0
                record["nino3_mean_anomaly"] = stats_3['anom'] / 100.0

            if stats_4.get('sst') is not None:
                record["nino4_mean_sst"] = stats_4['sst'] / 100.0
                record["nino4_mean_anomaly"] = stats_4['anom'] / 100.0
            record["coast_precipitation_mm"] = precip_stats["precipitation"]

            records.append(record)

        return {
            "metadata": {
                "source": "Google Earth Engine - NOAA OISST & NASA GPM",
                "regions": ["Niño 3.4 (Pacífico Central)", "Niño 1+2 (Sudamérica)"],
                "variables": [
                    "sst (Sea Surface Temperature)",
                    "anom (Sea Surface Temperature Anomaly)",
                    "precipitation (NASA GPM IMERG)"
                ],
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat()
            },
            "data": records
        }
    except Exception as e:
        print(f"[-] Error procesando datos de GEE: {e}")
        traceback.print_exc()
        return None


def run_producer():
    test_connection()
    producer = build_producer()
    def _fetch():
        data = ingest_data()
        if data:
            return [data]
        return []
    run_loop(producer, "gee-data", _fetch, interval_seconds=3600)

if __name__ == "__main__":
    run_producer()
