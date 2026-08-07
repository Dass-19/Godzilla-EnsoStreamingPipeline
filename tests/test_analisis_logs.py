"""
Tests de la agregación de logs que alimenta /api/logs/resumen. Funciones puras:
no importan la app ni tocan HDFS.
"""

from datetime import datetime

from analisis_logs import construir_resumen, resumir_producer

AHORA = datetime(2026, 8, 6, 20, 30, 0)


def _linea(mensaje, nivel="INFO", fecha="2026-08-06 20:00:00,000"):
    return {"fecha": fecha, "nivel": nivel, "logger": "enso.producer", "mensaje": mensaje}


def test_ciclo_ok_suma_throughput():
    r = resumir_producer(
        "noaa",
        [_linea("ciclo topic=noaa-data obtenidos=3 publicados=3")],
        AHORA,
    )
    assert r["ciclos_ok"] == 1
    assert r["ciclos_vacios"] == 0
    assert r["registros_obtenidos"] == 3
    assert r["registros_publicados"] == 3
    assert r["no_publicados"] == 0


def test_ciclo_vacio_no_cuenta_como_ok():
    r = resumir_producer(
        "inamhi_nivel_rio",
        [_linea("ciclo sin registros topic=inamhi-nivel-rio", nivel="WARNING")],
        AHORA,
    )
    assert r["ciclos_ok"] == 0
    assert r["ciclos_vacios"] == 1
    assert r["advertencias"] == 1


def test_brecha_entre_obtenidos_y_publicados():
    """Separa un fallo de Kafka de un fallo de la fuente."""
    r = resumir_producer(
        "sgr_eventos",
        [_linea("ciclo topic=sgr-eventos obtenidos=5 publicados=2")],
        AHORA,
    )
    assert r["no_publicados"] == 3


def test_degradacion_gana_aunque_los_ciclos_esten_ok():
    """El punto ciego: INOCAR degradado sigue cerrando ciclos con obtenidos=1.

    Sin esta regla el tablero mostraría verde mientras publica marea sintética.
    """
    r = resumir_producer(
        "inocar_mareas",
        [
            _linea("ciclo topic=mareas-inocar obtenidos=1 publicados=1"),
            _linea(
                "INOCAR: sin evento que rodee el instante actual (0 eventos "
                "parseados de 2026-T3); se usa el modelo armónico",
                nivel="WARNING",
            ),
        ],
        AHORA,
    )
    assert r["ciclos_ok"] == 1
    assert r["estado"] == "degradado"
    assert any("modelo armónico" in d for d in r["degradaciones"])


def test_error_gana_sobre_degradado():
    r = resumir_producer(
        "inamhi_precipitacion",
        [
            _linea("INAMHI lluvia: sin datos vigentes", nivel="ERROR"),
            _linea("ciclo sin registros topic=inamhi-precipitacion", nivel="WARNING"),
        ],
        AHORA,
    )
    assert r["estado"] == "error"
    assert r["errores"] == 1


def test_cadencia_se_toma_de_la_linea_de_intervalo():
    r = resumir_producer(
        "noaa",
        [_linea("iniciando loop de productor topic=noaa-data intervalo=3600s")],
        AHORA,
    )
    assert r["cadencia_s"] == 3600


def test_cadencia_se_infiere_de_la_mediana_sin_linea_de_intervalo():
    registros = [
        _linea("ciclo topic=x obtenidos=1 publicados=1", fecha="2026-08-06 20:00:00,000"),
        _linea("ciclo topic=x obtenidos=1 publicados=1", fecha="2026-08-06 20:15:00,000"),
        _linea("ciclo topic=x obtenidos=1 publicados=1", fecha="2026-08-06 20:30:00,000"),
    ]
    r = resumir_producer("x", registros, AHORA)
    assert r["cadencia_s"] == 900


def test_sin_cadencia_conocida_no_marca_atraso():
    """Un one-shot con una sola línea vieja no debe dar falso positivo."""
    r = resumir_producer(
        "seguraep",
        [_linea("Proceso finalizado: 6/6 capas guardadas.", fecha="2026-08-06 08:00:00,000")],
        AHORA,
    )
    assert r["cadencia_s"] is None
    assert r["estado"] == "ok"


def test_atraso_supera_el_doble_de_la_cadencia():
    registros = [
        _linea(
            "iniciando loop de productor topic=noaa-data intervalo=900s",
            fecha="2026-08-06 18:00:00,000",
        ),
    ]
    r = resumir_producer("noaa", registros, AHORA)
    assert r["estado"] == "atrasado"
    assert r["atraso_s"] == 9000


def test_producer_sin_registros_queda_sin_senal():
    r = resumir_producer("copernicus", [], AHORA)
    assert r["estado"] == "sin_senal"
    assert r["ultimo_evento"] is None
    assert r["atraso_s"] is None


def test_resumen_ordena_por_severidad_y_cuenta_totales():
    por_producer = {
        "sano": [_linea("ciclo topic=a obtenidos=2 publicados=2")],
        "roto": [_linea("NOAA respondió 500", nivel="ERROR")],
        "degradado": [
            _linea("ciclo topic=c obtenidos=1 publicados=1"),
            _linea("GEE: sin imágenes GPM para 2026-08-06, se degrada a 0 mm", nivel="WARNING"),
        ],
    }
    resumen = construir_resumen(por_producer, AHORA)

    assert [p["producer"] for p in resumen["producers"]] == ["roto", "degradado", "sano"]
    assert resumen["totales"] == {
        "producers": 3,
        "ok": 1,
        "atrasados": 0,
        "degradados": 1,
        "con_error": 1,
        "sin_senal": 0,
        "ciclos_ok": 2,
        "ciclos_vacios": 0,
        "registros_publicados": 3,
        "errores": 1,
        "advertencias": 1,
    }


def test_resumen_agrupa_actividad_por_hora_y_top_errores():
    por_producer = {
        "a": [
            _linea("hola", fecha="2026-08-06 20:10:00,000"),
            _linea("NOAA respondió 500", nivel="ERROR", fecha="2026-08-06 20:20:00,000"),
            _linea("chau", fecha="2026-08-06 21:05:00,000"),
        ],
        "b": [_linea("NOAA respondió 500", nivel="ERROR", fecha="2026-08-06 20:40:00,000")],
    }
    resumen = construir_resumen(por_producer, AHORA)

    assert resumen["actividad_por_hora"] == [
        {"hora": "2026-08-06 20:00", "INFO": 1, "WARNING": 0, "ERROR": 2},
        {"hora": "2026-08-06 21:00", "INFO": 1, "WARNING": 0, "ERROR": 0},
    ]
    # El mismo mensaje en dos producers no se fusiona: el origen importa.
    assert len(resumen["top_errores"]) == 2
    assert all(e["veces"] == 1 for e in resumen["top_errores"])
