// ==========================================
// CONFIGURACIÓN CENTRALIZADA Y UTILIDADES DOM
// ==========================================

export const CONFIG = {
    API_BASE: "/api/",
    OSRM_BASE: "https://router.project-osrm.org/route/v1/driving/",
    OPEN_METEO_BASE: "https://api.open-meteo.com/v1/forecast",
    MAP_CENTER_REGIONAL: [-95.0, -1.5],
    MAP_CENTER_LOCAL: [-79.9, -2.18],
    REFRESH_RATE_MS: 5 * 60 * 1000 // 5 minutos
};

// Escribe texto plano en un nodo por ID, sin interpretar HTML.
export function setText(id, texto, color) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = texto;
    if (color) el.style.color = color;
}

// Crea un elemento <span> con texto y CSS opcional.
export function spanTexto(texto, css) {
    const span = document.createElement('span');
    span.textContent = String(texto);
    if (css) span.style.cssText = css;
    return span;
}

// Crea un contenedor estilizado para mensajes de datos vacíos.
export function mensajeVacio(texto) {
    const div = document.createElement('div');
    div.style.cssText = "text-align: center; color: #94a3b8; font-size: 12px; margin-top: 20px;";
    div.textContent = texto;
    return div;
}
