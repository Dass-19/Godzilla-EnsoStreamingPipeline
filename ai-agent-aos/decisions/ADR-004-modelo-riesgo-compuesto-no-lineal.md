---
id: 20260927145521
type: decision
status: vigente
title: "ADR-004: Modelo Compuesto No Lineal con Términos de Interacción Física para el Índice de Riesgo"
created: 2026-09-27
---

# ADR-004: Modelo de Riesgo Compuesto No Lineal

> **Decisión**: El cálculo del índice de riesgo de inundación en Guayaquil incorporará términos de interacción no lineal entre lluvia y pleamar, caudal fluvial y pleamar, y anomalía térmica ENSO y precipitación, en lugar de una combinación lineal simple.

## Contexto
En Guayaquil, el drenaje pluvial urbano descarga por gravedad hacia el estuario del Río Guayas. Durante la pleamar, las compuertas y tuberías quedan anegadas por la marea, impidiendo la evacuación del agua. Por lo tanto, una lluvia intensa combinada con marea alta multiplica el riesgo de inundación mucho más que la simple suma aritmética de ambos factores por separado.

## Consecuencias
- **A favor**:
  - Refleja la física hidrodinámica real de las inundaciones compuestas (*compound flooding*).
  - Captura la amplificación convectiva costera generada por anomalías positivas de temperatura superficial del mar en la región Niño 1+2.
- **En contra**:
  - Requiere documentar y calibrar explícitamente los factores de ponderación e interacción en `risk_index.py`.

## Condiciones de Revocación
Si se integra un modelo hidrodinámico numérico 2D en tiempo real (ej: HEC-RAS o Telemac) acoplado directamente al pipeline.
