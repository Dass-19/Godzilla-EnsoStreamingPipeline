---
name: backend-producers
description: 'Use this skill when developing, refactoring, debugging, or adding Python Kafka data producers in backend/producers/. Covers the build_producer()/run_loop() pattern, contract compliance via backend/contracts.py, explicit degradation (never fabricated data), registration in run_producers.py, and environment-variable-driven polling intervals. Trigger phrases: "backend producers", "kafka producer", "ingest data", "producer script", "add data source", "producers".'
---

# Backend Data Producers Skill

## Overview
Governs `backend/producers/`: one `producer_*.py` per external source (NOAA, INOCAR, CELEC, INAMHI,
GEOGLOWS, IOC, Open-Meteo, OpenWeatherMap, SNGR, Copernicus, OSM/Overpass), each fetching
hydro-meteorological data and publishing it to a Kafka topic as plain JSON.

---

## 1. The real pattern: `build_producer()` + `run_loop()`

Every producer follows the same shape, built on
[common/kafka_client.py](../../../backend/producers/common/kafka_client.py). There is **no**
`KafkaProducer` constructed by hand and **no** envelope with `metadata`/`data` keys — `fetch_fn()`
returns a flat `list[dict]`, and `send_record()` (called internally by `run_loop`) just adds
`ingested_at` to each dict before publishing:

```python
import os
from common.kafka_client import build_producer, run_loop
from contracts import TOPIC_EJEMPLO, construir_ejemplo

INTERVAL_SECONDS = int(os.environ.get("INTERVALO_EJEMPLO", 15 * 60))


def fetch_payloads() -> list[dict]:
    try:
        resp = requests.get(URL, timeout=10)
        if not resp.ok:
            print(f"[-] Fuente respondió {resp.status_code}")
            return []
        # ... parseo ...
        return [construir_ejemplo(...)]
    except Exception as e:
        print(f"[-] Error consultando fuente: {e}")
        return []


def run_producer():
    producer = build_producer()
    run_loop(producer, TOPIC_EJEMPLO, fetch_payloads, INTERVAL_SECONDS)


if __name__ == "__main__":
    run_producer()
```

- `build_producer()` retries until Kafka answers (`bootstrap_servers` from `KAFKA_BOOTSTRAP_SERVERS`),
  and publishes gzip-compressed, JSON-serialized values.
- `run_loop(producer, topic, fetch_fn, interval_seconds)` calls `fetch_fn()` on a fixed cadence, forever;
  a raised exception inside `fetch_fn()` is logged and the loop continues (it never crashes the process).
- Logging convention: plain `print()` with `[*]`/`[+]`/`[-]` prefixes (starting/success/failure), not the
  `logging` module — that's only used inside `common/kafka_client.py` itself.

## 2. Contract first — `backend/contracts.py`

Every producer maps its external API response to a `construir_*` function from
[backend/contracts.py](../../../backend/contracts.py), never hand-building the dict inline. That module
is the **only** definition of each payload's shape — the Spark job's `parse_*` counterpart reads exactly
what `construir_*` writes. **If you change what a producer publishes, change `contracts.py` in the same
commit**, and add/update the round-trip test in `tests/test_contracts.py`.

## 3. Degradation, never fabrication

1. **No `random`**: `tests/test_producers_contract.py::test_ningun_productor_fabrica_datos_con_random`
   fails the build if any `producer_*.py` imports `random`. If an external source is down, publish
   nothing (empty list) — never synthesize a plausible-looking reading.
2. **Explicit fallback, when one exists and is documented**: e.g.
   [producer_inocar_mareas.py](../../../backend/producers/producer_inocar_mareas.py) scrapes a quarterly
   PDF and falls back to a documented harmonic tide model if the PDF is unavailable or its format
   changes — the fallback is a named function (`_modelo_armonico_fallback`), not silent interpolation.
3. **Freshness matters as much as fabrication**: if a source publishes a timestamp per record/station
   (e.g. INAMHI's `fecha_ultimo_dato`), a parser that claims to filter stale data must actually compare
   it against a clock — a parameter that's accepted but never used in the body is the same failure mode
   as fabricating data (it was found and fixed once in `parse_lluvia_estaciones`, don't reintroduce it).
4. There is **no `MOCK_MODE`** anywhere in this codebase. Don't add one — degrade to an empty list or a
   documented fallback instead.

## 4. Registration — `run_producers.py`

[run_producers.py](../../../backend/producers/run_producers.py) is the container's `CMD`. It has two
lists:
- `PRODUCTORES_CONTINUOS`: long-running scripts, each supervised in its own subprocess and restarted with
  exponential backoff (`BACKOFF_INICIAL_S` → `BACKOFF_MAXIMO_S`) if they die.
- `PRODUCTORES_ONESHOT`: scripts that fetch a full snapshot and exit, re-run every `INTERVALO_ONESHOT`
  seconds instead of looping internally (currently `producer_guayas_osm.py`, `producer_seguraep.py`).

**A new producer must be added to one of these two lists, or it never runs.** Exceptions already
documented in the file: `producer_copernicus.py` needs `COPERNICUS_USERNAME`/`PASSWORD` and the
`copernicusmarine` package (not in `requirements.txt`) and is run by hand.

Polling intervals are `INTERVALO_<NOMBRE>` environment variables with an in-code default (e.g.
`INTERVALO_MAREAS = int(os.environ.get("INTERVALO_MAREAS", 15 * 60))`), documented (commented out, with
their default) in [backend/env/.env.example](../../../backend/env/.env.example).

## 5. Key Files

- **Contratos**: [backend/contracts.py](../../../backend/contracts.py)
- **Utilidades Kafka**: [backend/producers/common/kafka_client.py](../../../backend/producers/common/kafka_client.py)
- **Orquestador**: [backend/producers/run_producers.py](../../../backend/producers/run_producers.py)
- **Productores**: `backend/producers/producer_*.py`

## 6. Verification Checklist

- [ ] `pytest tests/test_producers_contract.py tests/test_contracts.py -q`
- [ ] The new producer appears in `PRODUCTORES_CONTINUOS` or `PRODUCTORES_ONESHOT` in `run_producers.py`.
- [ ] Its `construir_*`/`parse_*` pair is in `contracts.py`, with a round-trip test in `test_contracts.py`.
- [ ] No `import random` (or `from random import`) anywhere in the file.
- [ ] On a failed/empty external response, it returns `[]` — it doesn't raise out of `run_loop`.
