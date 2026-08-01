---
name: backend-producers
description: 'Use this skill when developing, refactoring, debugging, or adding Python Kafka data producers in backend/producers/. Includes guidelines for contract compliance (contracts.py), rate limiting, exponential backoff, mock fallback modes, environment variable configuration, and Kafka topic publication. Trigger phrases: "backend producers", "kafka producer", "ingest data", "producer script", "add data source", "producers".'
---

# Backend Data Producers Skill

## Overview
This skill governs the development and maintenance of the Python-based data ingestion producers residing in `backend/producers/`. These scripts fetch real-time and historical hydro-meteorological telemetries from external APIs (NOAA, INOCAR, INAMHI, CELEC, GeoGLOWS, OpenWeatherMap, Copernicus, SNGR) and publish validated JSON payloads into Kafka topics.

---

## 1. Producer Architectural Principles

1. **Contract First**: Every producer must map external API responses to strong data models defined in `backend/contracts.py`.
2. **Resilience & Fallback Mode**: If an external API is down, rate-limited, or requires an missing API key, the producer MUST switch gracefully to **Mock Mode** (`MOCK_MODE=true` or synthetic data generation) rather than crashing the process.
3. **Standard Envelope**: Data sent to Kafka topics follows a unified JSON envelope:
   ```json
   {
     "metadata": {
       "fuente": "inocar_mareas",
       "timestamp_ingestion": "2026-08-01T12:00:00Z",
       "version_esquema": "1.0"
     },
     "data": { ... }
   }
   ```
4. **Rate Limiting & Polling**: Each producer defines an explicit polling interval (`POLL_INTERVAL_SEC`) to respect target API rate limits and avoid throttling.

---

## 2. Standard Producer Implementation Pattern

When creating or modifying a producer (e.g., `producer_example.py`):

```python
import json
import logging
import os
import time
from kafka import KafkaProducer
from backend.contracts import MiContratoData

logger = logging.getLogger("producer.example")

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC_NAME = "enso.raw.ejemplo"
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SEC", "300"))
MOCK_MODE = os.getenv("MOCK_MODE", "false").lower() == "true"

def obtener_datos() -> dict:
    if MOCK_MODE:
        return {"valor": 25.4, "observacion": "mock"}
    # Real HTTP fetch with timeout and retries...
    ...

def main():
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8")
    )
    logger.info("Iniciando productor %s en tema %s", __name__, TOPIC_NAME)
    
    while True:
        try:
            raw_data = obtener_datos()
            # Validar con contrato
            contrato = MiContratoData(**raw_data)
            payload = {
                "metadata": {"fuente": "ejemplo", "timestamp": time.time()},
                "data": contrato.model_dump()
            }
            producer.send(TOPIC_NAME, payload)
            producer.flush()
        except Exception as err:
            logger.error("Error en ciclo de productor: %s", err, exc_info=True)
        
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
```

---

## 3. Master Orchestrator (`run_producers.py`)

The master orchestrator [`run_producers.py`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/backend/producers/run_producers.py) is responsible for managing all producer subprocesses in parallel.

- **Concurrencia**: Inicia cada `producer_*.py` en un proceso hijo separado.
- **Salida Limpia**: Reenvía los logs a stdout con prefijos identificadores por fuente.
- **Reinicio Automático**: Detecta caídas inesperadas de procesos individuales y los reinicia con backoff.

---

## 4. Key Files & Components

- **Contratos**: [`backend/contracts.py`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/backend/contracts.py)
- **Orquestador**: [`backend/producers/run_producers.py`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/backend/producers/run_producers.py)
- **Productores**: [`backend/producers/producer_*.py`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/backend/producers/)

---

## 5. Verification Checklist

When editing or adding producers, verify:
- [ ] Schema validation tests pass: `pytest tests/test_producers_contract.py`
- [ ] Synthetic data/mock fallback triggers when API keys are absent.
- [ ] Topic name follows standard naming convention (`enso.raw.<fuente>`).
- [ ] Handles HTTP timeouts (10s max) and connection errors without process failure.
