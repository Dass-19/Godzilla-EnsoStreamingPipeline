"""
Tests de contrato entre productores y el job de Spark.

Cada fixture reproduce el payload que el productor publica realmente en su
tópico. Si alguien cambia el shape en un lado y no en el otro, estos tests
fallan; antes el desajuste solo se manifestaba como un índice de riesgo que
no se movía nunca.
"""

import pytest
from contracts import (
    CENTINELA_NASA_POWER,
    ORIGEN_DEFAULT,
    ORIGEN_REAL,
    Lectura,
    construir_embalse,
    construir_marea,
    construir_precipitacion_diaria,
    parse_embalse,
    parse_marea,
    parse_precipitacion,
)

# --- Fixtures con la forma real de cada payload ---------------------------

PAYLOAD_MAREA_INOCAR = {
    "fuente": "INOCAR_pdf",
    "puerto": "Guayaquil",
    "altura_marea_m": 2.734,
    "tendencia": "subiendo",
    "pleamar": True,
    "ingested_at": "2026-07-31T12:00:00+00:00",
}

PAYLOAD_EMBALSE_CELEC = {
    "fuente": "CELEC_wp_api",
    "embalse": "Daule-Peripa",
    "descripcion": "La cota del embalse se ubica en 82,15 m.s.n.m.",
    "url_fuente": "https://www.celec.gob.ec/hidronacion/ejemplo",
    "fecha_noticia": "2026-07-30T09:00:00",
    "nivel_msnm": 82.15,
    "nivel_maximo_msnm": 85.0,
    "ingested_at": "2026-07-31T12:00:00+00:00",
}

PAYLOAD_NASA_POWER = {
    "metadata": {
        "source": "NASA POWER API",
        "location": "Guayaquil Costero (Lat -2.1, Lon -79.9)",
    },
    "data": [
        {"date": "20260728", "precipitation_mm": 12.4, "temperature_2m_C": 25.1},
        {"date": "20260729", "precipitation_mm": 47.9, "temperature_2m_C": 24.6},
        # Los días más recientes suelen venir sin dato: NASA POWER tiene
        # varios días de latencia y rellena con -999.
        {"date": "20260730", "precipitation_mm": CENTINELA_NASA_POWER},
        {"date": "20260731", "precipitation_mm": CENTINELA_NASA_POWER},
    ],
}


# --- Marea ----------------------------------------------------------------

def test_parse_marea_lee_el_payload_de_inocar():
    assert parse_marea(PAYLOAD_MAREA_INOCAR) == pytest.approx(2.734)


def test_parse_marea_ignora_la_ruta_anidada_que_nunca_existio():
    """
    Regresión: el job leía `data.mareas.pleamar.altura_m`, una ruta que
    ningún productor emitió jamás. El `try/except` la convertía en el valor
    por defecto 1.8 y el componente de marea quedaba congelado.
    """
    payload_inventado = {"data": {"mareas": {"pleamar": {"altura_m": 3.1}}}}
    assert parse_marea(payload_inventado) is None


def test_round_trip_marea():
    payload = construir_marea(
        altura_m=1.2345, tendencia="bajando", pleamar=False, fuente="INOCAR_pdf",
    )
    assert parse_marea(payload) == pytest.approx(1.234, abs=1e-3)
    assert payload["pleamar"] is False


# --- Embalse --------------------------------------------------------------

def test_parse_embalse_lee_la_cota_del_payload_de_celec():
    assert parse_embalse(PAYLOAD_EMBALSE_CELEC) == pytest.approx(82.15)


def test_round_trip_embalse_sin_nivel_maximo():
    payload = construir_embalse(
        nivel_msnm=79.0,
        descripcion="boletín",
        url_fuente=None,
        fecha_noticia=None,
        nivel_maximo_msnm=None,
    )
    assert parse_embalse(payload) == pytest.approx(79.0)
    assert "nivel_maximo_msnm" not in payload


# --- Precipitación --------------------------------------------------------

def test_parse_precipitacion_toma_el_dia_mas_reciente_con_dato():
    assert parse_precipitacion(PAYLOAD_NASA_POWER) == pytest.approx(47.9)


def test_parse_precipitacion_descarta_el_centinela_y_los_negativos():
    payload = {"data": [
        {"date": "20260730", "precipitation_mm": CENTINELA_NASA_POWER},
        {"date": "20260729", "precipitation_mm": -3.0},
    ]}
    assert parse_precipitacion(payload) is None


def test_parse_precipitacion_acepta_cero_como_dato_valido():
    """Un día sin lluvia es un dato real, no un dato ausente."""
    payload = {"data": [{"date": "20260730", "precipitation_mm": 0.0}]}
    assert parse_precipitacion(payload) == 0.0


def test_parse_precipitacion_ignora_el_payload_de_inamhi():
    """
    Regresión: el job leía `pronostico_diario.pronostico[0].precipitacion_mm`.
    INAMHI publica pronóstico cualitativo (`rain`, `uv_radiation`,
    `min_temperature`), nunca un acumulado en mm, así que la lluvia entraba
    en 0.0 en todos los micro-batches.
    """
    payload_inamhi = {
        "pronostico_diario": {
            "pronostico": [
                {"locality_name": "Guayaquil", "rain": True, "uv_radiation": 9},
            ],
        },
    }
    assert parse_precipitacion(payload_inamhi) is None


def test_round_trip_precipitacion():
    payload = {"data": [construir_precipitacion_diaria(
        fecha="20260729", precipitacion_mm=33.3, temperature_2m_C=25.0,
    )]}
    assert parse_precipitacion(payload) == pytest.approx(33.3)


# --- Entradas defensivas --------------------------------------------------

@pytest.mark.parametrize("parser", [parse_marea, parse_embalse, parse_precipitacion])
@pytest.mark.parametrize("payload", [None, [], "texto", 42, {}, {"data": "no-lista"}])
def test_los_parsers_no_levantan_ante_basura(parser, payload):
    assert parser(payload) is None


@pytest.mark.parametrize("valor", [None, "", "n/d", float("nan"), True])
def test_valores_no_numericos_se_tratan_como_ausentes(valor):
    assert parse_marea({"altura_marea_m": valor}) is None


# --- Procedencia ----------------------------------------------------------

def test_lectura_marca_el_respaldo_como_default():
    lectura = Lectura.desde(None, respaldo=1.8, detalle_default="sin dato")
    assert lectura.valor == 1.8
    assert lectura.origen == ORIGEN_DEFAULT
    assert lectura.es_real is False


def test_lectura_marca_el_dato_de_la_fuente_como_real():
    lectura = Lectura.desde(2.5, respaldo=1.8)
    assert lectura.valor == 2.5
    assert lectura.origen == ORIGEN_REAL
    assert lectura.es_real is True


def test_lectura_distingue_un_cero_real_de_un_respaldo_de_cero():
    """
    El caso que motiva la columna de procedencia: 0 mm de lluvia y "no hay
    dato de lluvia" producen el mismo número, y sin la marca son
    indistinguibles en el parquet.
    """
    real = Lectura.desde(0.0, respaldo=0.0)
    respaldo = Lectura.desde(None, respaldo=0.0)

    assert real.valor == respaldo.valor
    assert real.origen != respaldo.origen
