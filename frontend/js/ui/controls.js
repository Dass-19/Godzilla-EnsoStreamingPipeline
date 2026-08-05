// ==========================================
// CONTROLES DE INTERFAZ (VISTAS Y TOGGLES)
// ==========================================

import { CONFIG } from '../config.js?v=21';
import { map, isLayersLoaded } from '../map/map-manager.js?v=21';

export const PARROQUIAS_COORDS = {
    "TARQUI": { name: "Tarqui (Urdesa / Sauces)", center: [-79.912, -2.165], zoom: 13.5, pitch: 40 },
    "FEBRES_CORDERO": { name: "Febres Cordero (Suburbio)", center: [-79.918, -2.205], zoom: 14, pitch: 45 },
    "XIMENA": { name: "Ximena (Guasmo / Trinitaria)", center: [-79.892, -2.255], zoom: 13.5, pitch: 40 },
    "PASCUALES": { name: "Pascuales (Mucho Lote)", center: [-79.925, -2.085], zoom: 13.5, pitch: 40 },
    "CHONGON": { name: "Chongón (Vía a la Costa)", center: [-80.080, -2.240], zoom: 13, pitch: 35 },
    "CENTRO": { name: "Centro (9 de Octubre)", center: [-79.882, -2.190], zoom: 14.5, pitch: 50 },
    "URDANETA": { name: "Urdaneta", center: [-79.902, -2.200], zoom: 14.5, pitch: 45 },
    "LETAMENDI": { name: "Letamendi", center: [-79.910, -2.210], zoom: 14.5, pitch: 45 },
    "GARCIA_MORENO": { name: "García Moreno", center: [-79.898, -2.207], zoom: 14.5, pitch: 45 },
    "CARBO": { name: "Carbo (Concepción)", center: [-79.880, -2.184], zoom: 15, pitch: 45 },
    "ROCAFUERTE": { name: "Rocafuerte", center: [-79.884, -2.186], zoom: 15, pitch: 45 },
    "POSORJA": { name: "Posorja", center: [-80.245, -2.705], zoom: 12.5, pitch: 35 },
    "PUNA": { name: "Isla Puná", center: [-79.910, -2.750], zoom: 11.5, pitch: 30 },
    "TENGUEL": { name: "Tenguel", center: [-79.835, -3.015], zoom: 12.5, pitch: 35 },
    "EL_MORRO": { name: "El Morro", center: [-80.315, -2.620], zoom: 12.5, pitch: 35 },
    "PROGRESO": { name: "Progreso (Juan Gómez Rendón)", center: [-80.370, -2.420], zoom: 12.5, pitch: 35 },
    "SAMBORONDON": { name: "Samborondón", center: [-79.865, -2.090], zoom: 12.5, pitch: 30 },
    "DAULE": { name: "Daule", center: [-79.980, -1.865], zoom: 12, pitch: 30 }
};

