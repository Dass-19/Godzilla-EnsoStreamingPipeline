---
id: 20260927152005
type: skill-spec
status: evergreen
name: "frontend-design"
runtime: browser / es-modules
entrypoint: "frontend/index.html"
inputs:
  - name: component
    type: string
    description: "Componente visual o módulo JS a crear o modificar"
    required: false
outputs:
  format: "html / css / js (ES Modules)"
created: 2026-09-27
updated: 2026-09-27
---

# Skill: Frontend & Dashboard Design System

> **Propósito**: Guiar el diseño visual, componentes UI, mapas geoespaciales y módulos ES del frontend en [`frontend/`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/frontend/).

---

## 1. Principios de Diseño y Arquitectura

1. **Zero-Build Step**: Plain HTML5, CSS3 y ES Modules nativos sin pasos de compilación.
2. **Paleta de Colores Estandarizada**:
   - `Bajo / Seguro`: `#4ade80` / `#22c55e`
   - `Medio`: `#facc15` / `#eab308`
   - `Alto`: `#f97316`
   - `Crítico`: `#ef4444` / `#dc2626`
   - `Fondo / Paneles`: `#0f172a` / `#1e293b`
   - `Acentos Hidrológicos`: `#38bdf8` (sky), `#60a5fa` (blue)
3. **Regla Estricta de Cache-Busting**:
   - Todo import en `js/` debe llevar query string versionado (ej: `import { CONFIG } from './config.js?v=22';`).
   - Al editar cualquier archivo JS, incrementar simultáneamente la versión `?v=N` en `index.html` y en todos los imports internos.
4. **Seguridad en DOM**:
   - Todo dato dinámico debe pasar por `setText()`, `spanTexto()` o `createElement()`.
   - **Prohibido** interpolar cadenas de texto no sanitizadas dentro de `innerHTML`.

---

## 2. Checklist de Verificación
- [ ] No se usa `innerHTML` para inyectar datos de API.
- [ ] Colores reutilizados de la paleta canónica.
- [ ] Sincronización de `?v=N` en todos los archivos JS modificados.
- [ ] Verificación manual visual en el navegador en `http://localhost:8000/dashboard`.
