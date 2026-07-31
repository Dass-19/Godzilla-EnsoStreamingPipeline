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
    PESO_HISTORICO,
    PESO_MAREA,
    PESO_PRECIP,
    PESO_RIO,
    PESO_SUELO,
    PESO_TOPOGRAFIA,
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


def indice(precip, marea, embalse=70.0, caudal=500.0, suelo=0.0, enso=0.0, zona=ZONA_LLANA):
    return calcular_indice_riesgo(
        precip_24h_mm=precip,
        altura_marea_m=marea,
        nivel_embalse_msnm=embalse,
        caudal_rio_m3s=caudal,
        saturacion_antecedente_mm=suelo,
        anomalia_nino12_c=enso,
        **zona,
    )["indice_riesgo"]


def test_suma_de_pesos_es_exactamente_uno():
    suma = PESO_PRECIP + PESO_MAREA + PESO_RIO + PESO_SUELO + PESO_TOPOGRAFIA + PESO_HISTORICO
    assert suma == pytest.approx(1.00)


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
    assert normalizar_embalse(EMBALSE_NIVEL_MIN_MSNM) == 0.0
    assert normalizar_embalse(EMBALSE_NIVEL_ALERTA_MSNM) == pytest.approx(1.0)
    intermedia = normalizar_embalse(77.5)
    assert 0.0 < intermedia < 1.0
    assert intermedia == pytest.approx(0.5)


# --- Monotonía por componente --------------------------------------------

def test_mas_lluvia_no_baja_el_riesgo():
    valores = [indice(mm, 1.0) for mm in (0, 25, 50, 100, 150)]
    assert valores == sorted(valores)
    assert valores[-1] > valores[0]


def test_mas_marea_no_baja_el_riesgo():
    valores = [indice(50.0, m) for m in (0.4, 1.2, 2.4, 3.6)]
    assert valores == sorted(valores)
    assert valores[-1] > valores[0]


def test_mas_caudal_no_baja_el_riesgo():
    valores = [indice(50.0, 1.0, caudal=c) for c in (400.0, 800.0, 1200.0, 1800.0)]
    assert valores == sorted(valores)
    assert valores[-1] > valores[0]


def test_mas_saturacion_no_baja_el_riesgo():
    valores = [indice(50.0, 1.0, suelo=s) for s in (0.0, 30.0, 60.0, 120.0)]
    assert valores == sorted(valores)
    assert valores[-1] > valores[0]


def test_anomalia_nino12_negativa_no_reduce_el_riesgo():
    r_neutro = indice(50.0, 1.0, enso=0.0)
    r_frio = indice(50.0, 1.0, enso=-2.0)
    assert r_frio == pytest.approx(r_neutro)


def test_zona_llana_junto_al_estero_es_mas_riesgosa_que_una_zona_alta():
    assert indice(50.0, 2.0, zona=ZONA_LLANA) > indice(50.0, 2.0, zona=ZONA_ALTA)


# --- Rango de salida ------------------------------------------------------

@pytest.mark.parametrize("precip, marea, embalse", [
    (0.0, 0.0, 0.0),
    (500.0, 10.0, 200.0),        # todo por encima de los umbrales
    (-5.0, -1.0, -50.0),         # entradas absurdas
])
def test_el_indice_siempre_queda_en_0_1(precip, marea, embalse):
    for zona in (ZONA_LLANA, ZONA_ALTA):
        assert 0.0 <= indice(precip, marea, embalse, zona=zona) <= 1.0


def test_niveles_de_riesgo_cubren_las_cuatro_categorias():
    niveles = {
        calcular_indice_riesgo(
            precip_24h_mm=p, altura_marea_m=m, caudal_rio_m3s=c, **z,
        )["nivel_riesgo"]
        for p, m, c, z in [
            (0.0, 0.0, 400.0, ZONA_ALTA),
            (0.0, 0.0, 400.0, ZONA_LLANA),
            (60.0, 2.0, 1000.0, ZONA_LLANA),
            (150.0, 3.6, 1800.0, ZONA_LLANA),
        ]
    }
    assert niveles == {"bajo", "medio", "alto", "critico"}


# --- Interacción lluvia + marea -----------------------------------

def test_lluvia_y_marea_juntas_superan_la_suma_lineal():
    base = indice(0.0, 0.4)
    solo_lluvia = indice(150.0, 0.4) - base
    solo_marea = indice(0.0, 3.6) - base
    juntas = indice(150.0, 3.6) - base

    assert juntas > solo_lluvia + solo_marea


def test_la_lluvia_pesa_mas_que_la_marea():
    assert PESO_PRECIP > PESO_MAREA

