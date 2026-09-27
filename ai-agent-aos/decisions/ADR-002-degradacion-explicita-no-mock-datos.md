---
id: 20260927145519
type: decision
status: vigente
title: "ADR-002: Principio de Degradación Explícita y Prohibición de Inventar Telemetría"
created: 2026-09-27
---

# ADR-002: Degradación Explícita y Prohibición de Inventar Telemetría

> **Decisión**: Los productores y servicios del pipeline **nunca inventarán datos artificiales** ante fallos de fuentes externas. Toda telemetría no disponible debe marcarse explícitamente como `origen="default"` en los contratos de datos.

## Contexto
En sistemas de monitoreo de riesgos naturales ante ENSO, emitir valores simulados o aleatorios haciéndolos pasar por lecturas reales oculta fallas de servicio y puede generar falsas alarmas o desestimar riesgos reales en la toma de decisiones.

## Consecuencias
- **A favor**:
  - Trazabilidad y auditabilidad completa en HDFS y endpoints REST.
  - El modelo de riesgo y la API conocen con precisión qué componentes se basan en lecturas reales y cuáles en respaldos.
- **En contra**:
  - Obliga a los consumidores a manejar posibles `None` o valores de respaldo tipados con metadata de origen.

## Condiciones de Revocación
Ninguna. Este es un principio de integridad inmutable del sistema.
