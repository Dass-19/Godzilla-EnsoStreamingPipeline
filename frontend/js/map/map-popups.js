// ==========================================
// INTERACCIONES Y POPUPS DEL MAPA
// ==========================================

import { map, getSafeZonesGeoJSON } from './map-manager.js?v=20';
import { fetchClimaPunto, fetchOpenMeteoHist, fetchEvacuationRoute } from '../api/client.js?v=20';
import { createPopupChart, showHistoryChart } from '../components/charts.js?v=20';
import { updateParroquiaEventsPanel } from '../ui/controls.js?v=20';

let currentPopup = null;

export function getCurrentPopup() {
    return currentPopup;
}

export function setCurrentPopup(popup) {
    if (currentPopup) currentPopup.remove();
    currentPopup = popup;
}

function getDistanceFromLatLonInKm(lat1, lon1, lat2, lon2) {
    const R = 6371;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return R * (2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a)));
}

export async function calculateEvacuationRoute(startLngLat) {
    let endLngLat = [-79.88, -2.175]; // Fallback

    try {
        const safeZones = getSafeZonesGeoJSON();
        if (safeZones && safeZones.features) {
            let minDist = Infinity;
            safeZones.features.forEach(f => {
                let lng, lat;
                if (f.geometry.type === 'Point') {
                    lng = f.geometry.coordinates[0];
                    lat = f.geometry.coordinates[1];
                } else if (f.geometry.type === 'Polygon' || f.geometry.type === 'MultiPolygon') {
                    const coords = f.geometry.type === 'Polygon' ? f.geometry.coordinates[0][0] : f.geometry.coordinates[0][0][0];
                    lng = coords[0]; lat = coords[1];
                }
                if (lng && lat) {
                    const dist = getDistanceFromLatLonInKm(startLngLat.lat, startLngLat.lng, lat, lng);
                    if (dist < minDist) {
                        minDist = dist;
                        endLngLat = [lng, lat];
                    }
                }
            });
        }
    } catch (e) {
        console.error("Error buscando zonas seguras:", e);
    }

    try {
        const data = await fetchEvacuationRoute(startLngLat, endLngLat);
        if (data.routes && data.routes.length > 0) {
            const routeGeoJSON = data.routes[0].geometry;
            if (map.getSource('route')) {
                map.getSource('route').setData({
                    type: 'Feature', properties: {}, geometry: routeGeoJSON
                });
            }
            if (currentPopup) currentPopup.remove();

            new maplibregl.Marker({ color: '#4ade80' })
                .setLngLat(endLngLat)
                .setPopup(new maplibregl.Popup().setHTML("<b>Zona Segura</b><br>Albergue sugerido"))
                .addTo(map);
        } else {
            alert("OSRM: No se encontró ruta terrestre.");
        }
    } catch (err) {
        console.error("OSRM Routing Error:", err);
        alert("Error al conectar con OSRM.");
    }
}

