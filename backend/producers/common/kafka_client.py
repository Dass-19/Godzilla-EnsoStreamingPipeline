"""
Utilidades comunes para todos los productores Kafka del proyecto.

Cada productor (NOAA, GPM, INAMHI, CELEC, INOCAR, SNGR) reutiliza:
    - build_producer(): crea un KafkaProducer serializado en JSON.
    - send_record(): publica un registro agregando timestamp de ingesta.
    - run_loop(): bucle infinito que llama a una función fetch_fn() cada
        N segundos y publica cada registro que retorne.

El runner `producers/run_all.ps1` arranca estos productores en background
para evitar tener que abrir seis terminales a mano.

fetch_fn() debe retornar una lista de dicts (uno por medición/evento).
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Callable, Iterable, Optional

from kafka import KafkaProducer
from kafka.errors import KafkaError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

def build_producer(bootstrap_servers: str = None) -> KafkaProducer:
    if bootstrap_servers is None:
        bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    
    while True:
        try:
            return KafkaProducer(
                bootstrap_servers=bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k is not None else None,
                acks="all",
                retries=5,
                linger_ms=200,
            )
        except Exception as e:
            logger.warning(f"Esperando a Kafka en {bootstrap_servers}: {e}")
            time.sleep(5)


def send_record(
        producer: KafkaProducer,
        topic: str,
        record: dict,
        key: Optional[str] = None
        ) -> None:
    record = dict(record)
    record.setdefault("ingested_at", datetime.now(timezone.utc).isoformat())
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
        key_fn: Optional[Callable[[dict], str]] = None,
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
