# GEMINI.md — Guía Técnica Integral de Godzilla-EnsoStreamingPipeline

Este documento constituye la referencia técnica completa y exhaustiva del proyecto **Godzilla-EnsoStreamingPipeline**, un sistema de procesamiento en tiempo real distribuido para la ingesta, análisis, modelado predictivo del riesgo de inundación y visualización geoespacial ante el Fenómeno El Niño (ENSO) en el Cantón Guayaquil, Ecuador.

---

## 1. Visión General del Proyecto

### 1.1. Propósito y Dominio
Guayaquil presenta una vulnerabilidad extrema ante inundaciones compuestas (*compound flooding*) debido a la convergencia simultánea de:
- Precipitaciones convectivas intensas asociadas a la fase cálida del ENSO (anomalías en las regiones Niño 1+2 y Niño 3.4).
- Mareas astronómicas y de tormenta en el estuario del Río Guayas que impiden el drenaje pluvial por gravedad durante pleamar.
- Crecidas del Río Guayas y tributarios (Daule y Babahoyo), junto con los niveles de embalses reguladores (Daule-Peripa).
- Saturación previa del suelo y topografía baja y plana en zonas urbanas críticas.

El objetivo del sistema es monitorear en tiempo real variables meteorológicas, oceánicas, hidrológicas y territoriales, ejecutar una arquitectura de Big Data en streaming (Kafka + PySpark + HDFS) y exponer los resultados a través de una API REST de alto rendimiento y un dashboard analítico e interactivo.

### 1.2. Principio Rector: Integridad y Degradación Explícita
El pipeline implementa una política estricta de **degradación explícita (no invención de datos)**:
- Si una fuente remota (INOCAR, CELEC, NOAA, INAMHI, etc.) no responde o degrada su servicio, el productor **nunca inventa valores artificiales**.
- El job de Spark y el modelo de riesgo rastrean el origen de cada entrada (`origen="real"` vs `origen="default"`), garantizando que las métricas calculadas con respaldos sean auditables en HDFS y en la API.

---

## 2. Arquitectura del Sistema de Punta a Punta

```
               FUENTES EXTERNAS (APIs, Scraping, PDF, Satélites)
  [NOAA / CPC] [INAMHI] [INOCAR / IOC] [GEOGLOWS] [NASA POWER] [Open-Meteo] [CELEC]
                                     │
                                     ▼
                CAPA DE INGESTA DISTRIBUIDA (Kafka Producers)
                 20+ Productores Python supervisados (run_producers.py)
                 Buffer de Observabilidad hacia HDFS (HandlerHDFS)
                                     │
                                     ▼
                  CAPA DE MENSAJERÍA (Apache Kafka Cluster)
                   19 Tópicos estructurados (cp-kafka 7.6.1)
                                     │
                                     ▼
             CAPA DE PROCESAMIENTO EN STREAMING (Apache Spark 3.5.1)
           - Ingesta estructurada (readStream kafka)
           - Particionado y persistencia raw en HDFS (Parquet)
           - Interpolación espacial IDW de precipitación por sector
           - Cálculo del Índice Multidimensional de Riesgo e Impacto
                                     │
                                     ▼
                 CAPA DE ALMACENAMIENTO (Hadoop HDFS 3.3.6)
             /enso_data/raw/{fuente}/fecha=YYYY-MM-DD/*.parquet
             /enso_data/processed/indice_riesgo/fecha=YYYY-MM-DD/*.parquet
             /enso_data/raw/producer_logs/producer={p}/fecha=YYYY-MM-DD/*.log
                                     │
                                     ▼
                     CAPA DE SERVICIO (FastAPI REST API)
           - Lectura optimizada vía WebHDFS (hdfs_client.py con TTL Cache)
           - Envelope uniforme RespuestaAPI[T]
           - Proxies seguros y endpoints de simulación/pronóstico
                                     │
                                     ▼
                   CAPA DE PRESENTACIÓN (Frontend Dashboard)
          - MapLibre GL JS + Capas GeoJSON + Ruteo de Evacuación OSRM
          - ECharts / Chart.js + Simulador interactivo de escenarios
          - Tablero de observabilidad y auditoría de productores (/logs)
```

---

## 3. Componentes del Repositorio

### 3.1. Estructura de Directorios

