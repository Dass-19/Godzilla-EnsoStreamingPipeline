"""
Cliente delgado sobre WebHDFS para que la API lea los parquet que escribe
Spark sin necesitar libhdfs/pyarrow con Hadoop nativo instalado — basta con
que el NameNode tenga WebHDFS habilitado (puerto 9870 por defecto).

Se usa la librería `hdfs` (paquete `hdfs`, cliente puro en Python de
WebHDFS), que descarga los bytes del parquet y los entrega a pandas.
"""

import io
import json
import logging
from functools import lru_cache
from typing import Optional, List
import socket

import pandas as pd
from hdfs import InsecureClient



logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_client(webhdfs_url: str, user: str) -> InsecureClient:
    return InsecureClient(webhdfs_url, user=user)


def read_latest_partition_parquet(
    client: InsecureClient,
    base_path: str,
    partition_col: str = "fecha",
) -> pd.DataFrame:
    """
    Lee todos los archivos parquet de la partición de fecha más reciente
    bajo base_path (esquema Hive: base_path/fecha=YYYY-MM-DD/*.parquet).
    """
    entradas = client.list(base_path, status=False)
    particiones = sorted(
        [e for e in entradas if e.startswith(f"{partition_col}=")],
        reverse=True,
    )
    if not particiones:
        raise FileNotFoundError(f"No hay particiones bajo {base_path}")

    ultima_particion = particiones[0]
    ruta_particion = f"{base_path}/{ultima_particion}"
    archivos = [f for f in client.list(ruta_particion) if f.endswith(".parquet")]

    dfs = []
    for archivo in archivos:
        with client.read(f"{ruta_particion}/{archivo}") as reader:
            contenido = reader.read()
        dfs.append(pd.read_parquet(io.BytesIO(contenido)))

    if not dfs:
        raise FileNotFoundError(f"No hay archivos parquet en {ruta_particion}")

    return pd.concat(dfs, ignore_index=True)


def read_all_partitions_parquet(
    client: InsecureClient,
    base_path: str,
    partition_col: str = "fecha",
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
) -> pd.DataFrame:
    """Lee y concatena varias particiones de fecha, opcionalmente filtrando por rango."""
    entradas = client.list(base_path, status=False)
    particiones = [e for e in entradas if e.startswith(f"{partition_col}=")]

    if desde:
        particiones = [p for p in particiones if p.split("=", 1)[1] >= desde]
    if hasta:
        particiones = [p for p in particiones if p.split("=", 1)[1] <= hasta]

    dfs = []
    for particion in sorted(particiones):
        ruta_particion = f"{base_path}/{particion}"
        archivos = [f for f in client.list(ruta_particion) if f.endswith(".parquet")]
        for archivo in archivos:
            with client.read(f"{ruta_particion}/{archivo}") as reader:
                contenido = reader.read()
            dfs.append(pd.read_parquet(io.BytesIO(contenido)))

    if not dfs:
        return pd.DataFrame()

    return pd.concat(dfs, ignore_index=True)
