"""
Verifica que lo que los productores publican de verdad pase por los parsers
que usa Spark.

Los tests de `test_contracts.py` trabajan sobre fixtures; estos importan los
módulos de los productores y ejercitan sus funciones puras, para que el
contrato no se rompa si alguien edita el productor sin tocar `contracts.py`.

`conftest.py` registra un stub de `kafka` si el paquete no está instalado, así
que estos tests corren sin levantar el pipeline. Los que además necesitan
`pdfplumber` o `requests` sí se saltan cuando faltan.
"""

import pytest
from contracts import parse_embalse, parse_marea, parse_precipitacion


def test_el_fallback_armonico_de_inocar_cumple_el_contrato():
    pytest.importorskip("pdfplumber")
    import producer_inocar_mareas

    registros = producer_inocar_mareas._modelo_armonico_fallback()

    assert len(registros) == 1
    altura = parse_marea(registros[0])
    assert altura is not None
    # El modelo armónico oscila alrededor del nivel medio del estuario.
    assert 0.0 < altura < 4.0
    assert registros[0]["fuente"] == "modelo_armonico_fallback"


def test_el_intervalo_de_inocar_no_vuelve_a_ser_de_horas():
    """Regresión: `INTERVAL_SECONDS = 15 * 60 * 60` publicaba cada 15 horas
    una altura interpolada "para el instante actual"."""
    pytest.importorskip("pdfplumber")
    import producer_inocar_mareas

    assert producer_inocar_mareas.INTERVAL_SECONDS <= 30 * 60


def test_el_registro_de_celec_cumple_el_contrato():
    import producer_celec_embalse

    texto = (
        "Hidronación informa que la cota del embalse se ubica en 82,15 m.s.n.m. "
        "Su nivel máximo es 85 m.s.n.m."
    )
    extraido = producer_celec_embalse._extraer_nivel_embalse(texto)

    assert extraido is not None
    assert parse_embalse(extraido) == pytest.approx(82.15)
    assert extraido["nivel_maximo_msnm"] == pytest.approx(85.0)


def test_nasa_power_pide_una_ventana_movil_y_no_un_rango_fijo():
    """Regresión: el rango estaba clavado en 20260101..20260115, así que el
    productor reenviaba el mismo bloque en cada ciclo, para siempre."""
    import producer_nasa_power

    inicio, fin = producer_nasa_power._ventana_fechas()

    assert len(inicio) == 8 and len(fin) == 8
    assert inicio < fin
    # La ventana termina hoy, no en una fecha escrita a mano.
    import datetime
    assert fin == datetime.datetime.now(datetime.UTC).date().strftime("%Y%m%d")


def test_el_registro_de_nasa_power_cumple_el_contrato():
    import producer_nasa_power

    registro = producer_nasa_power.construir_precipitacion_diaria(
        fecha="20260729", precipitacion_mm=18.2, temperature_2m_C=25.0,
    )
    assert parse_precipitacion({"data": [registro]}) == pytest.approx(18.2)


def test_ningun_productor_fabrica_datos_con_random():
    """
    Regresión: `producer_ndbc_buoys` generaba la SST con `random.uniform` y
    la persistía en el lake como una lectura real de la boya.
    """
    import pathlib
    import re

    # Se busca el import, no la palabra: los comentarios que explican por qué
    # se quitó `random` no deben hacer fallar el test.
    importa_random = re.compile(r"^\s*(import random\b|from random import\b)", re.MULTILINE)

    directorio = pathlib.Path(__file__).resolve().parent.parent / "backend" / "producers"
    ofensores = [
        archivo.name
        for archivo in directorio.glob("producer_*.py")
        if importa_random.search(archivo.read_text(encoding="utf-8"))
    ]
    assert ofensores == []