```
Godzilla-EnsoStreamingPipeline/
├── backend/
│   ├── contracts.py                # Contrato canónico de esquemas y parsers
│   ├── env/                        # Configuración y credenciales (.env, GEE JSON)
│   ├── api/                        # Servicio FastAPI REST
│   │   ├── app.py                  # Entrada principal y montaje de rutas
│   │   ├── hdfs_client.py          # Cliente WebHDFS puro en Python con caché
│   │   ├── helpers.py              # Funciones auxiliares y singleton de cliente
│   │   ├── schemas.py              # Modelos Pydantic para OpenAPI / Swagger
│   │   ├── analisis_logs.py        # Agregaciones de observabilidad y salud
│   │   └── routers/                # Enrutadores por dominio funcional
│   │       ├── alertas.py          # Boletines SNGR
│   │       ├── capas.py            # GeoJSON estáticos (sectores, zonas, vías)
│   │       ├── clima.py            # Telemetría meteorológica y proxies
│   │       ├── enso.py             # Índices oceánicos Niño 1+2 / 3.4
│   │       ├── eventos.py          # Incidentes reportados SGR
│   │       ├── hidrologia.py       # Mareas, embalse y caudal
│   │       ├── observabilidad.py   # Logs y estados de productores
│   │       ├── riesgo.py           # Riesgo actual, histórico, simulación y pronóstico
│   │       └── salud.py            # Healthcheck de la API
│   ├── producers/                  # Productores Kafka
│   │   ├── run_producers.py        # Supervisor con backoff exponencial
│   │   ├── common/kafka_client.py  # Wrapper de KafkaProducer y HandlerHDFS
│   │   ├── producer_caudal_geoglows.py
│   │   ├── producer_celec_embalse.py
│   │   ├── producer_copernicus.py
│   │   ├── producer_enso_indexes.py
│   │   ├── producer_gee.py
│   │   ├── producer_guayas_osm.py
│   │   ├── producer_inamhi.py
│   │   ├── producer_inamhi_nivel_rio.py
│   │   ├── producer_inamhi_precipitacion.py
│   │   ├── producer_inocar_mareas.py
│   │   ├── producer_marea_observada.py
│   │   ├── producer_nasa_power.py
│   │   ├── producer_ndbc_buoys.py
│   │   ├── producer_noaa.py
│   │   ├── producer_open_meteo.py
│   │   ├── producer_openweathermap.py
│   │   ├── producer_pronostico_precip.py
│   │   ├── producer_seguraep.py
│   │   ├── producer_sgr_eventos.py
│   │   ├── producer_sngr_alertas.py
│   │   └── producer_sst_semanal.py
│   └── spark/                      # Motor de procesamiento distribuido
│       ├── spark_streaming_job.py  # Structured Streaming Job
│       ├── risk_index.py           # Fórmula no lineal del índice de riesgo
│       ├── interpolacion.py        # Algoritmo espacial IDW puro
│       ├── contracts.py            # Espejo del contrato para Spark Worker
│       └── data/geo_ref/
│           └── zonas_guayaquil.csv # 22 sectores urbanos de referencia
├── docker/
│   └── hadoop/                     # Dockerfile y configuración del clúster HDFS
├── frontend/                       # Aplicación Web SPA sin pasos de build
│   ├── index.html                  # Dashboard principal
│   ├── styles.css                  # Estilos visuales optimizados (Dark Theme)
│   ├── logs.css                    # Estilos del panel de observabilidad
│   ├── js/
│   │   ├── main.js                 # Orquestador del frontend
│   │   ├── config.js               # Constantes y utilidades DOM
│   │   ├── dashboard.js            # Lógica de refresco y componentes
│   │   ├── logs.js / logs-resumen.js # Consumo de métricas de observabilidad
│   │   ├── api/client.js           # Cliente HTTP con desempaquetado de envelope
│   │   ├── components/charts.js    # Visualizaciones ECharts / Chart.js
│   │   ├── map/map-manager.js      # MapLibre GL JS, capas e interacciones
│   │   ├── map/map-popups.js       # Popups dinámicos por zona y punto
│   │   └── ui/                     # Controles, simulación y timelapse
│   └── logs/index.html             # Vista dedicada de auditoría de logs
├── scripts/
│   └── derivar_zonas_gee.py        # Generación de DEM y WorldPop vía GEE
├── tests/                          # Suite automatizada de pruebas (pytest)
├── compose.yml                     # Orquestación multicontenedor Docker
└── pyproject.toml / requirements.txt # Dependencias del proyecto
```

---

## 4. Contratos de Datos y Fuentes Ingestadas

### 4.1. Catálogo de Productores y Tópicos Kafka

