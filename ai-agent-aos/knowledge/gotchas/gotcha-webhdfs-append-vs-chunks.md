---
id: 20260927145505
type: gotcha
status: evergreen
title: "Gotcha: Escritura de Logs en HDFS vía WebHDFS (Append vs Archivos Chunked)"
created: 2026-09-27
---

# Gotcha: Escritura de Logs en HDFS (Append vs Archivos Chunked)

## Problema
El soporte de `append` en WebHDFS (`dfs.webhdfs.enabled` y `dfs.support.append`) puede estar deshabilitado o presentar problemas de consistencia y bloqueos de leases en clústeres Hadoop estándar cuando múltiples productores intentan escribir continuamente en un único archivo de log.

## Solución en el Proyecto
El handler de observabilidad `HandlerHDFS` (`backend/producers/common/kafka_client.py`) **nunca realiza append**.
En su lugar, bufferiza los registros en memoria y en cada flush escribe un archivo inmutable nuevo:
```
/enso_data/raw/producer_logs/producer={nombre}/fecha=YYYY-MM-DD/{epoch_ms}.log
```

La API (`backend/api/routers/observabilidad.py` y `hdfs_client.py`) lee todos los `.log` de la partición y los concatena ordenados por timestamp, evitando problemas de concurrencia y leases bloqueados en HDFS.
