// ==========================================
// CONTROLADOR DEL DASHBOARD (DATOS EN TIEMPO REAL)
// ==========================================

import { setText, spanTexto, mensajeVacio } from './config.js';
import {
    fetchEnsoEstado,
    fetchMacroIndexes,
    fetchOpenMeteoData,
    fetchInamhiData,
    fetchMareasActual,
    fetchEmbalseActual,
    fetchRiesgoZonas,
    fetchCaudalGeoglows,
    fetchSgrEvents
} from './api/client.js';
import { map, isLayersLoaded } from './map/map-manager.js';
import { updateGlobalRiskGauge } from './components/charts.js';
import { getIsSimulating } from './ui/simulation.js';

export async function updateDashboard() {
    await Promise.all([
        updateEnsoData(),
        updateMacroIndexes(),
        updateOpenMeteoData(),
        updateInamhiData(),
        updateTideData(),
        updateEmbalseData(),
        updateHydroData(),
        updateSgrEventsData(),
        updateRiskZonesAndGauge()
    ]);
}

export async function updateEnsoData() {
    try {
        const data = await fetchEnsoEstado();
        const parsed = JSON.parse(data.json_str);
        const currentData = parsed.data[parsed.data.length - 1];
        const r = currentData.regions || {};
        const n34 = r.nino_3_4?.anomaly ?? 0;
        const n12 = r.nino_1_2?.anomaly ?? 0;
        const n3 = r.nino_3?.anomaly;
        const n4 = r.nino_4?.anomaly;

        window.noaaAnomalies = { n34, n12, n3: n3 ?? 0, n4: n4 ?? 0 };

        const getColor = anom => anom >= 1.5 ? '#dc2626' : (anom >= 0.5 ? '#f87171' : (anom >= -0.5 ? '#facc15' : '#60a5fa'));
        const getBgColor = anom => anom >= 1.5 ? 'rgba(220, 38, 38, 0.4)' : (anom >= 0.5 ? 'rgba(248, 113, 113, 0.4)' : (anom >= -0.5 ? 'rgba(250, 204, 21, 0.4)' : 'rgba(96, 165, 250, 0.4)'));
        const formatAnom = anom => `${anom > 0 ? '+' : ''}${anom.toFixed(2)} °C`;

        const val34 = document.getElementById('val-nino34');
        if (val34) val34.innerText = formatAnom(n34);
        const block34 = document.getElementById('block-nino34');
        if (block34) block34.style.background = getBgColor(n34);

        const val12 = document.getElementById('val-nino12');
        if (val12) val12.innerText = formatAnom(n12);
        const block12 = document.getElementById('block-nino12');
        if (block12) block12.style.background = getBgColor(n12);

        if (n3 !== undefined) {
            const val3 = document.getElementById('val-nino3');
            if (val3) val3.innerText = formatAnom(n3);
            const block3 = document.getElementById('block-nino3');
            if (block3) block3.style.background = getBgColor(n3);
        }
        if (n4 !== undefined) {
            const val4 = document.getElementById('val-nino4');
            if (val4) val4.innerText = formatAnom(n4);
            const block4 = document.getElementById('block-nino4');
            if (block4) block4.style.background = getBgColor(n4);
        }

        if (map && isLayersLoaded()) {
            map.setPaintProperty('nino34-layer', 'fill-color', getColor(n34));
            map.setPaintProperty('nino12-layer', 'fill-color', getColor(n12));
            if (n3 !== undefined) map.setPaintProperty('nino3-layer', 'fill-color', getColor(n3));
            if (n4 !== undefined) map.setPaintProperty('nino4-layer', 'fill-color', getColor(n4));

            const updateLabel = (id, labelName, anom, coords) => {
                const src = map.getSource(id);
                if (src) {
                    src.setData({ type: 'Feature', properties: { label: `${labelName}\n${formatAnom(anom)}` }, geometry: { type: 'Polygon', coordinates: [coords] } });
                }
            };
            updateLabel('nino34', 'Niño 3.4', n34, [[-170, -5], [-120, -5], [-120, 5], [-170, 5], [-170, -5]]);
            updateLabel('nino12', 'Niño 1+2', n12, [[-90, -10], [-80, -10], [-80, 0], [-90, 0], [-90, -10]]);
            if (n3 !== undefined) updateLabel('nino3', 'Niño 3', n3, [[-150, -5], [-90, -5], [-90, 5], [-150, 5], [-150, -5]]);
            if (n4 !== undefined) updateLabel('nino4', 'Niño 4', n4, [[160, -5], [210, -5], [210, 5], [160, 5], [160, -5]]);
        }
    } catch (e) { console.error("Error NOAA:", e); }
}

