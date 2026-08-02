// ==========================================
// CLIENTE API DE SERVICIOS
// ==========================================

import { CONFIG } from '../config.js';

/**
 * Desempaqueta y valida respuestas con envoltura RespuestaAPI { status, data, error, meta }.
 */
async function parseResponse(res, defaultErrorMsg) {
    let body;
    try {
        body = await res.json();
    } catch {
        if (!res.ok) throw new Error(defaultErrorMsg);
        return null;
    }

    if (body && typeof body === 'object' && 'status' in body && 'data' in body) {
        if (body.status === 'error' || !res.ok) {
            const mensaje = body.error?.mensaje || body.detail || defaultErrorMsg;
            throw new Error(mensaje);
        }
        return body.data;
    }

    if (!res.ok) throw new Error(defaultErrorMsg);
    return body;
}

export async function fetchEnsoEstado() {
    const res = await fetch(CONFIG.API_BASE + 'enso/estado');
    return await parseResponse(res, "Error consultando estado ENSO");
}

export async function fetchMacroIndexes() {
    const res = await fetch(CONFIG.API_BASE + 'enso/indices');
    return await parseResponse(res, "Error consultando índices macro");
}

export async function fetchOpenMeteoData() {
    const res = await fetch(CONFIG.API_BASE + 'clima/open-meteo');
    return await parseResponse(res, "Error consultando Open-Meteo");
}

export async function fetchInamhiData() {
    const res = await fetch(CONFIG.API_BASE + 'clima/inamhi');
    return await parseResponse(res, "Error consultando INAMHI");
}

export async function fetchMareasActual() {
    const res = await fetch(CONFIG.API_BASE + 'mareas/actual');
    return await parseResponse(res, "Error consultando mareas");
}

export async function fetchEmbalseActual() {
    const res = await fetch(CONFIG.API_BASE + 'embalse/actual');
    return await parseResponse(res, "Error consultando embalse");
}

export async function fetchRiesgoZonas() {
    const res = await fetch(CONFIG.API_BASE + 'riesgo/zonas');
    return await parseResponse(res, "Error consultando riesgo por zonas");
}

export async function fetchHistoricoZona(zonaId) {
    const res = await fetch(`${CONFIG.API_BASE}riesgo/zonas/${encodeURIComponent(zonaId)}/historico`);
    if (!res.ok) return [];
    try {
        return await parseResponse(res, "Error consultando histórico de zona");
    } catch {
        return [];
    }
}

export async function fetchSimulacion(rain, tide, caudal = 500, suelo = 0, nino12 = 0) {
    const res = await fetch(`${CONFIG.API_BASE}escenario/simular?precip_24h_mm=${rain}&altura_marea_m=${tide}&caudal_rio_m3s=${caudal}&saturacion_antecedente_mm=${suelo}&anomalia_nino12_c=${nino12}`);
    return await parseResponse(res, "Error en simulación");
}

export async function fetchPronosticoRiesgo(horizonteH = 24) {
    const res = await fetch(`${CONFIG.API_BASE}riesgo/pronostico?horizonte_h=${horizonteH}`);
    return await parseResponse(res, "Error en pronóstico de riesgo");
}

export async function fetchClimaPunto(lat, lon) {
    const res = await fetch(`${CONFIG.API_BASE}clima/punto?lat=${lat}&lon=${lon}`);
    return await parseResponse(res, "Error consultando clima del punto");
}

export async function fetchOpenMeteoHist(lat, lon) {
    const url = `${CONFIG.OPEN_METEO_BASE}?latitude=${lat}&longitude=${lon}&hourly=temperature_2m&past_days=7&forecast_days=1`;
    const res = await fetch(url);
    return await parseResponse(res, "Error consultando histórico Open-Meteo");
}

export async function fetchEvacuationRoute(startLngLat, endLngLat) {
    const url = `${CONFIG.OSRM_BASE}${startLngLat.lng},${startLngLat.lat};${endLngLat[0]},${endLngLat[1]}?overview=full&geometries=geojson`;
    const res = await fetch(url);
    return await parseResponse(res, "Error consultando ruta OSRM");
}

export async function fetchCaudalGeoglows() {
    const res = await fetch(CONFIG.API_BASE + 'hidrologia/geoglows');
    return await parseResponse(res, "Error consultando caudal GEOGLOWS");
}

export async function fetchSgrEvents() {
    const res = await fetch(CONFIG.API_BASE + 'eventos/sgr');
    return await parseResponse(res, "Error consultando eventos SGR");
}

export async function fetchCapasParroquias() {
    const res = await fetch(CONFIG.API_BASE + 'capas/parroquias');
    return await parseResponse(res, "Error consultando parroquias");
}

export async function fetchCapasSectores() {
    const res = await fetch(CONFIG.API_BASE + 'capas/sectores');
    return await parseResponse(res, "Error consultando sectores");
}
