---
name: frontend-design
description: 'Use this skill when designing or implementing frontend UI components, dashboards, data visualizations, GIS map controls, visual hierarchies, color systems, or user interaction flows for web applications. Trigger phrases: "design a dashboard", "improve UI layout", "frontend design", "map visual hierarchy", "component structure", "dashboard UX".'
---

# Frontend & Dashboard Design System

## Overview
This skill provides guidelines for designing and building data-dense, real-time web applications and GIS dashboards. It combines modern UI aesthetics (dark mode, glassmorphism, harmonious color tokens) with efficient information architecture (Level-of-Detail zooming, non-cluttered map layers, and actionable metrics).

---

## 1. Visual Hierarchy & Dashboard Architecture

### Layout Pattern (F-Pattern / Hybrid Canvas)
- **Top Bar / View Pill**: Global controls, view toggles (Regional vs. Local), and macro status indicators.
- **Center Canvas**: Interactive Map/Visualization taking 100% of viewport.
- **Left Sidebar**: Scrollable container holding hierarchical metric cards:
  - **Level 1 (Headline KPIs)**: Large numbers for primary risk/status metrics.
  - **Level 2 (Contextual Cards)**: Sector-level breakdowns, environmental gauges, forecast cards.
  - **Level 3 (Action / Interactive)**: What-If simulation controls, evacuation routing, historical time-series modal.
- **Floating Overlays**: Translucent layer controls and legends placed at map corners (`backdrop-filter: blur(12px)`).

---

## 2. GIS & Map Visualization (Level-of-Detail Strategy)

To avoid visual clutter when displaying multiple geographic layers (e.g., Parishes, Sectors, Risk Polygons, Flooded Streets):

### Zoom-Based Layer Visibility (LOD)
| Zoom Level | Target Granularity | Visible Features | Visual Treatment |
|---|---|---|---|
| **Zoom 10 – 12** | **Parroquias / Cantón** | Parroquias urbanas/rurales (polígonos agrupados) | Coropleta suave con relleno transparente (opacidad 0.25) |
| **Zoom 13 – 14** | **Sectores / Zonas de Riesgo** | Zonas de riesgo del modelo, sectores SeguraEP, eventos SGR | Polígonos con bordes definidos, etiquetas de sectores activas |
| **Zoom 15+** | **Micro-Barrial / Callejero** | Vías inundables, zonas seguras, puntos de albergue, ruta de evacuación OSRM | Íconos interactivos detallados, trazado de calles en rojo/verde |

### Layer Clutter Prevention Rules
1. **Dynamic Hover Highlighting**: Keep fill opacities low (`0.2 – 0.35`) and increase stroke width on `mousemove` / `mouseenter`.
2. **Accordion Layer Control**: Group map checkboxes into collapsible semantic categories:
   - *Límites Administrativos* (Parroquias/Cantones)
   - *Amenaza Hídrica & Riesgo* (Interpolación Lluvia IDW, Zonas de Riesgo)
   - *Infraestructura y Respuesta* (Vías Inundables, Zonas Seguras SeguraEP)
3. **Interactive Search / Spatial Jump**: Provide a dropdown search ("Ir a Barrio / Parroquia") that executes `map.flyTo()` rather than permanently displaying dozens of text labels.

---

## 3. Color Palette & Status Indicators

### Palette Tokens (Dark Glassmorphism Theme)
- **Background Base**: `#0f172a` (Slate 900)
- **Surface Panels**: `rgba(15, 23, 42, 0.85)` with `backdrop-filter: blur(12px)` and `border: 1px solid rgba(255, 255, 255, 0.1)`
- **Text Primary**: `#f8fafc` (Slate 50)
- **Text Secondary**: `#94a3b8` (Slate 400)

### Severity / Status Color System
- **Crítico / Alto**: `#ef4444` (Red 500) | `rgba(239, 68, 68, 0.2)`
- **Medio / Alerta**: `#facc15` (Yellow 400) | `rgba(250, 204, 21, 0.2)`
- **Bajo / Seguro**: `#4ade80` (Green 400) | `rgba(74, 222, 128, 0.2)`
- **Marino / Hídrico**: `#38bdf8` (Sky 400) & `#60a5fa` (Blue 400)

---

## 4. Multi-Factor Popups & Tooltips

Popups must justify data points rather than presenting isolated numbers:
- **Headline Status**: Title + Color Badge (`Alto / Crítico`, `Medio`, `Bajo`).
- **Métricas Clave**: Grid de 2 columnas con Altitud Terreno vs. Nivel de Marea/Lluvia.
- **Argumentación del Riesgo**: Lista explícita de factores contribuyentes (Cota topográfica + Taponamiento estuarine por pleamar + Escorrentía por lluvia).
- **Call to Action**: Botón prominente de respuesta (ej. *Trazar Ruta de Evacuación*).

---

## 5. UI Micro-Interactions
- Smooth transitions on hover (`transition: all 0.2s ease`).
- Collapsible sidebar toggle for focused map inspection.
- Active states on view toggle pills (`.active` class with glowing accent border).
