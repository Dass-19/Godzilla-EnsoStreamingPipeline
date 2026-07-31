// ==========================================
// INTERACCIONES Y POPUPS DEL MAPA
// ==========================================

import { map, getSafeZonesGeoJSON } from './map-manager.js';
import { fetchClimaPunto, fetchOpenMeteoHist, fetchEvacuationRoute } from '../api/client.js';
import { createPopupChart, showHistoryChart } from '../components/charts.js';

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
            let riskLevel = "Bajo";
            let riskColor = "#4ade80";

            if (val < 2) { riskLevel = "Alto / Crítico"; riskColor = "#f87171"; }
            else if (val < 5) { riskLevel = "Medio"; riskColor = "#facc15"; }

            const popupHtml = `
                <div style="color: #1e293b; font-family: Inter;">
                    <h4 style="margin:0 0 5px 0;">Análisis de Vulnerabilidad</h4>
                    <p style="margin:0 0 5px 0; font-size: 12px;">Altitud Terreno: <b>${val.toFixed(1)} m</b></p>
                    <p style="margin:0 0 10px 0; font-size: 12px;">Riesgo Inundación: <b style="color: ${riskColor};">${riskLevel}</b></p>
                    ${val < 5 ? `<button id="btn-evac" style="background:#ef4444; color:white; border:none; padding:8px; border-radius:4px; cursor:pointer; width:100%; font-size:11px; font-weight:bold;">🚨 Trazar Ruta Evacuación</button>` : '<p style="font-size:11px; color:#64748b; margin:0;">Zona segura (No requiere evacuación)</p>'}
                </div>
            `;

            setCurrentPopup(new maplibregl.Popup().setLngLat(e.lngLat).setHTML(popupHtml).addTo(map));

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
}
