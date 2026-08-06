"""
Tests unitarios del HandlerHDFS de kafka_client.py: no tocan HDFS ni red.
"""

import logging

from common.kafka_client import HandlerHDFS, _nombre_producer


def test_nombre_producer_le_quita_el_prefijo():
    assert _nombre_producer("producer_noaa.py") == "noaa"
    assert _nombre_producer("/app/producer_inocar_mareas.py") == "inocar_mareas"


def test_nombre_producer_sin_prefijo_producer_queda_igual():
    assert _nombre_producer("run_producers.py") == "run_producers"


def _record(msg="hola", args=()):
    return logging.LogRecord(
        name="enso.producer",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=args,
        exc_info=None,
    )


class _ClienteFake:
    def __init__(self, falla=False):
        self.falla = falla
        self.escrituras = []

    def write(self, ruta, data, overwrite=True):
        if self.falla:
            raise RuntimeError("HDFS caído")
        self.escrituras.append((ruta, data))


def test_emit_acumula_en_el_buffer_sin_flushear_de_inmediato():
    handler = HandlerHDFS(nombre_producer="noaa")
    handler.emit(_record("mensaje %s", ("uno",)))
    handler.emit(_record("mensaje %s", ("dos",)))
    assert len(handler._buffer) == 2
    assert handler._buffer[0].endswith("INFO enso.producer: mensaje uno")


def test_la_linea_emitida_la_puede_parsear_la_api():
    """Contrato entre el escritor y el lector de logs.

    Regresión: el handler no seteaba formatter propio (`basicConfig` solo se lo
    aplica al StreamHandler que crea él), así que subía a HDFS el mensaje pelado
    sin fecha ni nivel. `/api/logs` no podía parsear ni una línea y devolvía 404
    con las particiones llenas. Un `in` sobre el mensaje no lo detectaba.
    """
    from hdfs_client import parsear_linea_log

    handler = HandlerHDFS(nombre_producer="noaa")
    handler.emit(_record("ciclo topic=%s obtenidos=%d", ("noaa-data", 1)))

    parseada = parsear_linea_log(handler._buffer[0])
    assert parseada is not None, f"la API no pudo parsear: {handler._buffer[0]!r}"
    assert parseada["nivel"] == "INFO"
    assert parseada["logger"] == "enso.producer"
    assert parseada["mensaje"] == "ciclo topic=noaa-data obtenidos=1"


def test_flush_escribe_una_ruta_particionada_por_producer_y_fecha_y_vacia_el_buffer():
    handler = HandlerHDFS(nombre_producer="noaa")
    cliente = _ClienteFake()
    handler._client = cliente
    handler._buffer = ["linea 1", "linea 2"]

    handler.flush()

    assert len(cliente.escrituras) == 1
    ruta, data = cliente.escrituras[0]
    assert ruta.startswith("/enso_data/raw/producer_logs/producer=noaa/fecha=")
    assert ruta.endswith(".log")
    assert data == b"linea 1\nlinea 2\n"
    assert handler._buffer == []


def test_flush_con_buffer_vacio_no_llama_al_cliente():
    handler = HandlerHDFS(nombre_producer="noaa")
    cliente = _ClienteFake()
    handler._client = cliente

    handler.flush()

    assert cliente.escrituras == []


def test_flush_no_propaga_si_hdfs_falla_y_conserva_el_buffer():
    handler = HandlerHDFS(nombre_producer="noaa")
    handler._client = _ClienteFake(falla=True)
    handler._buffer = ["linea 1"]

    handler.flush()  # no debe lanzar

    assert handler._buffer == ["linea 1"]


def test_emit_no_propaga_si_el_formato_es_invalido():
    """Un log mal formado no debe tumbar al productor que lo emitió."""
    handler = HandlerHDFS(nombre_producer="noaa")
    handler._client = _ClienteFake()
    # Faltan argumentos para el %s -> format() lanza dentro de emit().
    handler.emit(_record("faltan args %s %s", ("solo_uno",)))
    assert handler._buffer == []
