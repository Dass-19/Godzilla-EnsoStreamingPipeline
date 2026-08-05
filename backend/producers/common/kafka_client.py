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
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime

from kafka import KafkaProducer
from kafka.errors import KafkaError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("enso.producer")

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
MAX_REQUEST_SIZE_BYTES = 10 * 1024 * 1024


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
        ) -> None:
    record = dict(record)
    record.setdefault("ingested_at", datetime.now(UTC).isoformat())
    future = producer.send(topic, key=key, value=record)
    try:
        metadata = future.get(timeout=10)
        logger.info(
            "topic=%s partition=%s offset=%s key=%s",
            metadata.topic, metadata.partition, metadata.offset, key,
        )
    except KafkaError:
        logger.exception("fallo al publicar en topic=%s key=%s", topic, key)


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
        try:
            for record in fetch_fn():
                key = key_fn(record) if key_fn else None
                send_record(producer, topic, record, key=key)
        except Exception:
            logger.exception(
                "error en ciclo de fetch/publish para topic=%s",
                topic,
            )

        elapsed = time.monotonic() - start
        sleep_for = max(0, interval_seconds - elapsed)
        time.sleep(sleep_for)
