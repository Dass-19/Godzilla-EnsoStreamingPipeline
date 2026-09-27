---
id: 20260927145501
type: knowledge
status: evergreen
title: "Base de Conocimiento: Backend, Streaming y Persistencia"
created: 2026-09-27
---

# Base de Conocimiento: Backend

## 1. Arquitectura General del Backend

El backend se compone de tres capas desacopladas:
1. **Productores Kafka (`backend/producers/`)**: Procesos Python autónomos supervisados por `run_producers.py`. Publican en 19 tópicos y respaldan logs en HDFS vía `HandlerHDFS`.
2. **Motor de Streaming PySpark (`backend/spark/`)**: Consume tópicos en streaming, persiste crudos en Parquet (`/enso_data/raw/{fuente}`), ejecuta interpolación IDW y calcula el índice de riesgo multidimensional escribiendo en `/enso_data/processed/indice_riesgo`.
3. **Servicio REST FastAPI (`backend/api/`)**: Expone endpoints de lectura sobre HDFS usando `hdfs_client.py`, simulaciones en memoria con `risk_index.py` y proxies seguros hacia OpenWeatherMap.

---

## 2. Contratos y Esquemas Canónicos (`backend/contracts.py`)

- **Regla Fundamental**: `contracts.py` es la única fuente de verdad para los shapes de los payloads.
- **Tipos Canónicos**:
  - `Lectura(valor: float, origen: str, detalle: str)`: Permite rastrear explícitamente si un valor fue obtenido de una fuente remota (`origen="real"`) o si corresponde a un respaldo por caída de servicio (`origen="default"`).
  - `LluviaEstacion`: Representa telemetría de una estación pluviométrica INAMHI (`id_estacion`, `codigo`, `lat`, `lon`, `precip_24h_mm`, `fecha_ultimo_dato`).
- **No Excepciones**: Los parsers (`parse_marea`, `parse_embalse`, `parse_precipitacion`, `parse_caudal`, etc.) nunca deben lanzar excepciones; devuelven `None` ante datos ausentes o malformados.

---

## 3. WebHDFS Client (`backend/api/hdfs_client.py`)

- **Librería pura**: Usa `hdfs.InsecureClient` contra el puerto 9870 de NameNode.
- **Lectura de Parquets**: Descarga bytes en memoria y los transforma a `pandas.DataFrame` mediante `io.BytesIO` y `pyarrow`.
- **Caché TTL**: Implementa `CacheTTL` en memoria para endpoints de alta frecuencia.
- **Resiliencia ante Particiones Vacías**: En `read_latest_partition_parquet`, si Spark creó una partición de fecha vacía, el cliente retrocede automáticamente a particiones anteriores válidas.

---

## 4. PySpark Structured Streaming (`backend/spark/`)

- **Job Principal**: `spark_streaming_job.py`.
- **Bootstrap de Estado**: `EstadoFuentes.bootstrap()` precarga en memoria la última telemetría real disponible en HDFS antes de procesar nuevos micro-batches.
- **Interpolación IDW (`interpolacion.py`)**: Interpola lluvia en los centroides de las 22 zonas urbanas a partir de estaciones INAMHI válidas mediante distancia Haversine ($p=2.0$, radio 25 km).
- **Cálculo de Riesgo (`risk_index.py`)**:
  $$\text{Base} = 0.28 P + 0.12 M + 0.15 Q + 0.10 S + 0.20 T + 0.15 H$$
  $$\text{Interacción} = 0.15 (P \cdot M) + 0.15 (Q \cdot M) + 0.10 (\text{ENSO}_{1+2} \cdot P)$$
  $$\text{Riesgo} = \min(1.0, \max(0.0, \text{Base} + \text{Interacción}))$$
  $$\text{Impacto} = \text{Riesgo} \times \text{Exposición}_{\text{norm}}$$