export async function updateMacroIndexes() {
    try {
        const json = await fetchMacroIndexes();
        if (json.data && json.data.length > 0) {
            const data = json.data[0];
            setText('val-soi', `${data.soi_proxy_diff.toFixed(2)} hPa`);
            const valDarwin = document.getElementById('val-darwin');
            if (valDarwin) valDarwin.innerHTML = `${data.darwin_mslp_hpa.toFixed(1)}<br>hPa`;
            const valTahiti = document.getElementById('val-tahiti');
            if (valTahiti) valTahiti.innerHTML = `${data.tahiti_mslp_hpa.toFixed(1)}<br>hPa`;
            setText('val-enso-status', data.enso_status.toUpperCase());
        }
    } catch (e) { console.error("Error Macro Indexes:", e); }
}

export async function updateOpenMeteoData() {
    try {
        const json = await fetchOpenMeteoData();
        if (json.data && json.data.length > 0) {
            const data = json.data[json.data.length - 1];
            window.currentPrecipSum = data.precipitation_sum_mm || 0;
            setText('val-meteo-rain', `${data.precipitation_sum_mm.toFixed(1)} mm`);
            setText('val-meteo-wind', `${data.max_wind_speed_ms.toFixed(1)} m/s`);
            setText('val-gpm-rain', `0.0 mm/día`);
        }
    } catch (e) { console.error("Error Open Meteo:", e); }
}

export async function updateInamhiData() {
    try {
        const json = await fetchInamhiData();
        const listContainer = document.getElementById('inamhi-list');
        if (!listContainer) return;
        listContainer.textContent = '';

        const estaciones = json?.estaciones?.estaciones;
        if (!Array.isArray(estaciones)) {
            listContainer.appendChild(mensajeVacio("Sin catálogo de estaciones disponible."));
            return;
        }

        const cantonesInteres = ["GUAYAQUIL", "DAULE", "DURAN", "SAMBORONDON"];
        const activas = estaciones.filter(e =>
            e.estado_transmision === "TRANSMITIENDO" &&
            cantonesInteres.includes(e.canton)
        );

        if (activas.length === 0) {
            listContainer.appendChild(mensajeVacio("No hay estaciones transmitiendo en esta zona."));
            return;
        }

        activas.forEach(est => {
            const el = document.createElement('div');
            el.style.borderBottom = "1px solid rgba(255,255,255,0.1)";
            el.style.padding = "8px 0";
            el.style.fontSize = "11px";

            const categoria = String(est.categoria ?? "");
            const catColor = categoria.includes("METEORO") ? "#60a5fa" : "#34d399";

            const filaSuperior = document.createElement('div');
            filaSuperior.style.cssText = "display: flex; justify-content: space-between; margin-bottom: 2px;";
            filaSuperior.appendChild(spanTexto(est.punto_obs ?? "--", "font-weight: bold; color: #e2e8f0;"));
            filaSuperior.appendChild(spanTexto(`${est.canton ?? "--"} | Alt: ${est.altitud ?? "--"}m`, "color: #94a3b8;"));

            const filaInferior = document.createElement('div');
            filaInferior.style.cssText = "display: flex; justify-content: space-between;";
            filaInferior.appendChild(spanTexto(categoria || "--", `color: ${catColor}; font-weight: 600;`));
            filaInferior.appendChild(spanTexto("● Transmitiendo", "color: #4ade80;"));

            el.appendChild(filaSuperior);
            el.appendChild(filaInferior);
            listContainer.appendChild(el);
        });

        if (json.pronostico_diario && json.pronostico_diario.pronostico) {
            const guayaquil = json.pronostico_diario.pronostico.find(p => p.locality_name === "Guayaquil");
            if (guayaquil) {
                setText('val-inamhi-temp', `${guayaquil.min_temperature} / ${guayaquil.max_temperature} °C`);

                let uvColor = '#4ade80';
                if (guayaquil.uv_radiation >= 8) uvColor = '#ef4444';
                else if (guayaquil.uv_radiation >= 5) uvColor = '#facc15';
                setText('val-inamhi-uv', guayaquil.uv_radiation ?? '--', uvColor);

                const lluviaEl = document.getElementById('val-inamhi-lluvia');
                if (lluviaEl) {
                    lluviaEl.innerText = guayaquil.rain ? "Sí 🌧️" : "No ☀️";
                    lluviaEl.style.color = guayaquil.rain ? "#60a5fa" : "#4ade80";
                }

                const tarde = guayaquil.forecast.find(f => f.period_name === "Tarde") || guayaquil.forecast[0];
                if (tarde) {
                    setText('val-inamhi-cond', tarde.condition_name);
                    const iconEl = document.getElementById('val-inamhi-icon');
                    if (iconEl && tarde.condition_icon_url) {
                        iconEl.src = tarde.condition_icon_url;
                        iconEl.style.display = 'block';
                    }
                }
            }
        }
    } catch (e) { console.error("Error INAMHI:", e); }
}

