---
name: backend-spark
description: 'Use this skill when developing, optimizing, or debugging the PySpark Structured Streaming job (spark_streaming_job.py), the risk index formula (risk_index.py), or the IDW spatial interpolation module (interpolacion.py). Trigger phrases: "backend spark", "pyspark", "spark streaming", "risk index", "interpolation", "spark job", "hdfs parquet", "calc risk".'
---

# Backend PySpark & Risk Processing Skill

## Overview
Governs `backend/spark/`. The job consumes raw Kafka telemetry, archives every message unparsed to
`hdfs://…/enso_data/raw/<fuente>/fecha=YYYY-MM-DD/`, and runs a **separate** streaming query that
computes a per-zone flood-risk index and writes it to `hdfs://…/enso_data/processed/indice_riesgo/`.

---

## 1. Two independent streaming queries in `spark_streaming_job.py`

1. **Raw archival**: one `writeStream` per Kafka topic via `write_raw_zone(df, nombre_fuente)`, using the
   `TOPICS_A_FUENTES` dict (`topic → nombre_fuente`). **Adding a new source = adding its topic to
   `init-kafka` in `compose.yml` + one entry in `TOPICS_A_FUENTES`.**
2. **Risk calculation**: a `foreachBatch` query subscribed only to the topics that feed the index (listed
   in the `topics_riesgo` tuple inside `main()` and `calcular_riesgo_batch`) — currently 8: marea INOCAR,
   embalse CELEC, precipitación NASA POWER, estaciones INAMHI, pronóstico Open-Meteo, marea observada IOC,
   caudal GEOGLOWS, SST semanal. Subscribing only to these avoids deserializing heavy payloads (INAMHI
   catalog, OSM GeoJSON) on every micro-batch just to discard them.

`EstadoFuentes` holds the driver's last-known value per source (updated from each batch's messages, with
a `bootstrap()` from HDFS on startup so a restart doesn't reset everything to fallback values). Its
`lecturas(lat, lon)` method resolves precipitation **per zone** via `interpolar_idw` over the INAMHI
stations currently held in state — every other component is the same across zones. Each output row
carries `origen_precip` / `origen_marea` / `origen_embalse` / `origen_rio` / `origen_suelo` /
`origen_marea_obs` / `origen_enso` (`"real"` | `"default"`, from the `Lectura` dataclass in
`contracts.py`) and `datos_completos`: **a row computed with fallbacks must not be indistinguishable from
a real one.** Rows also carry `epoch_id` because `append` inside `foreachBatch` isn't idempotent — the API
deduplicates by `(zona_id, epoch_id)` on read (`_ultimo_por_zona` in `app.py`).

## 2. `risk_index.py` — pure Python, no Spark

No PySpark import in this file — that's exactly why `backend/api/app.py` can import it directly for the
`/api/escenario/simular` and `/api/riesgo/pronostico` endpoints without a Spark session.

`calcular_indice_riesgo()` combines, all normalized to `[0, 1]` and weighted by `PESO_*` (they sum to
exactly `1.00`, enforced by `test_suma_de_pesos_es_exactamente_uno`):

| Component | Weight constant | Source |
|---|---|---|
| `precip_norm` | `PESO_PRECIP` (0.28) | IDW-interpolated 24h rainfall |
| `marea_norm` | `PESO_MAREA` (0.12) | INOCAR predicted tide |
| `caudal_norm` | `PESO_RIO` (0.15) | Guayas river flow, GEOGLOWS |
| `suelo_norm` | `PESO_SUELO` (0.10) | antecedent soil saturation (API index over INAMHI series) |
| `topografia_norm` | `PESO_TOPOGRAFIA` (0.20) | static per zone: elevation + slope + distance to estuary |
| `historico_norm` | `PESO_HISTORICO` (0.15) | 1.0 if the zone has flood history, else 0 |