export function updateParroquiaEventsPanel(parroquiaKey, customTitle = null) {
    const panel = document.getElementById('parroquia-events-panel');
    if (!panel) return;

    const titleEl = document.getElementById('panel-parroquia-title');
    const subtitleEl = document.getElementById('panel-parroquia-subtitle');
    const countEl = document.getElementById('panel-event-count');
    const affectedEl = document.getElementById('panel-affected-count');
    const listEl = document.getElementById('panel-events-list');

    const pObj = PARROQUIAS_COORDS[parroquiaKey] || {};
    const displayName = customTitle || pObj.name || parroquiaKey || 'Sector';

    if (titleEl) titleEl.innerText = displayName;
    if (subtitleEl) subtitleEl.innerText = `Histórico de Incidentes SGR`;

    const allEvents = window.sgrEventsData || [];

    // Localizar el polígono correspondiente en la capa de Parroquias o de Sectores
    let targetPolygonFeature = null;
    const findPoly = (fc) => {
        if (!fc || !fc.features) return null;
        const targetClean = displayName.toLowerCase().replace(/[\(\)-]/g, '').trim();
        const keyClean = (parroquiaKey || '').toLowerCase().replace(/_/g, ' ').trim();
        return fc.features.find(f => {
            const p = f.properties || {};
            const name = (p.name || p.Nam || p.DPA_DESPAR || p.PARROQUIA || p.AGA || '').toLowerCase();
            return name.includes(targetClean) || targetClean.includes(name) || name.includes(keyClean);
        });
    };

    targetPolygonFeature = findPoly(window.parroquiasGeoJSON) || findPoly(window.sectoresGeoJSON);

    let matchingEvents = [];

    if (targetPolygonFeature && typeof turf !== 'undefined') {
        // Filtrado Espacial Real: comprobar si la coordenada del evento está DENTRO del polígono
        matchingEvents = allEvents.filter(f => {
            if (!f || !f.geometry || !f.geometry.coordinates) return false;
            try {
                const coords = f.geometry.coordinates;
                if (Array.isArray(coords) && coords.length >= 2) {
                    const pt = turf.point([coords[0], coords[1]]);
                    return turf.booleanPointInPolygon(pt, targetPolygonFeature);
                }
            } catch (e) {
                return false;
            }
            return false;
        });
    }

    // Fallback: coincidencia por texto en caso de falta de coordenadas fidedignas o falta de Turf.js
    if (matchingEvents.length === 0) {
        const searchTerms = [displayName.toLowerCase(), (parroquiaKey || '').toLowerCase().replace('_', ' ')];
        matchingEvents = allEvents.filter(f => {
            const p = f.properties || f;
            const txt = `${p.canton || ''} ${p.parroquia || ''} ${p.sector || ''} ${p.evento || ''} ${p.descripcion || ''}`.toLowerCase();
            return searchTerms.some(term => term.length > 2 && txt.includes(term));
        });
    }

    let totalAfectados = 0;
    listEl.innerHTML = '';

    if (matchingEvents.length === 0) {
        if (countEl) countEl.innerText = '0';
        if (affectedEl) affectedEl.innerText = '0';
        listEl.innerHTML = '<div class="empty-state" style="color:#64748b; font-size:12px; text-align:center; padding:15px 0;">Sin eventos de lluvia críticos registrados dentro de esta parroquia.</div>';
    } else {
        matchingEvents.forEach(f => {
            const p = f.properties || f;
            const af = parseInt(p.personasafectadasdirectamente || p.afectados || p.afectados_directos || 0);
            totalAfectados += af;

            const card = document.createElement('div');
            card.className = 'event-card-item';
            card.innerHTML = `
                <div class="event-date">📅 ${p.fechadelevento || p.fecha || 'Registro Reciente'}</div>
                <div class="event-title">${p.evento || p.sector || 'Inundación / Lluvia'}</div>
                <div class="event-desc">${p.descripciongeneraldeevento || p.observaciones || 'Afectación vial y empozamiento de agua por precipitaciones intensas.'}</div>
                <div style="font-size:10px; color:#ef4444; font-weight:bold; margin-top:4px;">Afectados: ${af} personas</div>
            `;
            listEl.appendChild(card);
        });

        if (countEl) countEl.innerText = `${matchingEvents.length}`;
        if (affectedEl) affectedEl.innerText = `${totalAfectados}`;
    }

    panel.classList.remove('hidden');
}

