---
id: 20260927152003
type: skill-spec
status: evergreen
name: "backend-producers"
runtime: python3 / kafka
entrypoint: "backend/producers/run_producers.py"
inputs:
  - name: producer_name
    type: string
    description: "Nombre del script de productor a crear o modificar"
    required: false
outputs:
  format: "kafka-records / hdfs-logs"
created: 2026-09-27
updated: 2026-09-27
---

# Skill: Backend Data Producers (Kafka Producers)

> **Propósito**: Guiar la creación, depuración y mantenimiento de los productores de datos en [`backend/producers/`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/backend/producers/), asegurando cumplimiento de contratos, degradación explícita y supervisión con backoff.

---

## 1. Patrón Canónico: `build_producer()` + `run_loop()`

Cada productor sigue la estructura canónica basada en [`common/kafka_client.py`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/backend/producers/common/kafka_client.py):

```python
import os
import requests
from common.kafka_client import build_producer, run_loop
from contracts import TOPIC_EJEMPLO, construir_ejemplo

INTERVAL_SECONDS = int(os.environ.get("INTERVALO_EJEMPLO", 15 * 60))

def fetch_payloads() -> list[dict]:
    try:
        resp = requests.get(URL, timeout=10)
        if not resp.ok:
            return []
        # Normalizar datos usando contratos canónicos
        return [construir_ejemplo(...)]
    except Exception:
        return []

def run_producer():
    producer = build_producer()
    run_loop(producer, TOPIC_EJEMPLO, fetch_payloads, INTERVAL_SECONDS)

if __name__ == "__main__":
    run_producer()
```

---

## 2. Reglas Obligatorias de Diseño

1. **Cero Invención de Datos (Degradación Explícita)**:
   - Prohibido el uso de `random` para inventar mediciones ante caídas remotas.
   - Si la fuente falla, devolver lista vacía `[]`.
2. **Contrato Único (`backend/contracts.py`)**:
   - Todo payload debe construirse mediante `construir_*()` y validarse con `parse_*()`.
3. **Registro en Supervisor (`backend/producers/run_producers.py`)**:
   - Registrar en `PRODUCTORES_CONTINUOS` (productores de streaming) o `PRODUCTORES_ONESHOT` (descargas completas periódicas).
4. **Buffer de Observabilidad (`HandlerHDFS`)**:
   - Todos los logs generados por `kafka_client.logger` se bufferizan y escriben en `/enso_data/raw/producer_logs/producer={p}/fecha=YYYY-MM-DD/{epoch_ms}.log` sin bloquear la ejecución.

---

## 3. Checklist de Verificación
- [ ] `pytest tests/test_producers_contract.py tests/test_contracts.py -q` pasa al 100%.
- [ ] El nuevo productor está registrado en `run_producers.py`.
- [ ] Sin `import random` en ningún productor.