**`embalse_norm` (Daule-Peripa reservoir level) is still computed and reported in `componentes`, but does
not weight the index** — CELEC's reservoir feed was the most fragile in the pipeline (regex over press
releases) and its conceptual role (water flowing toward Guayaquil) is better covered by the river flow
from GEOGLOWS. `nivel_embalse_msnm` keeps being archived as dashboard context.

Two interaction terms model that high tide blocks gravity drainage (amplifying both rainfall and river
flow), plus a third that lets a warm Niño 1+2 SST anomaly amplify rainfall (more convection ⇒ same
accumulation falls with more hourly intensity):
```python
interaccion = (FACTOR_INTERACCION_LLUVIA_MAREA * precip_norm * marea_norm
             + FACTOR_INTERACCION_RIO_MAREA    * caudal_norm * marea_norm
             + FACTOR_AMPLIFICACION_ENSO       * enso12_norm * precip_norm)
```
`_clip01()` bounds the final `base + interaccion` sum. Risk levels come from `_clasificar_nivel()`:
`score < 0.25` → `"bajo"`, `< 0.5` → `"medio"`, `< 0.75` → `"alto"`, else `"critico"` — **lowercase, not**
`BAJO/MEDIO/ALTO/EXTREMO`.

`calcular_indice_riesgo()` also returns `exposicion_norm` (population / `poblacion_maxima`) and
`indice_impacto = indice_riesgo × exposicion_norm`. `indice_riesgo` itself never changes meaning — it
stays a pure hazard index; exposure/impact are separate metrics layered on top.

When adding or recalibrating a threshold/weight, keep the sum-to-1.00 invariant and document the
justification in a comment (the technical report needs to be able to cite it).

## 3. `interpolacion.py` — IDW, also pure Python

[interpolacion.py](../../../backend/spark/interpolacion.py) has one job: `interpolar_idw(estaciones, lat,
lon, potencia=2.0, radio_km=25.0, minimo_estaciones=1)` resolves a rainfall value at a point from nearby
INAMHI stations using classic inverse-distance weighting over haversine distance. Returns
`(valor, n_estaciones_usadas)`, or `(None, 0)` if nothing is within `radio_km` or `minimo_estaciones` isn't
met — that `None` becomes a `Lectura` fallback upstream, same pattern as every other source. It does
**not** currently get imported by `app.py` (unlike `risk_index.py`) — the simulator endpoints take
`precip_24h_mm` as a direct query parameter instead of interpolating per zone.

## 4. Zone reference CSV

[backend/spark/data/geo_ref/zonas_guayaquil.csv](../../../backend/spark/data/geo_ref/zonas_guayaquil.csv)
is read by both Spark (`inferSchema`, native types) and the API (`csv.DictReader`, everything a string —
`historicamente_inundable` gets compared with `.lower() == "true"`). Changing its columns breaks both
readers; a new numeric column needs an explicit `float(...)` on the API side, and the API's
`_zonas_referencia()` is `@lru_cache(maxsize=1)` — restart the API after editing the CSV.

## 5. Key Files

- **Streaming Job**: [backend/spark/spark_streaming_job.py](../../../backend/spark/spark_streaming_job.py)
- **Modelo de Riesgo**: [backend/spark/risk_index.py](../../../backend/spark/risk_index.py)
- **Interpolación IDW**: [backend/spark/interpolacion.py](../../../backend/spark/interpolacion.py)
- **CSV de Zonas**: [backend/spark/data/geo_ref/zonas_guayaquil.csv](../../../backend/spark/data/geo_ref/zonas_guayaquil.csv)

## 6. Verification Checklist

- [ ] `pytest tests/test_risk_index.py tests/test_interpolacion.py tests/test_estado_fuentes.py -q`
- [ ] If a weight changed: `test_suma_de_pesos_es_exactamente_uno` still passes.
- [ ] `calcular_indice_riesgo(...)` still returns `indice_riesgo`, `nivel_riesgo` (`bajo|medio|alto|critico`),
      `exposicion_norm`, `indice_impacto`, and `componentes`.
- [ ] After editing anything under `backend/spark/`: `docker compose restart spark-submitter` (it's a
      bind-mount, not a build).