export async function updateTideData() {
    try {
        const data = await fetchMareasActual();
        const parsed = JSON.parse(data.json_str);
        const altura = parsed.altura_marea_m ?? 0;
        window.currentTideHeight = altura;
        setText('val-surge', `${altura > 0 ? '+' : ''}${altura.toFixed(2)} m`);
        const descEl = document.getElementById('val-surge-desc');
        if (descEl) {
            if (altura > 2.5) {
                descEl.innerText = "⚠️ Marea Alta";
                descEl.style.color = "#f87171";
            } else {
                descEl.innerText = "✓ Marea normal";
                descEl.style.color = "#4ade80";
            }
        }
        setText('val-pleamar', `${altura.toFixed(2)} m`);
    } catch (e) { console.error("Error Mareas:", e); }
}

export async function updateEmbalseData() {
    try {
        const data = await fetchEmbalseActual();
        const parsed = JSON.parse(data.json_str);
        const cota = parsed.nivel_msnm ?? null;
        window.currentEmbalseCota = cota;
        setText('val-cota-embalse', cota != null ? `${cota} msnm` : 'sin dato');
        setText('val-nivel-max-embalse',
            parsed.nivel_maximo_msnm != null ? `${parsed.nivel_maximo_msnm} msnm` : 'no informado');

        if (cota != null && cota > 80) {
            setText('embalse-alert', "⚠️ Nivel Crítico. Posible desfogue.", "#f87171");
        } else if (cota != null) {
            setText('embalse-alert', "✓ Nivel Operativo Normal", "#4ade80");
        } else {
            setText('embalse-alert', "Sin boletín reciente de CELEC", "#94a3b8");
        }
    } catch (e) {
        console.error("Error Embalse:", e);
        setText('embalse-alert', "Error consultando el embalse", "#f87171");
    }
}

