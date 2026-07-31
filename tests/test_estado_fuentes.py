"""
Tests unitarios para EstadoFuentes y actualización de estado.
"""

from contracts import (
    TOPIC_CAUDAL,
    TOPIC_MAREA,
    TOPIC_PRECIP_ESTACIONES,
    construir_caudal,
    construir_lluvia_estacion,
    construir_marea,
)
from spark_streaming_job import EstadoFuentes


def test_estado_fuentes_actualizar_y_lecturas():
    estado = EstadoFuentes()

    # Inicialmente todo por defecto
    lects_init = estado.lecturas(lat=-2.19, lon=-79.89)
    assert not lects_init["marea"].es_real
    assert not lects_init["caudal"].es_real

    # Actualizamos con payload real de marea
    payload_marea = construir_marea(altura_m=2.4, tendencia="subiendo", pleamar=False, fuente="inocar")
    estado.actualizar(TOPIC_MAREA, payload_marea)

    # Actualizamos con caudal real GEOGLOWS
    payload_caudal = construir_caudal(river_id=670078246, caudal_m3s=650.0, tramo="Guayas")
    estado.actualizar(TOPIC_CAUDAL, payload_caudal)

    # Actualizamos con estaciones INAMHI
    payload_precip = {
        "estaciones": [
            construir_lluvia_estacion("E1", "COD1", -2.19, -79.89, 45.0, "2026-07-31 12:00:00")
        ]
    }
    estado.actualizar(TOPIC_PRECIP_ESTACIONES, payload_precip)

    lects = estado.lecturas(lat=-2.19, lon=-79.89)
    assert lects["marea"].es_real
    assert lects["marea"].valor == 2.4
    assert lects["caudal"].es_real
    assert lects["caudal"].valor == 650.0
    assert lects["precip"].es_real
    assert lects["precip"].valor == 45.0
