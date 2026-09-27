---
id: 20260927145520
type: decision
status: vigente
title: "ADR-003: Acceso a HDFS vía WebHDFS Puro en Python sin Dependencias Nativas libhdfs"
created: 2026-09-27
---

# ADR-003: Acceso a HDFS vía WebHDFS Puro en Python

> **Decisión**: La capa de servicio REST (FastAPI) leerá particiones Parquet en HDFS a través del protocolo WebHDFS HTTP (puerto 9870) utilizando el paquete puro `hdfs` y conversión en memoria con `pyarrow`, sin instalar binarios C nativos de Hadoop (`libhdfs`).

## Contexto
Compilar y configurar binarios nativos de Hadoop y variables `CLASSPATH` en imágenes Docker livianas de FastAPI (Python 3.11-slim) introduce dependencias pesadas de JVM y librerías C, aumentando el tamaño de la imagen y la fragilidad del despliegue.

## Consecuencias
- **A favor**:
  - Imágenes Docker ligeras y portables.
  - Cero dependencias de Java en el contenedor de FastAPI.
  - Lectura en memoria directa con `io.BytesIO` y `pandas.read_parquet()`.
- **En contra**:
  - WebHDFS tiene una ligera sobrecarga HTTP en comparación con socket IPC nativo de Hadoop, mitigada mediante caché TTL (`CacheTTL`).

## Condiciones de Revocación
Si el volumen de consultas concurrentes directas a HDFS satura el NameNode HTTP y se decide migrar a una base de datos analítica intermedia (ej. DuckDB o ClickHouse).