export function initMapInteractions() {
    if (!map) return;

    // Hover sobre el mapa
    map.on('mousemove', (e) => {
        const isLocal = !document.getElementById('local-layer-control').classList.contains('hidden');
        if (isLocal) {
            const elevation = map.queryTerrainElevation(e.lngLat);
            const elSpan = document.getElementById('hover-elevation');
            if (elSpan) {
                if (elevation !== null) {
                    const val = Math.max(0, elevation);
                    elSpan.innerText = `${val.toFixed(1)} m s.n.m.`;
                    elSpan.style.color = val < 2 ? '#f87171' : (val < 5 ? '#facc15' : '#4ade80');
                } else {
                    elSpan.innerText = `-- m s.n.m.`;
                    elSpan.style.color = '#fff';
                }
            }
        }
    });

    // Clic en el mapa
    map.on('click', async (e) => {
        const isLocal = !document.getElementById('local-layer-control').classList.contains('hidden');

        // Ignorar si el click fue sobre un popup de evento o zona segura
        const eventLayers = ['sgr-events-layer', 'seguraep-zonasegura-layer', 'zonas-riesgo-layer'];
        const activeLayers = eventLayers.filter(l => map.getLayer(l) && map.getLayoutProperty(l, 'visibility') === 'visible');
        if (activeLayers.length > 0) {
            const features = map.queryRenderedFeatures(e.point, { layers: activeLayers });
            if (features.length > 0) return;
        }

        if (isLocal) {
            const elevation = map.queryTerrainElevation(e.lngLat);
            if (elevation === null) return;

            const val = Math.max(0, elevation);
            const tide = window.currentTideHeight ?? 2.8;
            const precip = window.currentPrecipSum ?? 0;
            const nino12 = window.noaaAnomalies?.n12 ?? 0;

            let riskLevel = "Bajo";
            let riskColor = "#4ade80";
            let riskBg = "rgba(74, 222, 128, 0.15)";
            let altColor = "#4ade80";

            if (val < 2.0 || (val < 4.0 && tide >= 2.5)) {
                riskLevel = "Alto / Crítico";
                riskColor = "#ef4444";
                riskBg = "rgba(239, 68, 68, 0.15)";
                altColor = "#ef4444";
            } else if (val < 5.0) {
                riskLevel = "Medio";
                riskColor = "#facc15";
                riskBg = "rgba(250, 204, 21, 0.15)";
                altColor = "#facc15";
            }

            const tideDesc = tide >= 2.5 ? "Pleamar / Alta" : "Normal";
            const tideColor = tide >= 2.5 ? "#ef4444" : "#4ade80";

            // Construcción dinámica de argumentos de riesgo
            const factores = [];

            if (val <= 2.0) {
                factores.push(`<b>Cota Crítica (≤2.0m):</b> Depresión plana propensa a empozamiento sin pendiente de desagüe natural.`);
            } else if (val <= 5.0) {
                factores.push(`<b>Cota Baja (2.0m–5.0m):</b> Susceptible a anegamiento si la lluvia coincide con marea alta.`);
            } else {
                factores.push(`<b>Elevación Adecuada (>5.0m):</b> Facilita la escorrentía por gravedad.`);
            }

            if (tide >= 2.5) {
                factores.push(`<b>Taponamiento por Pleamar (+${tide.toFixed(2)}m):</b> El nivel del río bloquea la descarga de la red de alcantarillado.`);
            } else {
                factores.push(`<b>Marea Moderada (+${tide.toFixed(2)}m):</b> Colectores pluviales operan sin contra-presión estuarine.`);
            }

            if (precip > 0) {
                factores.push(`<b>Precipitación Registrada (${precip.toFixed(1)}mm):</b> Volumen activo de agua sobre la cuenca urbana.`);
            }

            if (nino12 >= 1.5) {
                factores.push(`<b>Amplificación El Niño (+${nino12.toFixed(1)}°C):</b> Calentamiento costero incrementa la intensidad de tormentas.`);
            }

            const factoresHtml = factores.map(f => `<li style="margin-bottom: 4px;">${f}</li>`).join('');

            const popupHtml = `
                <div style="color: #1e293b; font-family: Inter, system-ui, sans-serif; width: 270px; padding: 2px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; margin-bottom: 8px;">
                        <h4 style="margin: 0; font-size: 13px; font-weight: 700; color: #0f172a;">Análisis de Vulnerabilidad</h4>
                        <span style="background: ${riskBg}; color: ${riskColor}; font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 10px; border: 1px solid ${riskColor};">${riskLevel}</span>
                    </div>

                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 10px; font-size: 11px;">
                        <div style="background: #f8fafc; padding: 6px; border-radius: 6px; border: 1px solid #e2e8f0;">
                            <span style="color: #64748b; display: block; font-size: 9px; font-weight: 600;">ALTITUD TERRENO</span>
                            <b style="color: ${altColor}; font-size: 12px;">${val.toFixed(1)} m s.n.m.</b>
                        </div>
                        <div style="background: #f8fafc; padding: 6px; border-radius: 6px; border: 1px solid #e2e8f0;">
                            <span style="color: #64748b; display: block; font-size: 9px; font-weight: 600;">NIVEL MAREA RÍO</span>
                            <b style="color: ${tideColor}; font-size: 12px;">${tide.toFixed(2)} m (${tideDesc})</b>
                        </div>
                    </div>

                    <div style="margin-bottom: 10px;">
                        <span style="font-size: 10px; font-weight: 700; color: #475569; display: block; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.4px;">Argumentación del Riesgo:</span>
                        <ul style="margin: 0; padding-left: 14px; font-size: 10.5px; color: #334155; line-height: 1.35;">
                            ${factoresHtml}
                        </ul>
                    </div>

                    ${val < 5.0 ? `
                        <button id="btn-evac" style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); color: white; border: none; padding: 8px 12px; border-radius: 6px; cursor: pointer; width: 100%; font-size: 11px; font-weight: 700; display: flex; align-items: center; justify-content: center; gap: 6px; box-shadow: 0 2px 4px rgba(239, 68, 68, 0.25); transition: all 0.2s;">
                            <span>🚨</span> Trazar Ruta a Zona Segura
                        </button>
                    ` : `
                        <div style="background: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; padding: 6px; border-radius: 6px; font-size: 10px; text-align: center; font-weight: 600;">
                            ✓ Zona segura por elevación (Sin evacuación)
                        </div>
                    `}
                </div>
            `;

            setCurrentPopup(new maplibregl.Popup({ maxWidth: '300px' }).setLngLat(e.lngLat).setHTML(popupHtml).addTo(map));

            setTimeout(() => {
                const btnEvac = document.getElementById('btn-evac');
                if (btnEvac) {
                    btnEvac.addEventListener('click', () => {
                        btnEvac.innerText = "Calculando ruta...";
                        calculateEvacuationRoute(e.lngLat);
                    });
                }
            }, 100);
        } else {
            // Vista regional: info marina/climática
            const lat = e.lngLat.lat;
            const lon = e.lngLat.lng;

            setCurrentPopup(new maplibregl.Popup()
                .setLngLat(e.lngLat)
                .setHTML(`<div style="color: #1e293b; font-family: Inter; font-size: 12px; padding: 5px;">Consultando datos marinos...</div>`)
                .addTo(map));

            try {
                const data = await fetchClimaPunto(lat, lon);
                const histData = await fetchOpenMeteoHist(lat, lon);

                const labels = [];
                const temps = [];
                if (histData.hourly && histData.hourly.time) {
                    histData.hourly.time.forEach((t, i) => {
                        if (t.endsWith('12:00')) {
                            labels.push(t.substring(5, 10));
                            temps.push(histData.hourly.temperature_2m[i]);
                        }
                    });
                }

                const popupRoot = document.createElement('div');
                popupRoot.style.cssText = "color: #1e293b; font-family: Inter; min-width: 220px;";
                popupRoot.innerHTML = `
                    <h4 style="margin:0 0 8px 0; border-bottom: 1px solid #cbd5e1; padding-bottom: 4px;">Información Oceánica</h4>
                    <p style="margin:0 0 4px 0; font-size: 12px;"><b>Coord:</b> ${lat.toFixed(2)}, ${lon.toFixed(2)}</p>
                    <p style="margin:0 0 4px 0; font-size: 12px;"><b>Temperatura:</b> ${data.temperatura_c != null ? data.temperatura_c.toFixed(1) + '°C' : '--'}</p>
                    <p style="margin:0 0 4px 0; font-size: 12px;"><b>Viento:</b> ${data.viento_ms != null ? data.viento_ms.toFixed(1) + ' m/s' : '--'}</p>
                    <p style="margin:0 0 4px 0; font-size: 12px;"><b>Humedad:</b> ${data.humedad_pct != null ? data.humedad_pct + '%' : '--'}</p>
                    <p style="margin:0 0 4px 0; font-size: 12px; text-transform: capitalize;"><b>Condición:</b> <span data-campo="descripcion"></span></p>
                    <div style="margin-top: 10px; height: 100px; width: 100%;">
                        <canvas id="popupChart"></canvas>
                    </div>
                `;
                popupRoot.querySelector('[data-campo="descripcion"]').textContent = data.descripcion || '--';

                currentPopup.setDOMContent(popupRoot);

                if (labels.length > 0) {
                    setTimeout(() => createPopupChart('popupChart', labels, temps), 100);
                }
            } catch (error) {
                console.error("Error fetching marine info:", error);
                currentPopup.setHTML(`<div style="color: #ef4444; font-family: Inter; font-size: 12px; padding: 5px;">No se pudo obtener información de esta zona.</div>`);
            }
        }
    });

    // Eventos SGR
    map.on('click', 'sgr-events-layer', (e) => {
        const p = e.features[0].properties;
        const html = `<div style="color: #1e293b; font-family: Inter; max-width: 250px;">
            <h4 style="margin:0 0 5px 0; color: #ea580c;">🚨 ${p.evento || 'Evento SGR'}</h4>
            <p style="margin:0 0 5px 0; font-size: 12px;"><b>Fecha:</b> ${p.fechadelevento || 'N/A'}</p>
            <p style="margin:0 0 5px 0; font-size: 12px;"><b>Cantón:</b> ${p.canton || 'N/A'}</p>
            <p style="margin:0 0 5px 0; font-size: 12px;"><b>Afectados:</b> ${p.personasafectadasdirectamente || '0'}</p>
            <p style="margin:0; font-size: 11px; color: #475569;">${p.descripciongeneraldeevento || ''}</p>
        </div>`;
        setCurrentPopup(new maplibregl.Popup().setLngLat(e.lngLat).setHTML(html).addTo(map));
    });
    map.on('mouseenter', 'sgr-events-layer', () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', 'sgr-events-layer', () => { map.getCanvas().style.cursor = ''; });

    // Zonas Seguras SEGURA EP
    map.on('click', 'seguraep-zonasegura-layer', (e) => {
        const p = e.features[0].properties;
        let ubicacion = p['UBICACIÓN'] || p['UBICACION'] || '';
        if (!ubicacion) {
            const uKey = Object.keys(p).find(k => k.includes('UBICACI'));
            if (uKey) ubicacion = p[uKey];
        }
        const html = `<div style="color: #1e293b; font-family: Inter; max-width: 250px;">
            <h4 style="margin: 0 0 8px 0; color: #16a34a; font-size: 14px; border-bottom: 2px solid #22c55e; padding-bottom: 4px;">🟩 Zona Segura #${p.N_ZONA || 'N/A'}</h4>
            <div style="font-size: 12px; margin-bottom: 4px;"><strong>Lugar:</strong> ${p.N_LUGAR || 'Desconocido'}</div>
            <div style="font-size: 12px; margin-bottom: 4px;"><strong>Ubicación:</strong> ${ubicacion || 'Desconocida'}</div>
            <div style="font-size: 12px; margin-bottom: 4px;"><strong>Área Útil:</strong> ${p.AREA_UTI_1 || p.AREA_UTIL || 'N/A'}</div>
        </div>`;
        setCurrentPopup(new maplibregl.Popup({ closeButton: true }).setLngLat(e.lngLat).setHTML(html).addTo(map));
    });
    map.on('mouseenter', 'seguraep-zonasegura-layer', () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', 'seguraep-zonasegura-layer', () => { map.getCanvas().style.cursor = ''; });

    // Zonas de Riesgo
    map.on('click', 'zonas-riesgo-layer', async (e) => {
        const p = e.features[0].properties;
        showHistoryChart(p.zona_id);

        const safeZones = getSafeZonesGeoJSON();
        if (typeof turf !== 'undefined' && safeZones) {
            const startPoint = turf.point([p.lon_centroide, p.lat_centroide]);
            const nearest = turf.nearestPoint(startPoint, safeZones);

            if (nearest) {
                const dest = nearest.geometry.coordinates;
                try {
                    const data = await fetchEvacuationRoute({ lng: p.lon_centroide, lat: p.lat_centroide }, dest);

                    if (data.routes && data.routes.length > 0) {
                        const routeGeoJSON = {
                            type: 'Feature',
                            geometry: data.routes[0].geometry
                        };

                        if (map.getSource('evacuation-route')) {
                            map.getSource('evacuation-route').setData(routeGeoJSON);
                        } else {
                            map.addSource('evacuation-route', {
                                'type': 'geojson',
                                'data': routeGeoJSON
                            });
                            map.addLayer({
                                'id': 'evacuation-route-layer',
                                'type': 'line',
                                'source': 'evacuation-route',
                                'layout': {
                                    'line-join': 'round',
                                    'line-cap': 'round'
                                },
                                'paint': {
                                    'line-color': '#3b82f6',
                                    'line-width': 6,
                                    'line-opacity': 1.0,
                                    'line-dasharray': [2, 1]
                                }
                            });
                        }

                        setCurrentPopup(new maplibregl.Popup({ closeButton: true })
                            .setLngLat([p.lon_centroide, p.lat_centroide])
                            .setHTML(`
                                <div style="font-family: Inter; color: #1e293b;">
                                    <h4 style="margin:0 0 5px 0;">Ruta de Evacuación Trazada</h4>
                                    <p style="margin:0; font-size:12px;">Destino: <b>${nearest.properties.N_LUGAR}</b></p>
                                    <p style="margin:0; font-size:12px;">Distancia: ${(data.routes[0].distance / 1000).toFixed(2)} km</p>
                                </div>
                            `)
                            .addTo(map));
                    }
                } catch (err) {
                    console.error("OSRM Error:", err);
                }
            }
        }
    });
    map.on('mouseenter', 'zonas-riesgo-layer', () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', 'zonas-riesgo-layer', () => { map.getCanvas().style.cursor = ''; });

    // Parroquias Cantonales
    map.on('click', 'sgr-parroquias-layer', (e) => {
        if (!e.features || e.features.length === 0) return;
        const p = e.features[0].properties;
        const pName = p.name || p.Nam || p.DPA_DESPAR || p.PARROQUIA || 'Parroquia';
        updateParroquiaEventsPanel(pName.toUpperCase().replace(/\s+/g, '_'), pName);
    });
    map.on('mouseenter', 'sgr-parroquias-layer', () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', 'sgr-parroquias-layer', () => { map.getCanvas().style.cursor = ''; });

    // Sectores SeguraEP
    map.on('click', 'sgr-celestes-layer', (e) => {
        if (!e.features || e.features.length === 0) return;
        const p = e.features[0].properties;
        const sName = p.name || p.AGA || p.DISTRITO ? `Distrito ${p.DISTRITO}` : 'Distrito Segura EP';
        updateParroquiaEventsPanel(sName.toUpperCase().replace(/\s+/g, '_'), sName);
    });
    map.on('mouseenter', 'sgr-celestes-layer', () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', 'sgr-celestes-layer', () => { map.getCanvas().style.cursor = ''; });
}