| Tópico Kafka | Productor Script | Fuente Primaria | Variable Principal / Rol | Cadencia Recomendada |
| :--- | :--- | :--- | :--- | :--- |
| `mareas-inocar` | `producer_inocar_mareas.py` | INOCAR (PDF/Scraping) | Altura marea modelada (m), tendencia | 15 min |
| `marea-observada` | `producer_marea_observada.py` | IOC (Mareógrafo `gyer`) | Altura marea observada por radar (m) | 15 min |
| `nivel-embalse-celec` | `producer_celec_embalse.py` | CELEC EP (WP REST API) | Cota embalse Daule-Peripa (msnm) | 60 min |
| `nasa-power-data` | `producer_nasa_power.py` | NASA POWER API | Precipitación diaria (mm) en Guayaquil | 60 min |
| `inamhi-precipitacion`| `producer_inamhi_precipitacion.py` | INAMHI API Visor | Lluvia 24h en 24+ estaciones Guayas | 15 min |
| `pronostico-precipitacion`| `producer_pronostico_precip.py` | Open-Meteo Forecast | Pronóstico de lluvia a 24h (mm) | 30 min |
| `caudal-geoglows` | `producer_caudal_geoglows.py` | GEOGLOWS v2 (ECMWF) | Caudal del Río Guayas ($m^3/s$) | 60 min |
| `sst-semanal` | `producer_sst_semanal.py` | NOAA CPC `wksst9120.for` | SST y Anomalía Niño 1+2 / 3.4 (°C) | 12 horas |
| `inamhi-nivel-rio` | `producer_inamhi_nivel_rio.py` | INAMHI Hidrología | Nivel de agua en estaciones fluviales | 12 horas |
| `alertas-sngr` | `producer_sngr_alertas.py` | SNGR Ecuador | Boletines de alerta temprana | 15 min |
| `sgr-eventos` | `producer_sgr_eventos.py` | SGR Ecuador | Histórico de emergencias por lluvia | 60 min |
| `noaa-data` | `producer_noaa.py` | NOAA OISST | Temperatura superficial marina | 60 min |
| `enso-indexes` | `producer_enso_indexes.py` | NOAA / CPC ONI | Índices climáticos ONI, SOI | 60 min |
| `open-meteo-data` | `producer_open_meteo.py` | Open-Meteo | Clima regional en Niño 3.4 | 60 min |
| `openweathermap-data`| `producer_openweathermap.py`| OpenWeatherMap | Clima actual y capas meteorológicas | 60 min |
| `ndbc-buoys` | `producer_ndbc_buoys.py` | NOAA NDBC | Boyas oceánicas en el Pacífico | 60 min |
| `gee-data` | `producer_gee.py` | Google Earth Engine | Índices satelitales (NDVI, NDWI) | 60 min |
| `guayas-osm` (one-shot) | `producer_guayas_osm.py` | OpenStreetMap Overpass | Infraestructura y vías vulnerables | 6 horas |
| `seguraep.py` (one-shot)| `producer_seguraep.py` | Segura EP Guayaquil | Zonas de refugio y albergues | 6 horas |

### 4.2. Estructura de Clases Canónicas (`backend/contracts.py`)
- `Lectura`: Modela un valor numérico junto con su origen canónico (`"real"` vs `"default"`) y un mensaje explicativo.
- `LluviaEstacion`: Modela una estación pluviométrica de INAMHI con coordenadas `(lat, lon)`, `precip_24h_mm` y timestamp.

---

## 5. Procesamiento Distribuido en Spark y Modelo de Riesgo

### 5.1. Flujo de `spark_streaming_job.py`
1. **Bootstrap del Estado**: Al arrancar, `EstadoFuentes.bootstrap()` consulta las particiones más recientes de HDFS (`/enso_data/raw/{fuente}`) para inicializar la memoria con telemetría real previa.
2. **Ingesta Multi-Tópico Kafka**: Consume en streaming los 19 tópicos.
3. **Persistencia Raw**: Escribe cada evento crudo en `/enso_data/raw/{fuente}/fecha=YYYY-MM-DD/*.parquet` particionado por fecha.
4. **Interpolación Espacial IDW**: Para cada una de las 22 zonas de Guayaquil, interpola la precipitación a partir de las estaciones INAMHI válidas mediante distancia Haversine:
   $$w_i = \frac{1}{d_i^p} \quad (p=2.0, \text{radio} = 25\text{ km})$$
   $$P_{\text{interpolado}} = \frac{\sum w_i P_i}{\sum w_i}$$