export async function updateRiskZonesAndGauge() {
    if (getIsSimulating()) return;
    try {
        const data = await fetchRiesgoZonas();
        let totalRiesgo = 0;
        const features = [];
        if (data.zonas && data.zonas.length > 0) {
            data.zonas.forEach(z => {
                z.indice_riesgo = (z.indice_riesgo || 0) * 100;
                totalRiesgo += z.indice_riesgo;
                if (z.lon_centroide && z.lat_centroide) {
                    if (typeof turf !== 'undefined') {
                        const pt = turf.point([z.lon_centroide, z.lat_centroide]);
                        const buffered = turf.buffer(pt, 1.5, { units: 'kilometers' });
                        buffered.properties = z;
                        features.push(buffered);
                    } else {
                        features.push({
                            type: 'Feature',
                            geometry: { type: 'Point', coordinates: [z.lon_centroide, z.lat_centroide] },
                            properties: z
                        });
                    }
                }
            });
            const avgRiesgo = totalRiesgo / data.zonas.length;
            updateGlobalRiskGauge(avgRiesgo);

            if (map && map.getSource('zonas-riesgo')) {
                map.getSource('zonas-riesgo').setData({ type: 'FeatureCollection', features: features });
            }
        }
    } catch (e) { console.error("Error Riesgo Zonas:", e); }
}

export async function updateHydroData() {
    try {
        const json = await fetchCaudalGeoglows();
        let caudalVal = 400.0;
        if (json.data && json.data.length > 0) {
            const last = json.data[json.data.length - 1];
            caudalVal = last.caudal_m3s || last.q_m3s || 400.0;
        } else if (json.caudal_m3s) {
            caudalVal = json.caudal_m3s;
        }

        setText('val-caudal-rio', `${caudalVal.toFixed(0)} m³/s`);
        const estadoEl = document.getElementById('val-caudal-estado');
        if (estadoEl) {
            if (caudalVal > 1800) {
                estadoEl.innerText = "⚠️ Crecida Crítica";
                estadoEl.style.color = "#ef4444";
            } else if (caudalVal > 1000) {
                estadoEl.innerText = "⚡ Caudal Elevado";
                estadoEl.style.color = "#facc15";
            } else {
                estadoEl.innerText = "✓ Caudal Normal";
                estadoEl.style.color = "#4ade80";
            }
        }

        const tideHeight = window.currentTideHeight ?? 2.8;
        setText('val-marea-ioc', `${tideHeight.toFixed(2)} m`);
        const diffAnom = tideHeight - 2.0;
        const anomEl = document.getElementById('val-anomalia-marea');
        if (anomEl) {
            anomalia_marea.innerText = `${diffAnom >= 0 ? '+' : ''}${diffAnom.toFixed(2)}m vs armónico`;
            anomalia_marea.style.color = diffAnom > 0.5 ? "#f87171" : "#4ade80";
        }
    } catch (e) {
        console.error("Error Hydro Data:", e);
        setText('val-caudal-rio', '400 m³/s');
    }
}

export async function updateSgrEventsData() {
    try {
        const json = await fetchSgrEvents();
        const listContainer = document.getElementById('sgr-incidencias-list');
        if (!listContainer) return;

        let features = [];
        if (json.features) features = json.features;
        else if (json.data) features = json.data;

        setText('val-sgr-count', `${features.length}`);

        let totalAfectados = 0;
        listContainer.innerHTML = '';

        if (features.length === 0) {
            listContainer.appendChild(mensajeVacio("No hay incidentes reportados hoy."));
            setText('val-sgr-afectados', '0 pers.');
            return;
        }

        features.slice(0, 5).forEach(f => {
            const p = f.properties || f;
            const afectados = parseInt(p.personasafectadasdirectamente || p.afectados || 0);
            totalAfectados += afectados;

            const el = document.createElement('div');
            el.className = 'sgr-incident-item';

            const titulo = spanTexto(p.evento || p.canton || 'Lluvia / Inundación', 'font-weight: bold; color: #f87171; display: block;');
            const desc = spanTexto(`${p.canton || 'Guayas'} | ${p.fechadelevento || 'Reciente'}`, 'color: #94a3b8; font-size: 10px;');

            el.appendChild(titulo);
            el.appendChild(desc);
            listContainer.appendChild(el);
        });

        setText('val-sgr-afectados', `${totalAfectados} pers.`);
    } catch (e) {
        console.error("Error SGR Events:", e);
        setText('val-sgr-count', '0');
        setText('val-sgr-afectados', '0 pers.');
    }
}
