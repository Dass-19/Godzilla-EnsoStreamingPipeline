---
name: backend-spark
description: 'Use this skill when developing, optimizing, or debugging PySpark Streaming jobs, risk index computation logic (risk_index.py), spatial/temporal interpolation algorithms (interpolacion.py), checkpointing, or HDFS Parquet partitioning. Trigger phrases: "backend spark", "pyspark", "spark streaming", "risk index", "interpolation", "spark job", "hdfs parquet", "calc risk".'
---

# Backend PySpark & Risk Processing Skill

## Overview
This skill governs the PySpark Streaming processing pipeline, risk index calculation engine, and spatial interpolation module located in `backend/spark/`. The Spark job consumes raw telemetry events from Kafka, computes normalized risk scores for Guayaquil's urban sectors, and writes append-only Parquet partitions to HDFS (`/enso_data/processed/indice_riesgo`).

---

## 1. Pipeline Architecture & Streaming Strategy

1. **Structured Streaming Engine**: Reads Kafka topics in micro-batches using PySpark (`spark_streaming_job.py`).
2. **Zone Geospatial Reference**: Loads sector centroids, ground elevations (`cota_media_msnm`), and historical flood flags from [`backend/spark/data/geo_ref/zonas_guayaquil.csv`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/backend/spark/data/geo_ref/zonas_guayaquil.csv).
3. **Partitioning & Checkpoints**: Writes to WebHDFS Parquet partitioned by date (`year`, `month`, `day`). Ensures fault tolerance via HDFS checkpointing.

---

## 2. Mathematical Risk Model (`risk_index.py`)

The risk index algorithm in [`risk_index.py`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/backend/spark/risk_index.py) evaluates a multi-factor risk score:

$$I_R = f(\text{Lluvia}, \text{Marea}, \text{Cota Topográfica}, \text{Caudal}, \text{Saturación Suelo}, \text{Anomalía SST})$$

### Core Rules for Risk Calculations:
- **Normalización**: All sub-indices (Amenaza, Vulnerabilidad, Exposición) must be bounded strictly between `0.0` and `1.0`.
- **Categorías de Riesgo**:
  - `0.0 <= score < 0.35`: **BAJO** (Verde)
  - `0.35 <= score < 0.60`: **MEDIO** (Amarillo)
  - `0.60 <= score < 0.80`: **ALTO** (Naranja)
  - `0.80 <= score <= 1.00`: **EXTREMO** (Rojo)
- **Manejo de Valores Faltantes (Fallback)**: When real-time telemetries are missing, historical mean values are substituted and `datos_completos` flag is set to `False`.

---

## 3. Spatial & Temporal Interpolation (`interpolacion.py`)

The module [`interpolacion.py`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/backend/spark/interpolacion.py) handles point-to-polygon surface estimation:

1. **Inverse Distance Weighting (IDW)**: Interpolates rainfall measurements from sparse INAMHI rain gauges to sector centroids.
2. **Distancia a Estero**: Calculates exponential distance decay to esteros (e.g. Estero Salado, Río Guayas) for tide lock risk amplification.

---

## 4. Key Files & Components

- **Streaming Job**: [`backend/spark/spark_streaming_job.py`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/backend/spark/spark_streaming_job.py)
- **Modelo Matemático**: [`backend/spark/risk_index.py`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/backend/spark/risk_index.py)
- **Interpolación Espacial**: [`backend/spark/interpolacion.py`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/backend/spark/interpolacion.py)
- **CSV de Zonas Geográficas**: [`backend/spark/data/geo_ref/zonas_guayaquil.csv`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/backend/spark/data/geo_ref/zonas_guayaquil.csv)

---

## 5. Verification Checklist

When updating Spark streaming or risk index formulas:
- [ ] Run mathematical model tests: `pytest tests/test_risk_index.py`
- [ ] Run spatial interpolation tests: `pytest tests/test_interpolacion.py`
- [ ] Ensure `calcular_indice_riesgo(...)` returns a dictionary containing `indice_riesgo`, `nivel_riesgo`, `exposicion_norm`, and `indice_impacto`.