5. **Cálculo de Saturación Antecedente (API)**:
   $$\text{API} = \sum_{i=1}^{15} k^i \cdot P_i \quad (k = 0.9)$$
6. **Persistencia Procesada**: Guarda el DataFrame resultante en `/enso_data/processed/indice_riesgo/fecha=YYYY-MM-DD/*.parquet`.

### 5.2. Formulación Matemática del Índice de Riesgo (`backend/spark/risk_index.py`)
El índice no es una regresión lineal simple; incorpora **términos de interacción física** que reflejan cómo la pleamar estrangula el drenaje pluvial y cómo la anomalía térmica ENSO intensifica la convección atmosférica:

$$\text{Base} = 0.28 P_{\text{norm}} + 0.12 M_{\text{norm}} + 0.15 Q_{\text{norm}} + 0.10 S_{\text{norm}} + 0.20 T_{\text{norm}} + 0.15 H_{\text{norm}}$$

$$\text{Interacción} = 0.15 (P_{\text{norm}} \cdot M_{\text{norm}}) + 0.15 (Q_{\text{norm}} \cdot M_{\text{norm}}) + 0.10 (\text{ENSO}_{1+2} \cdot P_{\text{norm}})$$

$$\text{Índice de Riesgo} = \min(1.0, \max(0.0, \text{Base} + \text{Interacción}))$$

#### Factores y Normalizaciones:
- $P_{\text{norm}} = \text{clip}(P_{24h} / 150.0\text{ mm})$
- $M_{\text{norm}} = \text{clip}((M - 0.4) / (3.6 - 0.4))$
- $Q_{\text{norm}} = \text{clip}((Q - 400.0) / (1800.0 - 400.0))$
- $S_{\text{norm}} = \text{clip}(\text{API} / 120.0\text{ mm})$
- $\text{ENSO}_{1+2} = \text{clip}(\Delta T_{1+2} / 4.0^\circ\text{C})$
- $T_{\text{norm}} = 0.5 \cdot \text{Cota}_{\text{norm}} + 0.3 \cdot \text{Pendiente}_{\text{factor}} + 0.2 \cdot \text{Cercanía}_{\text{norm}}$
- $H_{\text{norm}} = 1.0$ si la zona es históricamente inundable, $0.0$ si no.

#### Métricas Derivadas:
- **Nivel de Riesgo**: `bajo` (<0.25), `medio` (0.25-0.50), `alto` (0.50-0.75), `critico` ($\ge 0.75$).
- **Exposición e Impacto**:
  $$\text{Exposición}_{\text{norm}} = \text{clip}\left(\frac{\text{Población}}{200\,000}\right)$$
  $$\text{Índice de Impacto} = \text{Índice de Riesgo} \times \text{Exposición}_{\text{norm}}$$

---

## 6. Servicio Backend (FastAPI) y Persistencia HDFS

### 6.1. Acceso a Datos vía WebHDFS (`backend/api/hdfs_client.py`)
- Utiliza la librería pura de Python `hdfs.InsecureClient` sobre el puerto WebHDFS (`http://namenode:9870`).
- No requiere dependencias nativas C de Hadoop (`libhdfs` / C++ binaries).
- Descarga los bytes del archivo Parquet directamente en memoria (`io.BytesIO`) y los convierte a `pandas.DataFrame` mediante `pyarrow`.
- Incorpora caché TTL en memoria (`CacheTTL`) para mitigar sobrecarga de E/S en peticiones recurrentes.

### 6.2. Envoltorio Estándar de Respuestas (`RespuestaAPI`)
Todos los endpoints REST envuelven su salida bajo un formato consistente:
```json
{
  "status": "success",
  "data": { ... },
  "error": null,
  "meta": {
    "api_version": "1.2.0",
    "timestamp": "2026-09-27T14:20:00Z",
    "fuente": "/enso_data/processed/indice_riesgo",
    "total_registros": 22
  }
}
```

En caso de error HTTP (404, 502, 503):
```json
{
  "status": "error",
  "data": null,
  "error": {
    "codigo": 503,
    "tipo": "SERVICIO_HDFS_NO_DISPONIBLE",
    "mensaje": "No se pudo conectar con el clúster HDFS",
    "detalle": "ConnectionRefusedError..."
  },
  "meta": { ... }
}
```

