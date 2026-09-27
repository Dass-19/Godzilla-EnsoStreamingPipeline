---
id: 20260927145506
type: gotcha
status: evergreen
title: "Gotcha: Tamaño Máximo de Mensajes en Kafka para Catálogos y GeoJSON"
created: 2026-09-27
---

# Gotcha: Límite de Tamaño de Mensajes en Kafka

## Problema
Por defecto, Apache Kafka impone un límite de $1\text{ MB}$ (`1048576` bytes) por mensaje. El catálogo completo de estaciones de INAMHI (`inamhi-data`, `inamhi-precipitacion`) y los GeoJSON de vías descargados desde OpenStreetMap (`guayas-osm`) superan fácilmente $1\text{ MB}$, lo que provocaba `RecordTooLargeException` en los productores.

## Solución en el Proyecto
1. **Configuración del Broker (`compose.yml`)**:
   ```yaml
   KAFKA_MESSAGE_MAX_BYTES: 10485760       # 10 MB
   KAFKA_REPLICA_FETCH_MAX_BYTES: 10485760 # 10 MB
   ```
2. **Configuración del Producer (`backend/producers/common/kafka_client.py`)**:
   ```python
   MAX_REQUEST_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
   # Pasado a KafkaProducer(max_request_size=MAX_REQUEST_SIZE_BYTES)
   ```
Ambos límites deben mantenerse sincronizados en 10 MB para evitar rechazos de mensajes voluminosos.
