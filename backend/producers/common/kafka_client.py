"""
Utilidades comunes para todos los productores Kafka del proyecto.

Cada productor (NOAA, GPM, INAMHI, CELEC, INOCAR, SNGR) reutiliza:
    - build_producer(): crea un KafkaProducer serializado en JSON.
    - send_record(): publica un registro agregando timestamp de ingesta.
    - run_loop(): bucle infinito que llama a una función fetch_fn() cada
        N segundos y publica cada registro que retorne.

`run_producers.py` supervisa estos productores en un solo contenedor y
reinicia el que muera.

fetch_fn() debe retornar una lista de dicts (uno por medición/evento).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path

from kafka import KafkaProducer
from kafka.errors import KafkaError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("enso.producer")

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
MAX_REQUEST_SIZE_BYTES = 10 * 1024 * 1024

# Misma variable y mismo significado que usa la API para leer (`HDFS_BASE` en
# app.py): raíz de datos, sin esquema, porque WebHDFS recibe rutas y no URIs.
# Hardcodear la ruta de escritura hacía que apuntar el pipeline a otra raíz
# dejara los logs escritos en HDFS pero invisibles para `/api/logs` — los dos
# contenedores comparten el mismo `env_file`, así que la divergencia sería
# silenciosa.
HDFS_BASE_PATH = os.environ.get("HDFS_BASE_PATH", "/enso_data")
HDFS_LOGS_BASE_PATH = f"{HDFS_BASE_PATH}/raw/producer_logs"
INTERVALO_FLUSH_LOGS_S = int(os.environ.get("INTERVALO_FLUSH_LOGS_S", "60"))


def _nombre_producer(argv0: str | None = None) -> str:
    """Deriva el nombre del producer del script en ejecución (producer_noaa.py -> noaa)."""
    return Path(argv0 if argv0 is not None else sys.argv[0]).stem.removeprefix("producer_")


class HandlerHDFS(logging.Handler):
    """Bufferiza líneas de log en memoria y las vuelca a HDFS periódicamente.

    Cada flush escribe un archivo nuevo (nunca hace append) bajo
    ``producer_logs/producer=<nombre>/fecha=YYYY-MM-DD/<epoch_ms>.log`` para no
    depender de si el clúster tiene habilitado el append de WebHDFS. Un fallo
    al escribir a HDFS nunca debe tumbar el producer: se traga la excepción y
    solo avisa por stderr, igual que ya hace producer_seguraep.py con sus
    propios errores de descarga.
    """

    def __init__(self, nombre_producer: str | None = None):
        super().__init__()
        self._nombre = nombre_producer or _nombre_producer()
        self._buffer: list[str] = []
        self._ultimo_flush = time.monotonic()
        self._client = None

    def _obtener_cliente(self):
        if self._client is None:
            from hdfs import InsecureClient

            webhdfs_url = os.environ.get("WEBHDFS_URL", "http://localhost:9870")
            hdfs_user = os.environ.get("HDFS_USER", "root")
            self._client = InsecureClient(webhdfs_url, user=hdfs_user)
        return self._client

    def emit(self, record: logging.LogRecord) -> None:
        # Sin este try/except, un `logger.info("%s", ...)` con argumentos mal
        # formados haría que `format()` lance dentro de `emit()`, y logging no
        # lo atrapa: la excepción saldría por el `logger.info()` del productor
        # y lo tumbaría. Justo lo que este handler promete no hacer.
        try:
            self._buffer.append(self.format(record))
            # ponytail: buffer acotado a 2000 líneas (~ evita crecer sin límite si
            # HDFS está caído por mucho tiempo); si se necesita retener más,
            # habría que persistir a disco local en vez de solo memoria.
            if len(self._buffer) > 2000:
                del self._buffer[:-2000]
            if time.monotonic() - self._ultimo_flush >= INTERVALO_FLUSH_LOGS_S:
                self.flush()
        except Exception:
            self.handleError(record)

    def flush(self) -> None:
        if not self._buffer:
            self._ultimo_flush = time.monotonic()
            return
        contenido = "\n".join(self._buffer) + "\n"
        hoy = datetime.now(UTC).strftime("%Y-%m-%d")
        epoch_ms = int(time.time() * 1000)
        ruta = (
            f"{HDFS_LOGS_BASE_PATH}/producer={self._nombre}/fecha={hoy}/{epoch_ms}.log"
        )
        try:
            self._obtener_cliente().write(ruta, data=contenido.encode("utf-8"), overwrite=True)
            self._buffer.clear()
        except Exception as e:
            print(f"[HandlerHDFS] no se pudo escribir logs en {ruta}: {e}", file=sys.stderr)
        finally:
            self._ultimo_flush = time.monotonic()


_handler_hdfs: HandlerHDFS | None = None
if os.environ.get("WEBHDFS_URL"):
    _handler_hdfs = HandlerHDFS()
    logger.addHandler(_handler_hdfs)


def build_producer(bootstrap_servers: str = KAFKA_BOOTSTRAP) -> KafkaProducer:
    while True:
        try:
            return KafkaProducer(
                bootstrap_servers=bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                retries=5,
                linger_ms=200,
                compression_type="gzip",
                max_request_size=MAX_REQUEST_SIZE_BYTES,
            )
        except Exception as e:
            logger.warning(f"Esperando a Kafka en {bootstrap_servers}: {e}")
            time.sleep(5)


def send_record(
        producer: KafkaProducer,
        topic: str,
        record: dict,
        key: str | None = None
        ) -> bool:
    """Publica un registro. Devuelve si Kafka lo confirmó."""
    record = dict(record)
    record.setdefault("ingested_at", datetime.now(UTC).isoformat())
    future = producer.send(topic, key=key, value=record)
    try:
        metadata = future.get(timeout=10)
        # DEBUG y no INFO: con `HandlerHDFS` cada línea termina en HDFS, y hay
        # fuentes que publican decenas de registros por ciclo (estaciones
        # INAMHI, boyas NDBC, eventos SGR). El detalle de partition/offset sirve
        # para depurar Kafka, no para auditar la ingesta: para eso está el
        # resumen por ciclo de `run_loop`. Se recupera bajando el nivel a DEBUG.
        logger.debug(
            "topic=%s partition=%s offset=%s key=%s",
            metadata.topic, metadata.partition, metadata.offset, key,
        )
        return True
    except KafkaError:
        logger.exception("fallo al publicar en topic=%s key=%s", topic, key)
        return False


def run_loop(
        producer: KafkaProducer,
        topic: str,
        fetch_fn: Callable[[], Iterable[dict]],
        interval_seconds: int,
        key_fn: Callable[[dict], str] | None = None,
        ) -> None:
    logger.info(
        "iniciando loop de productor topic=%s intervalo=%ss",
        topic,
        interval_seconds,
    )
    while True:
        start = time.monotonic()
        obtenidos = 0
        publicados = 0
        try:
            for record in fetch_fn():
                obtenidos += 1
                key = key_fn(record) if key_fn else None
                if send_record(producer, topic, record, key=key):
                    publicados += 1
        except Exception:
            logger.exception(
                "error en ciclo de fetch/publish para topic=%s",
                topic,
            )

        # Resumen por ciclo: es el único rastro que TODO productor deja sí o sí,
        # incluso los que no loguean nada propio. Un ciclo vacío es la
        # degradación documentada de varias fuentes (devuelven lista vacía en
        # vez de inventar datos), así que va como WARNING para que se distinga
        # de un ciclo sano al filtrar por nivel en la auditoría.
        if obtenidos:
            logger.info(
                "ciclo topic=%s obtenidos=%d publicados=%d",
                topic, obtenidos, publicados,
            )
        else:
            logger.warning("ciclo sin registros topic=%s", topic)

        # El ciclo es la unidad natural de flush. Sin esto el buffer espera al
        # primer emit del ciclo siguiente, y hay productores que duermen 12h
        # (INTERVALO_SST_SEMANAL, INTERVALO_NIVEL_RIO): sus logs no aparecerían
        # en la auditoría hasta medio día después.
        if _handler_hdfs:
            _handler_hdfs.flush()

        elapsed = time.monotonic() - start
        sleep_for = max(0, interval_seconds - elapsed)
        time.sleep(sleep_for)
