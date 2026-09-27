---
id: 20260927152004
type: skill-spec
status: evergreen
name: "backend-spark"
runtime: python3 / pyspark
entrypoint: "backend/spark/spark_streaming_job.py"
inputs:
  - name: component
    type: string
    description: "Componente a modificar: streaming_job, risk_index o interpolacion"
    required: false
outputs:
  format: "parquet / hdfs-processed"
created: 2026-09-27
updated: 2026-09-27
---

# Skill: Backend PySpark & Risk Processing

> **Propósito**: Guiar el desarrollo y optimización del job de streaming con PySpark ([`spark_streaming_job.py`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/backend/spark/spark_streaming_job.py)), la formulación matemática del índice de riesgo ([`risk_index.py`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/backend/spark/risk_index.py)) y la interpolación espacial IDW ([`interpolacion.py`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/backend/spark/interpolacion.py)).

---

## 1. Dos Consultas de Streaming Independientes

1. **Archivado Crudo (Raw Archival)**:
   - Un `writeStream` por tópico Kafka vía `write_raw_zone(df, nombre_fuente)`.
   - Escribe en `/enso_data/raw/{fuente}/fecha=YYYY-MM-DD/*.parquet`.
2. **Cálculo de Riesgo por Micro-Batch (`foreachBatch`)**:
   - Suscrito únicamente a los 8 tópicos que alimentan el índice (marea, embalse, lluvia NASA, lluvia INAMHI, pronóstico Open-Meteo, marea IOC, caudal GEOGLOWS, SST semanal).
   - `EstadoFuentes`: Mantiene los últimos valores conocidos y ejecuta `bootstrap()` desde HDFS al arrancar.
   - `interpolar_idw`: Resuelve precipitación por zona para los 22 sectores.
   - Escribe en `/enso_data/processed/indice_riesgo/fecha=YYYY-MM-DD/*.parquet`.

---

## 2. Formulación de Riesgo e Interacción Física (`risk_index.py`)

- **Python Puro**: Sin dependencias de PySpark (permite importación directa en la API).
- **Ponderación Base (Suma 1.00)**:
  $$\text{Base} = 0.28 P_{\text{norm}} + 0.12 M_{\text{norm}} + 0.15 Q_{\text{norm}} + 0.10 S_{\text{norm}} + 0.20 T_{\text{norm}} + 0.15 H_{\text{norm}}$$
- **Términos de Interacción No Lineal**:
  $$\text{Interacción} = 0.15 (P \cdot M) + 0.15 (Q \cdot M) + 0.10 (\text{ENSO}_{1+2} \cdot P)$$
- **Niveles de Riesgo**: `bajo` (<0.25), `medio` (0.25-0.50), `alto` (0.50-0.75), `critico` ($\ge 0.75$) en minúsculas.
- **Índice de Impacto**: $\text{Impacto} = \text{Riesgo} \times \text{Exposición}_{\text{norm}}$.

---

## 3. Checklist de Verificación
- [ ] `pytest tests/test_risk_index.py tests/test_interpolacion.py tests/test_estado_fuentes.py -q` pasa al 100%.
- [ ] La suma de pesos `PESO_*` en `risk_index.py` es exactamente `1.00`.
- [ ] `backend/spark/contracts.py` se mantiene sincronizado con `backend/contracts.py`.
