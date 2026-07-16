"""
API de solo lectura sobre los datos que Spark deja en HDFS zona `processed`
(y algunos crudos de `raw` para series de tiempo simples). Es el punto de
consumo único para el dashboard: el frontend nunca habla con HDFS
directamente.

Variables de entorno opcionales:
    WEBHDFS_URL    ej. "http://namenode:9870"
    HDFS_USER      usuario HDFS a usar en las peticiones (ej. "hdfs")
    HDFS_BASE_PATH ej. "/enso_data"

Si no se definen, la API usa valores por defecto pensados para desarrollo
local.

Ejecutar en desarrollo:
    cd api
    uvicorn app:app --reload --port 8000
"""

import os
from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from hdfs_client import (
    get_client,
    read_all_partitions_parquet,
    read_latest_partition_parquet,
)

WEBHDFS_URL = os.environ.get("WEBHDFS_URL", "http://localhost:9870")
HDFS_USER = os.environ.get("HDFS_USER", "root")
HDFS_BASE = os.environ.get("HDFS_BASE_PATH", "/enso_data")

app = FastAPI(
    title="API riesgo de inundación - Guayaquil / El Niño",
    description=(
        "Sirve al dashboard los datos procesados por el pipeline Kafka "
        "+ Spark + HDFS"
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.exists(frontend_path):
    app.mount("/dashboard", StaticFiles(directory=frontend_path, html=True), name="frontend")


def _client():
    return get_client(WEBHDFS_URL, HDFS_USER)


@app.get("/api/salud")
def salud():
    return {"estado": "ok"}


@app.get("/api/riesgo/zonas")
def riesgo_zonas_actual():
    """
    Último índice de riesgo calculado para todas las zonas de Guayaquil.
    Es el endpoint principal que consume el mapa del dashboard: una fila
    por zona con su score y nivel, lista para colorear polígonos.
    """
    try:
        df = read_latest_partition_parquet(
            _client(),
            f"{HDFS_BASE}/processed/indice_riesgo",
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Aún no hay datos de índice de riesgo procesados",
        )

    df_ultimo_por_zona = (
        df.sort_values("calculado_en")
        .groupby("zona_id", as_index=False)
        .last()
    )

    import csv
    import pathlib
    spark_dir = pathlib.Path(__file__).resolve().parent.parent / "spark"
    geo_ref_path = spark_dir / "data" / "geo_ref" / "zonas_guayaquil.csv"
    
    geo_info = {}
    with open(geo_ref_path, newline="", encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            geo_info[fila["zona_id"]] = {
                "nombre_sector": fila["nombre_sector"],
                "lat_centroide": float(fila["lat_centroide"]),
                "lon_centroide": float(fila["lon_centroide"])
            }
            
    zonas_dict = df_ultimo_por_zona.to_dict(orient="records")
    for z in zonas_dict:
        zid = z["zona_id"]
        if zid in geo_info:
            z.update(geo_info[zid])

    return {
        "actualizado_en": df_ultimo_por_zona["calculado_en"].max().isoformat(),
        "zonas": zonas_dict,
    }


@app.get("/api/riesgo/zonas/{zona_id}/historico")
def riesgo_zona_historico(
    zona_id: str,
    desde: Optional[date] = Query(
        None,
        description="fecha inicial YYYY-MM-DD",
    ),
    hasta: Optional[date] = Query(None, description="fecha final YYYY-MM-DD"),
):
    """Serie de tiempo del índice de riesgo de una zona."""
    df = read_all_partitions_parquet(
        _client(), f"{HDFS_BASE}/processed/indice_riesgo",
        desde=desde.isoformat() if desde else None,
        hasta=hasta.isoformat() if hasta else None,
    )
    if df.empty:
        raise HTTPException(
            status_code=404,
            detail="No hay datos para el rango solicitado",
        )

    df_zona = df[df["zona_id"] == zona_id].sort_values("calculado_en")
    if df_zona.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No hay datos para la zona {zona_id}",
        )

    columnas = [
        "calculado_en",
        "indice_riesgo",
        "nivel_riesgo",
        "precip_acumulada_24h_mm",
        "altura_marea_m",
        "caudal_embalse_m3s",
    ]

    return df_zona[columnas].to_dict(orient="records")


@app.get("/api/enso/estado")
def estado_enso():
    """Último estado ENSO para el panel nacional/regional del dashboard."""
    try:
        df = read_latest_partition_parquet(
            _client(),
            f"{HDFS_BASE}/raw/noaa",
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Aún no hay datos de SST/ENSO",
        )

    ultimo = df.sort_values("kafka_timestamp").iloc[-1]
    return ultimo.to_dict()


@app.get("/api/mareas/actual")
def marea_actual():
    try:
        df = read_latest_partition_parquet(
            _client(),
            f"{HDFS_BASE}/raw/inocar_mareas",
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Aún no hay datos de marea",
        )

    ultimo = df.sort_values("kafka_timestamp").iloc[-1]
    return ultimo.to_dict()


@app.get("/api/embalse/actual")
def embalse_actual():
    try:
        df = read_latest_partition_parquet(
            _client(),
            f"{HDFS_BASE}/raw/celec_embalse",
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Aún no hay datos del embalse",
        )

    ultimo = df.sort_values("kafka_timestamp").iloc[-1]
    return ultimo.to_dict()


@app.get("/api/alertas/recientes")
def alertas_recientes(limite: int = 20):
    """Últimas alertas SNGR crudas, para un listado o feed en el dashboard."""
    df = read_all_partitions_parquet(
        _client(),
        f"{HDFS_BASE}/raw/sngr_alertas",
    )
    if df.empty:
        return []

    return (
        df.sort_values("kafka_timestamp", ascending=False)
        .head(limite)
        .to_dict(orient="records")
    )


@app.get("/api/escenario/simular")
def simular_escenario(
    precip_24h_mm: float = Query(..., ge=0),
    altura_marea_m: float = Query(..., ge=0),
    caudal_embalse_m3s: float = Query(..., ge=0),
):
    """
    Recalcula el índice de riesgo para todas las zonas con valores
    hipotéticos de lluvia/marea/embalse, sin tocar HDFS. Pensado para el
    control interactivo del dashboard ("¿y si hay lluvia intensa + marea
    alta?") sin esperar al próximo micro-batch de Spark.
    """
    import csv
    import pathlib
    import sys

    # 1. Apuntar a la raíz del proyecto (ENSOSTREAMINGPIPELINE)
    # __file__ es api/app.py -> parent es api -> parent.parent es la raíz
    root_dir = pathlib.Path(__file__).resolve().parent.parent
    
    # 2. Agregar la raíz al sys.path para que detecte el paquete 'spark'
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))

    # 3. Importar usando la ruta absoluta desde la raíz
    from spark.risk_index import calcular_indice_riesgo

    # 4. Construir la ruta a la data
    spark_dir = root_dir / "spark"
    geo_ref_path = spark_dir / "data" / "geo_ref" / "zonas_guayaquil.csv"
    
    resultados = []
    with open(geo_ref_path, newline="", encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            r = calcular_indice_riesgo(
                precip_24h_mm=precip_24h_mm,
                altura_marea_m=altura_marea_m,
                caudal_descargado_m3s=caudal_embalse_m3s,
                cota_media_msnm=float(fila["cota_media_msnm"]),
                pendiente_clase=fila["pendiente_clase"],
                cercania_estero_m=float(fila["cercania_estero_m"]),
                historicamente_inundable=(
                    fila["historicamente_inundable"].lower() == "true"
                ),
            )
            resultados.append({
                "zona_id": fila["zona_id"],
                "nombre_sector": fila["nombre_sector"],
                "lat_centroide": float(fila["lat_centroide"]),
                "lon_centroide": float(fila["lon_centroide"]),
                **r,
            })

    return {"parametros": {
        "precip_24h_mm": precip_24h_mm,
        "altura_marea_m": altura_marea_m,
        "caudal_embalse_m3s": caudal_embalse_m3s,
    }, "zonas": resultados}


@app.get("/data/{filename}")
def get_data_file(filename: str):
    """Capa de compatibilidad para el frontend original de Godzilla."""
    import json

    mapping = {
        "gee_data.json": "gee",
        "noaa_data.json": "noaa",
        "open_meteo_data.json": "open_meteo",
        "nasa_power_data.json": "nasa_power",
        "enso_indexes.json": "enso_indexes",
        "inocar_data.json": "inocar_mareas",
        "inamhi_data.json": "inamhi",
        "openweathermap_data.json": "openweathermap",
        "sgr_eventos.json": "sgr_eventos",
        "guayas_osm.geojson": "guayas_osm",
        "ndbc_buoys.json": "ndbc_buoys"
    }

    if filename in mapping:
        source = mapping[filename]
        try:
            df = read_latest_partition_parquet(_client(), f"{HDFS_BASE}/raw/{source}")
            ultimo = df.sort_values("kafka_timestamp").iloc[-1]
            obj = json.loads(ultimo["json_str"])
            # Si el JSON viene envuelto con "metadata" y "data" y es un archivo GeoJSON (como guayas_osm.geojson),
            # MapLibre necesita directamente el GeoJSON, así que lo desenvolvemos.
            if filename.endswith('.geojson') and "data" in obj:
                return obj["data"]
            return obj
        except Exception:
            raise HTTPException(status_code=404, detail=f"Data for {filename} not found")

    elif filename.startswith("seguraep_") or filename.startswith("sgr_"):
        try:
            hdfs_path = f"{HDFS_BASE}/raw/seguraep/{filename}"
            with _client().read(hdfs_path) as reader:
                data = json.load(reader)
            return data
        except Exception as e:
            print(f"Error leyendo {filename} de HDFS: {e}")
            raise HTTPException(status_code=404, detail="Data for SeguraEP not found")
    else:
        raise HTTPException(status_code=404, detail="Unknown file")
