---
name: frontend-design
description: 'Use this skill when designing or implementing frontend UI components, dashboards, map layers/popups, or new sidebar cards for frontend/. Covers the verified color palette, the dashboard-sidebar/map-canvas layout, the no-build-step ES module convention, and the mandatory cache-busting rule. Trigger phrases: "design a dashboard", "improve UI layout", "frontend design", "map visual hierarchy", "component structure", "dashboard UX".'
---

# Frontend & Dashboard Design System

## Overview
`frontend/` is plain HTML/CSS/JS — **no build step, no package manager**. MapLibre GL, Chart.js and Turf
come from CDN with pinned versions and SRI `integrity` hashes. It's served as static files by the API
itself at `/dashboard` (the API root `/` does not serve it). `CONFIG` in
[js/config.js](../../../frontend/js/config.js) holds shared constants (`API_BASE: "/api/"`, map centers,
`REFRESH_RATE_MS`) and DOM-safe helpers (`setText`, `spanTexto`) — third-party data goes through those
(`textContent`/`createElement`), **never interpolated into `innerHTML`**.

---

## 1. Layout, as it actually exists in `index.html`

- **`#view-toggle-pill`**: global view switch (`🌍 Vista Regional` / `🏙️ Vista Local`) plus, since the
  parroquia-focus feature, a `<select id="select-parroquia">` to fly the map to a specific parish/sector.
- **Map canvas**: MapLibre fills the rest of the viewport, managed by
  [js/map/map-manager.js](../../../frontend/js/map/map-manager.js).
- **`#dashboard-sidebar`**: scrollable column of `<section class="card">` blocks — one per topic
  (`sst-card`, `macro-card`, `meteo-card`, `inamhi-card`, `embalse-card`, `pronostico-card`,
  `hidrologia-card`, `simulador-card`, …). Adding a new metric group means adding a new `.card` section
  here plus the JS that populates it, following the existing cards as the template — don't invent a new
  layout primitive for one more metric.
- **Floating layer controls**: translucent panels at the map corners using `backdrop-filter: blur(...)`
  (verified in `styles.css`: `blur(10px)`, `blur(12px)`, `blur(16px)` depending on panel prominence).

## 2. Verified color tokens (from `styles.css` and the JS that sets inline colors)

- **Background**: `#0f172a`. **Text primary**: `#f8fafc`. **Text secondary**: `#94a3b8`.
- **Risk/severity**: alto/crítico `#ef4444` (with `#dc2626` for a darker/gradient variant), medio
  `#facc15`, bajo/seguro `#4ade80`.
- **Hydro/marine accents**: `#38bdf8` (sky), `#60a5fa` (blue), `#818cf8` (indigo, used in the header
  gradient with `#38bdf8`).

These are grep-verified against `styles.css` and `frontend/js/**/*.js` inline styles — reuse them for any
new card or layer rather than picking new hex values, so the dashboard reads as one system.

## 3. Map layers

Layers are added in [map-manager.js](../../../frontend/js/map/map-manager.js) with MapLibre's
`map.addLayer({...})`; risk/hazard fills use the color tokens above, often via `interpolate` expressions
(e.g. a fill-color ramp keyed on a numeric field with stops at `40 → '#facc15'`, `100 → '#ef4444'`).
Popups are built in [map/map-popups.js](../../../frontend/js/map/map-popups.js) and follow a consistent
shape: colored headline status, a small metrics grid, then a call-to-action button (e.g. *Trazar Ruta de
Evacuación*) — match that shape for a new popup rather than free-forming one.

**Layer-density guidance** (recommendation, not yet fully encoded as automatic zoom-based show/hide in
the code): group related toggles under one accordion/category in the layer-control menu (the existing
`#toggle-*` checkboxes list in `index.html` already does this informally — administrative boundaries,
hazard/risk, infrastructure/response); keep fill opacities low (`0.2–0.35`) and thicken strokes on
hover/`mousemove` rather than showing dense labels at every zoom level.

## 4. The ES module convention — and its one sharp edge

9 files under `js/` import each other with relative paths (`js/main.js` is the entry point, loaded from
`index.html` as `<script type="module" src="js/main.js?v=N">`). **Every one of those internal imports
must carry the same `?v=N` querystring as `main.js`** — the browser caches each imported URL separately,
so bumping only `main.js?v=` does not invalidate `dashboard.js`, `client.js`, etc. When you edit any file
under `js/`, bump `N` in `index.html`'s `main.js?v=` **and** in every `import ... from '....js?v=N'` line
across all 9 files in the same change. `styles.css?v=M` is a separate, independent counter. This was a
real, shipped bug once (edited modules silently stayed cached) — don't reintroduce it.

## 5. Key Files

- **Entry point**: [frontend/index.html](../../../frontend/index.html)
- **Shared config/DOM helpers**: [frontend/js/config.js](../../../frontend/js/config.js)
- **Map**: [frontend/js/map/map-manager.js](../../../frontend/js/map/map-manager.js),
  [frontend/js/map/map-popups.js](../../../frontend/js/map/map-popups.js)
- **Dashboard cards**: [frontend/js/dashboard.js](../../../frontend/js/dashboard.js)
- **Styles**: [frontend/styles.css](../../../frontend/styles.css)

## 6. Verification Checklist

- [ ] New third-party/user-influenced text goes through `setText`/`spanTexto`/`createElement`, never
      `innerHTML` interpolation.
- [ ] Colors reused from the verified palette above, not new hex values invented per-component.
- [ ] `main.js?v=` **and** every internal `import ... ?v=` bumped together after any `js/` edit.
- [ ] Manually open `/dashboard/` in a browser and exercise the changed feature — type checks don't
      substitute for seeing it render (this project has no frontend test suite).