export function initUIControls() {
    // Botón Vista Regional
    document.getElementById('btn-regional')?.addEventListener('click', () => {
        if (!map) return;
        map.flyTo({ center: CONFIG.MAP_CENTER_REGIONAL, zoom: 4, pitch: 0, duration: 2000 });
        document.getElementById('layer-control')?.classList.remove('hidden');
        document.getElementById('local-layer-control')?.classList.add('hidden');
        document.getElementById('tracker-cards')?.classList.remove('hidden');
        document.getElementById('local-cards')?.classList.add('hidden');
        document.getElementById('select-parroquia')?.classList.add('hidden');
        document.getElementById('parroquia-events-panel')?.classList.add('hidden');

        // Ocultar capas locales
        const localLayers = [
            'sgr-events-layer', 'sgr-celestes-layer', 'sgr-celestes-outline', 'sgr-celestes-labels',
            'sgr-parroquias-layer', 'sgr-parroquias-outline', 'sgr-parroquias-labels',
            'sgr-zonasegura-layer', 'sgr-zonasinundables-layer', 'sgr-viasinundables-layer',
            'zonas-riesgo-layer', 'zonas-riesgo-labels'
        ];
        localLayers.forEach(l => { if (map.getLayer(l)) map.setLayoutProperty(l, 'visibility', 'none'); });

        // Activar capas regionales según sus checkboxes
        const regionalMap = [
            { check: 'toggle-sst', layers: ['nasa-sst-layer'] },
            { check: 'toggle-owm-precip', layers: ['owm-precip-layer'] },
            { check: 'toggle-owm-clouds', layers: ['owm-clouds-layer'] },
            { check: 'toggle-buoys', layers: ['buoys-layer'] },
            { check: 'toggle-thermal', layers: ['nino34-layer', 'nino12-layer', 'nino3-layer', 'nino4-layer', 'nino34-label', 'nino12-label', 'nino3-label', 'nino4-label', 'depth-layer'] }
        ];
        regionalMap.forEach(item => {
            const isChecked = document.getElementById(item.check)?.checked;
            item.layers.forEach(l => {
                if (map.getLayer(l)) map.setLayoutProperty(l, 'visibility', isChecked ? 'visible' : 'none');
            });
        });

        const thermalChecked = document.getElementById('toggle-thermal')?.checked;
        const sstChecked = document.getElementById('toggle-sst')?.checked;
        if (thermalChecked || sstChecked) {
            document.getElementById('sst-legend')?.classList.remove('hidden');
            document.getElementById('time-lapse-panel')?.classList.remove('hidden');
        } else {
            document.getElementById('sst-legend')?.classList.add('hidden');
            document.getElementById('time-lapse-panel')?.classList.add('hidden');
        }

        document.getElementById('btn-regional')?.classList.add('active');
        document.getElementById('btn-local')?.classList.remove('active');
    });

    // Botón Vista Local
    document.getElementById('btn-local')?.addEventListener('click', () => {
        if (!map) return;
        map.flyTo({ center: CONFIG.MAP_CENTER_LOCAL, zoom: 11, pitch: 65, bearing: -15, duration: 2000 });
        document.getElementById('layer-control')?.classList.add('hidden');
        document.getElementById('local-layer-control')?.classList.remove('hidden');
        document.getElementById('tracker-cards')?.classList.add('hidden');
        document.getElementById('local-cards')?.classList.remove('hidden');
        document.getElementById('select-parroquia')?.classList.remove('hidden');
        document.getElementById('sst-legend')?.classList.add('hidden');
        document.getElementById('time-lapse-panel')?.classList.add('hidden');

        document.getElementById('btn-local')?.classList.add('active');
        document.getElementById('btn-regional')?.classList.remove('active');

        // Ocultar capas regionales
        const regionalLayers = [
            'nasa-sst-layer', 'depth-layer', 'owm-precip-layer', 'owm-clouds-layer', 'buoys-layer',
            'nino34-layer', 'nino12-layer', 'nino3-layer', 'nino4-layer', 'nino34-label', 'nino12-label', 'nino3-label', 'nino4-label'
        ];
        regionalLayers.forEach(layer => {
            if (map.getLayer(layer)) map.setLayoutProperty(layer, 'visibility', 'none');
        });

        // Activar capas locales según sus checkboxes
        const localMap = [
            { check: 'toggle-base-map', layers: ['opentopo-layer'] },
            { check: 'toggle-riesgo-zonas', layers: ['zonas-riesgo-layer', 'zonas-riesgo-labels'] },
            { check: 'toggle-sgr-events', layers: ['sgr-events-layer'] },
            { check: 'toggle-sgr-parroquias', layers: ['sgr-parroquias-layer', 'sgr-parroquias-outline', 'sgr-parroquias-labels'] },
            { check: 'toggle-sgr-celestes', layers: ['sgr-celestes-layer', 'sgr-celestes-outline', 'sgr-celestes-labels'] },
            { check: 'toggle-seguraep-zonasegura', layers: ['sgr-zonasegura-layer'] },
            { check: 'toggle-sgr-zonasinundables', layers: ['sgr-zonasinundables-layer'] },
            { check: 'toggle-sgr-viasinundables', layers: ['sgr-viasinundables-layer'] }
        ];
        localMap.forEach(item => {
            const isChecked = document.getElementById(item.check)?.checked;
            item.layers.forEach(l => {
                if (map.getLayer(l)) map.setLayoutProperty(l, 'visibility', isChecked ? 'visible' : 'none');
            });
        });
    });

    // Selector de Parroquias / Barrios
    document.getElementById('select-parroquia')?.addEventListener('change', (e) => {
        const val = e.target.value;
        if (!val || !map || !PARROQUIAS_COORDS[val]) return;
        const p = PARROQUIAS_COORDS[val];
        map.flyTo({
            center: p.center,
            zoom: p.zoom,
            pitch: p.pitch,
            bearing: -10,
            duration: 2000
        });
        updateParroquiaEventsPanel(val);
    });

    // Botón de cerrar panel de eventos
    document.getElementById('btn-close-events-panel')?.addEventListener('click', () => {
        document.getElementById('parroquia-events-panel')?.classList.add('hidden');
    });

    // Sidebar Toggle
    document.getElementById('btn-toggle-sidebar')?.addEventListener('click', () => {
        document.getElementById('dashboard-sidebar')?.classList.toggle('collapsed');
        document.getElementById('btn-toggle-sidebar')?.classList.toggle('collapsed');
    });

    // Helper para toggles simples
    const toggleLayer = (id, layerId) => {
        document.getElementById(id)?.addEventListener('change', (e) => {
            if (map && map.getLayer(layerId)) {
                map.setLayoutProperty(layerId, 'visibility', e.target.checked ? 'visible' : 'none');
            }
        });
    };

    // Toggles de Capas Térmicas y SST
    document.getElementById('toggle-thermal')?.addEventListener('change', (e) => {
        if (!map) return;
        ['nino34-layer', 'nino12-layer', 'nino3-layer', 'nino4-layer', 'nino34-label', 'nino12-label', 'nino3-label', 'nino4-label'].forEach(l => {
            if (map.getLayer(l)) map.setLayoutProperty(l, 'visibility', e.target.checked ? 'visible' : 'none');
        });

        const buoysToggle = document.getElementById('toggle-buoys');
        if (buoysToggle) {
            buoysToggle.checked = e.target.checked;
            buoysToggle.dispatchEvent(new Event('change'));
        }

        if (map.getLayer('depth-layer')) {
            map.setLayoutProperty('depth-layer', 'visibility', e.target.checked ? 'visible' : 'none');
        }

        const legend = document.getElementById('sst-legend');
        const timePanel = document.getElementById('time-lapse-panel');
        const isLocal = !document.getElementById('local-layer-control')?.classList.contains('hidden');
        if (legend && timePanel && !isLocal) {
            const sstChecked = document.getElementById('toggle-sst')?.checked;
            if (e.target.checked || sstChecked) {
                legend.classList.remove('hidden');
                timePanel.classList.remove('hidden');
            } else {
                legend.classList.add('hidden');
                timePanel.classList.add('hidden');
            }
        }
    });

    document.getElementById('toggle-sst')?.addEventListener('change', (e) => {
        if (map && map.getLayer('nasa-sst-layer')) {
            map.setLayoutProperty('nasa-sst-layer', 'visibility', e.target.checked ? 'visible' : 'none');
        }
        const legend = document.getElementById('sst-legend');
        const timePanel = document.getElementById('time-lapse-panel');
        const isLocal = !document.getElementById('local-layer-control')?.classList.contains('hidden');
        if (legend && timePanel && !isLocal) {
            const thermalChecked = document.getElementById('toggle-thermal')?.checked;
            if (e.target.checked || thermalChecked) {
                legend.classList.remove('hidden');
                timePanel.classList.remove('hidden');
            } else {
                legend.classList.add('hidden');
                timePanel.classList.add('hidden');
            }
        }
    });

    document.getElementById('toggle-depth')?.addEventListener('change', (e) => {
        if (map && map.getLayer('depth-layer')) {
            map.setLayoutProperty('depth-layer', 'visibility', e.target.checked ? 'visible' : 'none');
        }
    });

    toggleLayer('toggle-owm-precip', 'owm-precip-layer');
    toggleLayer('toggle-owm-clouds', 'owm-clouds-layer');
    toggleLayer('toggle-buoys', 'buoys-layer');

    document.getElementById('toggle-base-map')?.addEventListener('change', (e) => {
        if (map && map.getLayer('opentopo-layer')) {
            map.setLayoutProperty('opentopo-layer', 'visibility', e.target.checked ? 'visible' : 'none');
        }
    });

    document.getElementById('toggle-riesgo-zonas')?.addEventListener('change', (e) => {
        if (map && map.getLayer('zonas-riesgo-layer')) {
            const vis = e.target.checked ? 'visible' : 'none';
            map.setLayoutProperty('zonas-riesgo-layer', 'visibility', vis);
            map.setLayoutProperty('zonas-riesgo-labels', 'visibility', vis);
        }
    });

    toggleLayer('toggle-sgr-events', 'sgr-events-layer');
    toggleLayer('toggle-seguraep-zonasegura', 'sgr-zonasegura-layer');
    toggleLayer('toggle-sgr-zonasinundables', 'sgr-zonasinundables-layer');
    toggleLayer('toggle-sgr-viasinundables', 'sgr-viasinundables-layer');

    document.getElementById('toggle-sgr-celestes')?.addEventListener('change', (e) => {
        if (map && map.getLayer('sgr-celestes-layer')) {
            const vis = e.target.checked ? 'visible' : 'none';
            map.setLayoutProperty('sgr-celestes-layer', 'visibility', vis);
            map.setLayoutProperty('sgr-celestes-outline', 'visibility', vis);
            map.setLayoutProperty('sgr-celestes-labels', 'visibility', vis);
        }
    });

    document.getElementById('toggle-sgr-parroquias')?.addEventListener('change', (e) => {
        if (map && map.getLayer('sgr-parroquias-layer')) {
            const vis = e.target.checked ? 'visible' : 'none';
            map.setLayoutProperty('sgr-parroquias-layer', 'visibility', vis);
            map.setLayoutProperty('sgr-parroquias-outline', 'visibility', vis);
            map.setLayoutProperty('sgr-parroquias-labels', 'visibility', vis);
        }
    });

    ['layer-control', 'local-layer-control'].forEach(prefix => {
        document.getElementById(`toggle-${prefix}-btn`)?.addEventListener('click', () => {
            document.getElementById(`${prefix}-content`)?.classList.toggle('hidden');
        });
    });

    // Cerrar Modal Histórico
    document.getElementById('close-modal-btn')?.addEventListener('click', () => {
        document.getElementById('chart-modal')?.classList.add('hidden');
    });
}
