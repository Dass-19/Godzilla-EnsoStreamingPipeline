"""
Cliente delgado sobre WebHDFS para que la API lea los parquet que escribe
Spark sin necesitar libhdfs/pyarrow con Hadoop nativo instalado — basta con
que el NameNode tenga WebHDFS habilitado (puerto 9870 por defecto).

Se usa la librería `hdfs` (paquete `hdfs`, cliente puro en Python de
WebHDFS), que descarga los bytes del parquet y los entrega a pandas.

Provee dos garantías principales:
1. Traduce errores de ruta inexistente a `FileNotFoundError`.
2. Acota lecturas mediante límites de particiones.
"""

from __future__ import annotations

import io
import logging
from functools import lru_cache

import pandas as pd
from hdfs import InsecureClient
from hdfs.util import HdfsError

logger = logging.getLogger(__name__)

# Tope por defecto de particiones de fecha a leer en una sola petición.
MAX_PARTICIONES_POR_DEFECTO = 7


@lru_cache(maxsize=1)
def get_client(webhdfs_url: str, user: str) -> InsecureClient:
    return InsecureClient(webhdfs_url, user=user)


def _es_ruta_inexistente(error: HdfsError) -> bool:
    mensaje = str(error)
    return (
        getattr(error, "exception", "") == "FileNotFoundException"
        or "FileNotFoundException" in mensaje
        or "does not exist" in mensaje
    )


def _listar(client: InsecureClient, ruta: str) -> list[str]:
    """`client.list` traduciendo 'no existe' a FileNotFoundError."""
    try:
        return client.list(ruta, status=False)
    except HdfsError as error:
        if _es_ruta_inexistente(error):
            raise FileNotFoundError(f"No existe la ruta {ruta}") from error
        raise


def _listar_particiones(
    client: InsecureClient,
    base_path: str,
    partition_col: str,
) -> list[str]:
    prefijo = f"{partition_col}="
    return sorted(e for e in _listar(client, base_path) if e.startswith(prefijo))


def _leer_particion(client: InsecureClient, ruta_particion: str) -> list[pd.DataFrame]:
    dfs = []
    for archivo in _listar(client, ruta_particion):
        if not archivo.endswith(".parquet"):
            continue
        with client.read(f"{ruta_particion}/{archivo}") as reader:
            contenido = reader.read()
        dfs.append(pd.read_parquet(io.BytesIO(contenido)))
    return dfs


def read_latest_partition_parquet(
    client: InsecureClient,
    base_path: str,
    partition_col: str = "fecha",
) -> pd.DataFrame:
    """
    Lee todos los archivos parquet de la partición de fecha más reciente
    bajo base_path (esquema Hive: base_path/fecha=YYYY-MM-DD/*.parquet).

    Si la partición más reciente quedó vacía (Spark crea el directorio antes
    de escribir), retrocede a la anterior en vez de fallar.
    """
    particiones = _listar_particiones(client, base_path, partition_col)
    if not particiones:
        raise FileNotFoundError(f"No hay particiones bajo {base_path}")

    for particion in reversed(particiones):
        dfs = _leer_particion(client, f"{base_path}/{particion}")
        if dfs:
            return pd.concat(dfs, ignore_index=True)

    raise FileNotFoundError(f"No hay archivos parquet bajo {base_path}")


def read_all_partitions_parquet(
    client: InsecureClient,
    base_path: str,
    partition_col: str = "fecha",
    desde: str | None = None,
    hasta: str | None = None,
    max_particiones: int | None = MAX_PARTICIONES_POR_DEFECTO,
) -> pd.DataFrame:
    """
    Lee y concatena varias particiones de fecha, filtrando por rango.

    `max_particiones` acota cuántas particiones se traen: se conservan las más
    recientes del rango. `None` desactiva el tope (usar solo con un rango
    explícito y acotado).
    """
    particiones = _listar_particiones(client, base_path, partition_col)

    if desde:
        particiones = [p for p in particiones if p.split("=", 1)[1] >= desde]
    if hasta:
        particiones = [p for p in particiones if p.split("=", 1)[1] <= hasta]

    if max_particiones is not None and len(particiones) > max_particiones:
        descartadas = len(particiones) - max_particiones
        logger.info(
            "%s: leyendo las %s particiones más recientes (%s descartadas)",
            base_path, max_particiones, descartadas,
        )
        particiones = particiones[-max_particiones:]

    dfs = []
    for particion in particiones:
        dfs.extend(_leer_particion(client, f"{base_path}/{particion}"))

    if not dfs:
        return pd.DataFrame()

    return pd.concat(dfs, ignore_index=True)
