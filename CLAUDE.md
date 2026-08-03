# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es este proyecto

Pipeline Big Data end-to-end para riesgo de inundación en Guayaquil (fenómeno El Niño):
**Producers Python → Kafka → Spark Structured Streaming → HDFS (Parquet) → FastAPI → dashboard MapLibre**.
Todo corre bajo un único `docker-compose.yml` en la red `enso_net`.

El código, los comentarios y los nombres de variables/endpoints están en **español**. Mantener esa
convención al añadir código.

## Comandos

```bash
# Tests y lint (no necesitan Docker ni el pipeline levantado)
pip install -r requirements-dev.txt
pytest tests -q
pytest tests/test_contracts.py::test_parse_precipitacion_toma_el_dia_mas_reciente_con_dato  # un solo test
ruff check .          # ruff check --fix . para autoarreglar

# Levantar todo el ecosistema (Hadoop, Kafka, Spark, producers, API)
docker compose build
docker compose up -d

docker compose logs -f producers          # ver ingesta
docker compose logs -f spark-submitter    # ver el job de streaming
docker compose down -v                    # reset total, incluidos volúmenes HDFS

# Un solo producer (dentro del contenedor; requiere que Kafka esté arriba)
docker compose exec producers python -u producer_noaa.py

# API en local con recarga
SPARK_APP_DIR=backend/spark uvicorn api.app:app --reload --port 8000

# Reenviar el job de Spark tras editar backend/spark/*.py
docker compose restart spark-submitter
```

Interfaces: dashboard `http://localhost:8000/dashboard/` (la raíz `/` **no** sirve el frontend),
HDFS UI `:9870`, Spark master UI `:8080`, Kafka externo `localhost:9092`.

## Requisitos previos no obvios

- `docker/hadoop/` está registrado en git como **gitlink (submódulo sin `.gitmodules`) y está vacío en
  el checkout**. `docker compose build` falla en `namenode`/`datanode` hasta que ese directorio
  contenga su `Dockerfile` + `config`.
- `backend/env/.env` (copiar de `.env.example`) y el JSON de service account de Google Earth Engine en
  `backend/env/ensostreamingpipeline-7f414895f6f4.json` — el `docker-compose.yml` monta ese nombre de
  archivo **literal**. Sin `.env`, `docker compose config` ya falla: lo consumen `producers` y `api`.

## Arquitectura

### El contrato de datos: `backend/contracts.py`
**Empezar por acá.** Es la única definición del shape de los payloads que alimentan el índice de riesgo:
marea INOCAR, cota CELEC, precipitación NASA POWER, estaciones de lluvia INAMHI (para IDW por zona),
pronóstico Open-Meteo, marea observada del mareógrafo IOC, caudal del río Guayas (GEOGLOWS) y SST semanal
de Niño 1+2 (NOAA CPC). Lo importan los dos lados: los productores para construir el payload
(`construir_*`) y el job de Spark para leerlo (`parse_*`).

Existe porque el acoplamiento era por strings anidados escritos a mano en cada lado, y los tres
accesos del job apuntaban a rutas que ningún productor emitía. Como cada acceso estaba envuelto en
`try/except → valor por defecto`, el índice quedó constante por zona sin un solo error en los logs.
**Al tocar cualquiera de esos tres payloads, cambiar `contracts.py` y no el productor ni el job.**
Los tests de contrato ([tests/test_contracts.py](tests/test_contracts.py)) cubren los tres bugs
históricos como regresiones.

El módulo llega a cada contenedor por caminos distintos: los productores lo copian en la imagen (por
eso su build context es `backend/`, no `backend/producers/`), y el job de Spark lo recibe por
`--py-files` con un bind-mount declarado en el compose.

### Ingesta (`backend/producers/`)
Un archivo `producer_*.py` por fuente, todos con la misma forma: una función que devuelve **lista de
dicts**, y `run_loop(producer, topic, fetch_fn, interval_seconds)` de
[common/kafka_client.py](backend/producers/common/kafka_client.py) que la reejecuta indefinidamente.
Los intervalos salen de variables de entorno (`INTERVALO_MAREAS`, `INTERVALO_CLIMA`, …) con defaults
en el código. `build_producer()` reintenta hasta que Kafka responda y publica con gzip.

[run_producers.py](backend/producers/run_producers.py) es el `CMD` del contenedor: supervisa los
productores continuos y los reinicia con backoff, y ejecuta los one-shot
(`guayas_osm`, `seguraep`) cada `INTERVALO_ONESHOT`. **Añadir un producer requiere registrarlo ahí.**

Excepciones al patrón:
- [producer_seguraep.py](backend/producers/producer_seguraep.py) **no usa Kafka**: escribe GeoJSON
  directo a HDFS. Son capas geográficas estáticas, no un flujo de eventos — el docstring explica la
  decisión. Por eso el tópico `seguraep-layers` ya no existe.
- [producer_copernicus.py](backend/producers/producer_copernicus.py) no está en `run_producers.py`:
  necesita `COPERNICUS_USERNAME`/`PASSWORD` y el paquete `copernicusmarine`, que no está en
  `requirements.txt`. Se corre a mano.

