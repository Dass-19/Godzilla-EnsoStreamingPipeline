// ==========================================
// CLIENTE API DE SERVICIOS
// ==========================================

import { CONFIG } from '../config.js';

export async function fetchEnsoEstado() {
    const res = await fetch(CONFIG.API_BASE + 'enso/estado');
    if (!res.ok) throw new Error("Error consultando estado ENSO");
    return await res.json();
}

export async function fetchMacroIndexes() {
    const res = await fetch(CONFIG.DATA_BASE + 'enso_indexes.json');
    if (!res.ok) throw new Error("Error consultando índices macro");
    return await res.json();
}

export async function fetchOpenMeteoData() {
    const res = await fetch(CONFIG.DATA_BASE + 'open_meteo_data.json');
    if (!res.ok) throw new Error("Error consultando Open-Meteo");
    return await res.json();
}

export async function fetchInamhiData() {
    const res = await fetch(CONFIG.DATA_BASE + 'inamhi_data.json');
    if (!res.ok) throw new Error("Error consultando INAMHI");
    return await res.json();
}

export async function fetchMareasActual() {
    const res = await fetch(CONFIG.API_BASE + 'mareas/actual');
    if (!res.ok) throw new Error("Error consultando mareas");
    return await res.json();
}

export async function fetchEmbalseActual() {
    const res = await fetch(CONFIG.API_BASE + 'embalse/actual');
    if (!res.ok) throw new Error("Error consultando embalse");
    return await res.json();
}

export async function fetchRiesgoZonas() {
    const res = await fetch(CONFIG.API_BASE + 'riesgo/zonas');
    if (!res.ok) throw new Error("Error consultando riesgo por zonas");
    return await res.json();
}

export async function fetchHistoricoZona(zonaId) {
    const res = await fetch(`${CONFIG.API_BASE}riesgo/zonas/${encodeURIComponent(zonaId)}/historico`);
    if (!res.ok) return [];
    return await res.json();
}

export async function fetchSimulacion(rain, tide, caudal = 500, suelo = 0, nino12 = 0) {
    const res = await fetch(`${CONFIG.API_BASE}escenario/simular?precip_24h_mm=${rain}&altura_marea_m=${tide}&caudal_rio_m3s=${caudal}&saturacion_antecedente_mm=${suelo}&anomalia_nino12_c=${nino12}`);
    if (!res.ok) throw new Error("Error en simulación");
    return await res.json();
}

export async function fetchPronosticoRiesgo(horizonteH = 24) {
    const res = await fetch(`${CONFIG.API_BASE}riesgo/pronostico?horizonte_h=${horizonteH}`);
    if (!res.ok) throw new Error("Error en pronóstico de riesgo");
    return await res.json();
}

export async function fetchClimaPunto(lat, lon) {
    const res = await fetch(`${CONFIG.API_BASE}clima/punto?lat=${lat}&lon=${lon}`);
    if (!res.ok) throw new Error("Error consultando clima del punto");
    return await res.json();
}

export async function fetchOpenMeteoHist(lat, lon) {
    const url = `${CONFIG.OPEN_METEO_BASE}?latitude=${lat}&longitude=${lon}&hourly=temperature_2m&past_days=7&forecast_days=1`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("Error consultando histórico Open-Meteo");
    return await res.json();
}

export async function fetchEvacuationRoute(startLngLat, endLngLat) {
    const url = `${CONFIG.OSRM_BASE}${startLngLat.lng},${startLngLat.lat};${endLngLat[0]},${endLngLat[1]}?overview=full&geometries=geojson`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("Error consultando ruta OSRM");
    return await res.json();
}
