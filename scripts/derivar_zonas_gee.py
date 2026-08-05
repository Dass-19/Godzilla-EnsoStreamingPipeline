"""
Script autónomo para derivar factores estáticos de zonas usando Google Earth Engine.

Calcula cota media (Copernicus DEM GLO-30) y población estimada (WorldPop)
para un buffer de 1.5 km alrededor del centroide de cada zona en Guayaquil.
"""

import csv
import os
import pathlib

import ee

CREDS_PATH = os.environ.get(
    "GEE_CREDENTIALS_PATH",
    "backend/env/ensostreamingpipeline-7f414895f6f4.json",
)

CSV_PATH = pathlib.Path(__file__).resolve().parent.parent / "backend" / "spark" / "data" / "geo_ref" / "zonas_guayaquil.csv"


def init_gee():
    if os.path.exists(CREDS_PATH):
        credentials = ee.ServiceAccountCredentials("", key_file=CREDS_PATH)
        ee.Initialize(credentials)
    else:
        ee.Initialize()


def derivar_factores_zonas():
    init_gee()

    dem = ee.Image("COPERNICUS/DEM/GLO30").select("DEM")
    worldpop = ee.ImageCollection("WorldPop/GP/100m/pop").first().select("population")

    zonas_actualizadas = []

    with open(CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lat = float(row["lat_centroide"])
            lon = float(row["lon_centroide"])
            point = ee.Geometry.Point([lon, lat])
            buffer = point.buffer(1500)

            cota_val = dem.reduceRegion(ee.Reducer.mean(), buffer, 30).get("DEM").getInfo()
            pop_val = worldpop.reduceRegion(ee.Reducer.sum(), buffer, 100).get("population").getInfo()

            if cota_val is not None:
                row["cota_media_msnm"] = str(round(float(cota_val), 1))
            if pop_val is not None:
                row["poblacion"] = str(int(round(float(pop_val))))

            zonas_actualizadas.append(row)

    print(f"[+] Factores GEE derivados exitosamente para {len(zonas_actualizadas)} zonas.")


if __name__ == "__main__":
    derivar_factores_zonas()