### 6.3. Módulos de Enrutamiento (Routers)
- `/api/salud`: Verificación de operatividad.
- `/api/riesgo/zonas`: Evaluación de riesgo actual por sector.
- `/api/riesgo/zonas/{zona_id}/historico`: Series temporales por sector.
- `/api/escenario/simular`: Simulador what-if con parámetros dinámicos de lluvia, marea, río, suelo y ENSO.
- `/api/riesgo/pronostico`: Estimación predictiva a 24 horas.
- `/api/enso/estado`, `/api/enso/indices`: Telemetría oceánica.
- `/api/hidrologia/mareas/actual`, `/api/hidrologia/embalse/actual`, `/api/hidrologia/caudal/actual`: Entradas físicas.
- `/api/clima/*`: Datos de estaciones y proxies seguros hacia OpenWeatherMap.
- `/api/logs/*`: Auditoría y resumen de observabilidad de productores.

---

## 7. Frontend y Experiencia de Usuario

### 7.1. Principios de Diseño
- **Zero-Build Step**: Arquitectura basada exclusivamente en ES Modules nativos del navegador.
- **Paleta de Colores de Alta Visibilidad**:
  - `Bajo`: `#22c55e` (Verde)
  - `Medio`: `#eab308` (Amarillo)
  - `Alto`: `#f97316` (Naranja)
  - `Crítico`: `#ef4444` (Rojo)
  - `Background`: `#0f172a` / `#1e293b` (Dark Slate)
- **Cache-Busting Obligatorio**: Importaciones con versión query param (`import ... from './config.js?v=22'`) para garantizar sincronización en navegadores clientes.

### 7.2. Capacidades Interactivas
1. **Mapa Dinámico (MapLibre GL JS)**:
   - Polígonos de zonas coloreados según nivel de riesgo.
   - Capas superpuestas: mareógrafos, estaciones meteorológicas, vías vulnerables y albergues.
   - Ruteo dinámico de evacuación hacia el refugio más cercano vía OSRM.
2. **Simulador de Escenarios**:
   - Controles deslizantes para alterar variables climáticas e hidrológicas y previsualizar en tiempo real el impacto en el mapa y en el gauge global.
3. **Timelapse Histórico**:
   - Reproducción horaria de la evolución del riesgo durante los últimos días.
4. **Tablero de Observabilidad (`/logs`)**:
   - Monitoreo en vivo de la salud de los productores Kafka, tasa de errores, degradaciones y auditoría de líneas de log archivadas en HDFS.

---

## 8. Guía de Ejecución y Operación

### 8.1. Variables de Entorno Clave (`backend/env/.env`)

```ini
OPENWEATHERMAP_API_KEY=tu_api_key_aqui
GEE_CREDENTIALS_PATH=/app/ensostreamingpipeline-7f414895f6f4.json
KAFKA_BOOTSTRAP_SERVERS=kafka:29092
TZ=America/Guayaquil
WEBHDFS_URL=http://namenode:9870
HDFS_BASE_PATH=/enso_data
```

### 8.2. Despliegue con Docker Compose

```bash
# 1. Levantar toda la infraestructura (HDFS, Kafka, Spark, Producers, API)
docker compose up -d --build

# 2. Verificar el estado de los servicios
docker compose ps

# 3. Consultar logs del supervisor de productores
docker compose logs -f producers

# 4. Consultar logs del submitter de Spark
docker compose logs -f spark-submitter

# 5. Acceder a los tableros web:
# - Dashboard Principal: http://localhost:8000/dashboard
# - Observabilidad de Logs: http://localhost:8000/logs
# - Swagger Docs: http://localhost:8000/docs
# - Spark Master UI: http://localhost:8080
# - Hadoop HDFS NameNode UI: http://localhost:9870
```

### 8.3. Ejecución de la Suite de Pruebas

```bash
# Ejecutar todas las pruebas unitarias y de integración de contratos
pytest -v
```

---

## 9. Resumen de Buenas Prácticas y Mantenimiento

1. **Modificación de Esquemas**: Cualquier cambio en los payloads debe realizarse primero en `backend/contracts.py`. Como este módulo es consumido tanto por los productores como por el submitter de Spark, no debe contener dependencias externas pesadas (como `pyspark` o `kafka`).
2. **Cero Mocks HTTP en Tests**: Los tests de contrato verifican lógica de normalización pura y parseo de payloads. Si una fuente externa cambia su JSON o PDF, se debe actualizar la fixture correspondiente en `tests/test_contracts.py`.
3. **Resiliencia ante Caídas de HDFS**: Los endpoints REST deben capturar `HdfsError` y convertirlo en `HTTP 503 (SERVICIO_HDFS_NO_DISPONIBLE)` mediante el helper `hdfs_caido()`, evitando propagar excepciones 500 no controladas.