Varios productores raspan fuentes públicas frágiles (PDF trimestral de INOCAR, WordPress REST API de
CELEC y SNGR) y **degradan explícitamente**: o caen a un modelo documentado, o devuelven lista vacía.
Ninguno fabrica datos — hay un test que falla si algún `producer_*.py` vuelve a importar `random`.

### Streaming (`backend/spark/`)
[spark_streaming_job.py](backend/spark/spark_streaming_job.py) mantiene el mapa `topic → nombre_fuente`
y vuelca cada mensaje **sin parsear** (`json_str` + `kafka_timestamp`) a
`hdfs://…/enso_data/raw/<fuente>/fecha=YYYY-MM-DD/`. **Añadir una fuente = crear el topic en
`init-kafka` + una entrada en `TOPICS_A_FUENTES`.**

El cálculo del riesgo es una query aparte suscrita a los ocho tópicos que alimentan el índice (ver
`TOPICS_A_FUENTES` y el filtro `topics_riesgo` en `spark_streaming_job.py`).
`EstadoFuentes` guarda en el driver el último valor de cada uno a partir de los mensajes del batch
(con un `bootstrap()` desde HDFS al arrancar), resuelve la precipitación por zona con `interpolar_idw`
(`interpolacion.py`) sobre las estaciones INAMHI vigentes, y cada micro-batch escribe una fila por zona a
`processed/indice_riesgo`. Cada fila lleva `origen_precip` / `origen_marea` / `origen_embalse` /
`origen_rio` / `origen_suelo` / `origen_marea_obs` / `origen_enso` (`real` | `default`) y
`datos_completos`: **una fila calculada con respaldos no debe ser indistinguible de una real.** También
lleva `epoch_id`, porque `append` dentro de `foreachBatch` no es idempotente y la API deduplica por
`(zona_id, epoch_id)` al leer.

[risk_index.py](backend/spark/risk_index.py) es **Python puro sin dependencias de Spark** — por eso la
API lo importa para el endpoint de simulación. El término clave es
`FACTOR_INTERACCION_LLUVIA_MAREA`: modela que la marea alta anula la descarga pluvial por gravedad (hay
un segundo término análogo para caudal+marea, y un tercero que usa la anomalía de Niño 1+2 para
amplificar la lluvia). **El embalse Daule-Peripa (CELEC) ya no pondera el índice**: la fuente era la más
frágil del pipeline (regex sobre notas de prensa) y su rol conceptual —agua que baja hacia Guayaquil— lo
cubre mejor el caudal del río Guayas medido por GEOGLOWS; `nivel_embalse_msnm` se sigue archivando como
contexto en el parquet. `calcular_indice_riesgo()` también devuelve `exposicion_norm` e `indice_impacto`
(riesgo × exposición poblacional de la zona) — `indice_riesgo` en sí sigue siendo amenaza pura.

[data/geo_ref/zonas_guayaquil.csv](backend/spark/data/geo_ref/zonas_guayaquil.csv) (22+ zonas y parroquias) es la
tabla estática de zonas. La leen Spark y la API (dos endpoints); cambiar sus columnas rompe los tres.

### API (`backend/api/`)
FastAPI de solo lectura. [hdfs_client.py](backend/api/hdfs_client.py) habla **WebHDFS** con la librería `hdfs`
pura-Python. Le da dos garantías a `app.py`: traduce "la ruta no existe" a `FileNotFoundError` (el
resto sigue siendo `HdfsError` → 503, no 404) y acota cuántas particiones de fecha lee.

`SPARK_APP_DIR` (default `/app/spark`, que es donde el compose ubica `backend/spark`) es lo que permite
importar `risk_index` y ubicar el CSV. Cada fuente de datos y capa geográfica en HDFS expone su propio
endpoint REST normalizado (`/api/eventos/sgr`, `/api/capas/parroquias`, `/api/capas/sectores`, `/api/clima/inamhi`, etc.),
retornando respuestas estandarizadas bajo el modelo `RespuestaAPI`. `/api/escenario/simular` recalcula el índice en memoria sin
tocar HDFS. `/api/clima/punto` es un proxy de OpenWeatherMap.

### Frontend (`frontend/`)
HTML/CSS/JS sin build step ni gestor de paquetes: MapLibre GL, Chart.js y Turf por CDN, con versión
exacta y `integrity` (SRI). Se sirve como estático desde la propia API en `/dashboard`, y el objeto
`CONFIG` en [config.js](frontend/js/config.js) usa rutas **relativas** (`/api/`).
Utiliza Turf.js (`turf.booleanPointInPolygon`) para filtrar geométricamente los eventos de lluvia SGR
dentro del polígono de la parroquia activa.
`index.html` cachebustea con querystring (`js/main.js?v=16`, `styles.css?v=19`) — **incrementar ese número
al editar** o el navegador servirá la versión vieja. Los 9 módulos ES bajo `js/` se importan entre sí con
rutas relativas (`import ... from './dashboard.js?v=16'`) que llevan el **mismo** `?v=` que `main.js`:
bumpear solo `main.js?v=` no invalida esos imports internos, porque el navegador los cachea por URL
completa (incluida la querystring) — hay que bumpear los dos a la vez.
