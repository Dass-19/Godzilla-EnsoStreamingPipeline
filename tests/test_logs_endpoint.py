"""
Tests de la lectura de logs que consume /api/logs. No importa app.py
(requiere fastapi/pydantic, que CI no instala para tests) ni toca HDFS: el
cliente WebHDFS se reemplaza por un doble en memoria.
"""

import contextlib

from hdfs_client import leer_texto_particiones, listar_valores_particion, parsear_linea_log


def test_parsea_linea_valida():
    linea = "2026-08-05 12:34:56,789 INFO enso.producer: topic=noaa-data partition=0"
    r = parsear_linea_log(linea)
    assert r == {
        "fecha": "2026-08-05 12:34:56,789",
        "nivel": "INFO",
        "logger": "enso.producer",
        "mensaje": "topic=noaa-data partition=0",
    }


def test_parsea_linea_con_dos_puntos_en_el_mensaje():
    linea = "2026-08-05 12:34:56,789 ERROR enso.producer: fallo al publicar en topic=noaa-data key=None"
    r = parsear_linea_log(linea)
    assert r["nivel"] == "ERROR"
    assert r["mensaje"] == "fallo al publicar en topic=noaa-data key=None"


def test_linea_corrupta_devuelve_none():
    assert parsear_linea_log("esto no tiene el formato esperado") is None
    assert parsear_linea_log("") is None


class _ClienteHdfsFake:
    """Doble del InsecureClient: `arbol` mapea ruta -> lista de entradas."""

    def __init__(self, arbol: dict[str, list[str]], archivos: dict[str, str] | None = None):
        self.arbol = arbol
        self.archivos = archivos or {}

    def list(self, ruta, status=False):
        return self.arbol[ruta]

    @contextlib.contextmanager
    def read(self, ruta):
        yield _Lector(self.archivos[ruta].encode("utf-8"))


class _Lector:
    def __init__(self, contenido: bytes):
        self._contenido = contenido

    def read(self):
        return self._contenido


def test_listar_valores_particion_quita_el_prefijo():
    cliente = _ClienteHdfsFake({"/base": ["producer=noaa", "producer=gee", "_SUCCESS"]})
    # Ordenado y sin la entrada que no es partición.
    assert listar_valores_particion(cliente, "/base", "producer") == ["gee", "noaa"]


def test_leer_texto_particiones_filtra_por_rango_y_extension():
    cliente = _ClienteHdfsFake(
        arbol={
            "/base": ["fecha=2026-08-01", "fecha=2026-08-02", "fecha=2026-08-03"],
            "/base/fecha=2026-08-02": ["1.log", "_SUCCESS"],
            "/base/fecha=2026-08-03": ["2.log"],
        },
        archivos={
            "/base/fecha=2026-08-02/1.log": "linea A\nlinea B\n",
            "/base/fecha=2026-08-03/2.log": "linea C\n",
        },
    )

    lineas = leer_texto_particiones(cliente, "/base", desde="2026-08-02")

    # La partición del 01 queda fuera del rango y `_SUCCESS` no es un .log.
    assert lineas == ["linea A", "linea B", "linea C"]


def test_leer_texto_particiones_conserva_las_particiones_mas_recientes():
    cliente = _ClienteHdfsFake(
        arbol={
            "/base": ["fecha=2026-08-01", "fecha=2026-08-02"],
            "/base/fecha=2026-08-02": ["1.log"],
        },
        archivos={"/base/fecha=2026-08-02/1.log": "la mas nueva\n"},
    )

    # Con tope 1 no debe leer la del 01: si lo intentara, el fake lanzaría
    # KeyError por no tener esa ruta en el árbol.
    assert leer_texto_particiones(cliente, "/base", max_particiones=1) == ["la mas nueva"]


def test_leer_texto_particiones_sin_particiones_en_rango_devuelve_vacio():
    cliente = _ClienteHdfsFake({"/base": ["fecha=2026-08-01"]})
    assert leer_texto_particiones(cliente, "/base", desde="2026-09-01") == []
