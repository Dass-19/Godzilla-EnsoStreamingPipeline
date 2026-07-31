"""
Tests del índice compuesto de riesgo.

`risk_index` es Python puro y determinista, así que se puede ejercitar sin
Spark ni HDFS. Interesa sobre todo el término de interacción lluvia×marea (el
objetivo específico 5 del proyecto), que en producción nunca llegó a
activarse porque la lluvia entraba siempre en 0.
"""

import pytest
from risk_index import (
    EMBALSE_NIVEL_ALERTA_MSNM,
    EMBALSE_NIVEL_MIN_MSNM,
    FACTOR_INTERACCION_LLUVIA_MAREA,
    MAREA_MAX_M,
    PESO_MAREA,
    PESO_PRECIP,
    PRECIP_24H_SATURACION_MM,
    calcular_indice_riesgo,
    normalizar_embalse,
    normalizar_marea,
    normalizar_precip,
)

ZONA_LLANA = {
    "cota_media_msnm": 6.0,
    "pendiente_clase": "plana",
    "cercania_estero_m": 150.0,
    "historicamente_inundable": True,
}
ZONA_ALTA = {
    "cota_media_msnm": 40.0,
    "pendiente_clase": "pronunciada",
    "cercania_estero_m": 5000.0,
    "historicamente_inundable": False,
}


def indice(precip, marea, embalse, zona=ZONA_LLANA):
    return calcular_indice_riesgo(
        precip_24h_mm=precip,
        altura_marea_m=marea,
        nivel_embalse_msnm=embalse,
        **zona,
    )["indice_riesgo"]


# --- Normalizadores -------------------------------------------------------

@pytest.mark.parametrize("mm, esperado", [
    (0.0, 0.0),
    (PRECIP_24H_SATURACION_MM / 2, 0.5),
    (PRECIP_24H_SATURACION_MM, 1.0),
    (PRECIP_24H_SATURACION_MM * 3, 1.0),   # satura, no se dispara
    (-10.0, 0.0),                          # no se vuelve negativo
])
def test_normalizar_precip(mm, esperado):
    assert normalizar_precip(mm) == pytest.approx(esperado)


def test_normalizar_marea_cubre_el_rango_del_estuario():
    assert normalizar_marea(0.0) == 0.0
    assert normalizar_marea(MAREA_MAX_M) == pytest.approx(1.0)
    assert 0.0 < normalizar_marea(2.0) < 1.0


def test_normalizar_embalse_usa_el_rango_de_operacion():
    """
    Regresión: `normalizar_embalse` dividía la cota por el umbral de alerta.
    Como Daule-Peripa opera cerca de ese umbral, cualquier cota real daba
    ~1.0 y el componente quedaba clavado en su máximo.
    """
    assert normalizar_embalse(EMBALSE_NIVEL_MIN_MSNM) == 0.0
    assert normalizar_embalse(EMBALSE_NIVEL_ALERTA_MSNM) == pytest.approx(1.0)

    # Una cota intermedia real tiene que quedar estrictamente entre 0 y 1.
    intermedia = normalizar_embalse(77.5)
    assert 0.0 < intermedia < 1.0
    assert intermedia == pytest.approx(0.5)


# --- Monotonía por componente --------------------------------------------

def test_mas_lluvia_no_baja_el_riesgo():
    valores = [indice(mm, 1.0, 75.0) for mm in (0, 25, 50, 100, 150)]
    assert valores == sorted(valores)
    assert valores[-1] > valores[0]


def test_mas_marea_no_baja_el_riesgo():
    valores = [indice(50.0, m, 75.0) for m in (0.4, 1.2, 2.4, 3.6)]
    assert valores == sorted(valores)
    assert valores[-1] > valores[0]


def test_mas_cota_de_embalse_no_baja_el_riesgo():
    valores = [indice(50.0, 1.0, cota) for cota in (70.0, 75.0, 80.0, 85.0)]
    assert valores == sorted(valores)
    assert valores[-1] > valores[0]


def test_zona_llana_junto_al_estero_es_mas_riesgosa_que_una_zona_alta():
    assert indice(50.0, 2.0, 80.0, ZONA_LLANA) > indice(50.0, 2.0, 80.0, ZONA_ALTA)


# --- Rango de salida ------------------------------------------------------

@pytest.mark.parametrize("precip, marea, embalse", [
    (0.0, 0.0, 0.0),
    (500.0, 10.0, 200.0),        # todo por encima de los umbrales
    (-5.0, -1.0, -50.0),         # entradas absurdas
])
def test_el_indice_siempre_queda_en_0_1(precip, marea, embalse):
    for zona in (ZONA_LLANA, ZONA_ALTA):
        assert 0.0 <= indice(precip, marea, embalse, zona) <= 1.0


def test_niveles_de_riesgo_cubren_las_cuatro_categorias():
    niveles = {
        calcular_indice_riesgo(
            precip_24h_mm=p, altura_marea_m=m, nivel_embalse_msnm=e, **z,
        )["nivel_riesgo"]
        for p, m, e, z in [
            (0.0, 0.0, 70.0, ZONA_ALTA),      # nada de agua, zona en altura
            (0.0, 0.0, 70.0, ZONA_LLANA),     # solo el riesgo estructural
            (60.0, 2.0, 78.0, ZONA_LLANA),
            (150.0, 3.6, 85.0, ZONA_LLANA),
        ]
    }
    assert niveles == {"bajo", "medio", "alto", "critico"}


# --- Interacción lluvia + marea (objetivo específico 5) -------------------

def test_lluvia_y_marea_juntas_superan_la_suma_lineal():
    """
    Con marea alta el sistema pluvial pierde descarga por gravedad, así que
    el efecto conjunto tiene que ser mayor que la suma de los efectos por
    separado. Este caso no se ejercitaba nunca en producción: la lluvia
    entraba siempre en 0 y el término de interacción quedaba anulado.
    """
    base = indice(0.0, 0.4, 70.0)
    solo_lluvia = indice(150.0, 0.4, 70.0) - base
    solo_marea = indice(0.0, 3.6, 70.0) - base
    juntas = indice(150.0, 3.6, 70.0) - base

    assert juntas > solo_lluvia + solo_marea


def test_el_termino_de_interaccion_vale_lo_documentado():
    componentes = calcular_indice_riesgo(
        precip_24h_mm=PRECIP_24H_SATURACION_MM,
        altura_marea_m=MAREA_MAX_M,
        nivel_embalse_msnm=EMBALSE_NIVEL_MIN_MSNM,
        **ZONA_ALTA,
    )["componentes"]

    assert componentes["precip_norm"] == pytest.approx(1.0)
    assert componentes["marea_norm"] == pytest.approx(1.0)
    assert componentes["interaccion_lluvia_marea"] == pytest.approx(
        FACTOR_INTERACCION_LLUVIA_MAREA
    )


def test_la_lluvia_pesa_mas_que_la_marea():
    """El peso de la precipitación es el mayor del modelo; si alguien los
    recalibra, que sea una decisión explícita y no un descuido."""
    assert PESO_PRECIP > PESO_MAREA
