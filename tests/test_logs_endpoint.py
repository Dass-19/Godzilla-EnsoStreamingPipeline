"""
Tests del parseo de líneas de log que consume /api/logs. No importa app.py
(requiere fastapi/pydantic, que CI no instala para tests) ni toca HDFS.
"""

from hdfs_client import parsear_linea_log


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
