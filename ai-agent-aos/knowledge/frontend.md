---
id: 20260927145502
type: knowledge
status: evergreen
title: "Base de Conocimiento: Frontend, Visualización y UX"
created: 2026-09-27
---

# Base de Conocimiento: Frontend

## 1. Arquitectura Zero-Build Step

- **Tecnología**: JavaScript vanilla utilizando ES Modules nativos (`import` / `export`).
- **Sin bundlers**: No requiere Webpack, Vite, Rollup ni npm build. Los archivos son servidos directamente por FastAPI (`StaticFiles`) en `/dashboard` y `/logs`.
- **Regla de Cache-Busting Obligatorio**: Cualquier importación entre módulos JS debe llevar la versión query string (ej: `import { CONFIG } from './config.js?v=22';`). Si se modifica un módulo JS, se debe incrementar el sufijo de versión de los imports.

---

## 2. Paleta de Colores y Jerarquía Visual de Riesgo

| Nivel de Riesgo | Rango Numérico | Color Hex | Semántica |
| :--- | :--- | :--- | :--- |
| **Bajo** | $[0.00, 0.25)$ | `#22c55e` | Verde esmeralda. Sin riesgo de anegamiento. |
| **Medio** | $[0.25, 0.50)$ | `#eab308` | Amarillo ámbar. Alerta preventiva. |
| **Alto** | $[0.50, 0.75)$ | `#f97316` | Naranja intenso. Drenaje comprometido. |
| **Crítico** | $[0.75, 1.00]$ | `#ef4444` | Rojo carmesí. Inundación inminente / compuesta. |

- **Fondo / Paneles**: Slate oscuro (`#0f172a` / `#1e293b`).
- **Texto Principal**: `#f8fafc`.
- **Texto Secundario**: `#94a3b8`.

---

## 3. Componentes Principales

1. **Mapa Interactivo (`frontend/js/map/map-manager.js`)**:
   - Motor: MapLibre GL JS.
   - Capas: Polígonos de zonas de riesgo, mareógrafos, estaciones meteorológicas, vías vulnerables, albergues de emergencia.
   - Popups dinámicos (`map-popups.js`) con desglose de componentes y radar chart.
   - Ruteo de evacuación a pie/auto hacia el refugio más cercano vía API OSRM.
2. **Dashboard y Telemetría (`frontend/js/dashboard.js`)**:
   - Tarjetas de estado macro ENSO (Niño 1+2 / Niño 3.4).
   - Gauges de marea, embalse, caudal del río y lluvia acumulada.
   - Boletines de alerta temprana SNGR y emergencias SGR.
3. **Simulador de Escenarios (`frontend/js/ui/simulation.js`)**:
   - Controles interactivos tipo slider para evaluar combinaciones what-if de lluvia, marea, río, saturación de suelo y anomalía térmica.
4. **Timelapse Histórico (`frontend/js/ui/timelapse.js`)**:
   - Reproductor paso a paso de la evolución del riesgo en las últimas horas y días.
5. **Panel de Observabilidad (`frontend/logs/`)**:
   - Vista dedicada para auditoría de salud de productores, conteo de errores y lectura de logs archivados en HDFS.
