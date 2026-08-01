// ==========================================
// CONTROLES DE INTERFAZ (VISTAS Y TOGGLES)
// ==========================================

import { CONFIG } from '../config.js';
import { map, isLayersLoaded } from '../map/map-manager.js';

const PARROQUIAS_COORDS = {
    "TARQUI_URDESA": { center: [-79.912, -2.165], zoom: 14, pitch: 45 },
    "TARQUI_SAUCES": { center: [-79.898, -2.132], zoom: 14, pitch: 45 },
    "FEBRES_CORDERO": { center: [-79.918, -2.205], zoom: 14, pitch: 45 },
    "XIMENA_GUASMO": { center: [-79.892, -2.255], zoom: 14, pitch: 45 },
    "PASCUALES": { center: [-79.925, -2.085], zoom: 13.5, pitch: 40 },
    "CHONGON": { center: [-80.080, -2.240], zoom: 13, pitch: 35 },
    "CENTRO": { center: [-79.882, -2.190], zoom: 14.5, pitch: 50 },
    "SAMBORONDON": { center: [-79.865, -2.090], zoom: 12.5, pitch: 30 },
    "DAULE": { center: [-79.980, -1.865], zoom: 12, pitch: 30 }
};

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

        const thermalCheckbox = document.getElementById('toggle-thermal');
        const sstCheckbox = document.getElementById('toggle-sst');
        if ((thermalCheckbox && thermalCheckbox.checked) || (sstCheckbox && sstCheckbox.checked)) {
            document.getElementById('sst-legend')?.classList.remove('hidden');
            document.getElementById('time-lapse-panel')?.classList.remove('hidden');
            if (thermalCheckbox && thermalCheckbox.checked) {
                ['nino34-layer', 'nino12-layer', 'nino3-layer', 'nino4-layer', 'nino34-label', 'nino12-label', 'nino3-label', 'nino4-label', 'depth-layer', 'buoys-layer'].forEach(l => {
                    if (map.getLayer(l)) map.setLayoutProperty(l, 'visibility', 'visible');
                });
            }
            if (sstCheckbox && sstCheckbox.checked) {
                if (map.getLayer('nasa-sst-layer')) map.setLayoutProperty('nasa-sst-layer', 'visibility', 'visible');
            }
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

        const regionalLayers = [
            'nasa-sst-layer', 'depth-layer', 'owm-precip-layer', 'owm-clouds-layer', 'buoys-layer',
            'nino34-layer', 'nino12-layer', 'nino3-layer', 'nino4-layer', 'nino34-label', 'nino12-label', 'nino3-label', 'nino4-label'
        ];
        regionalLayers.forEach(layer => {
            if (map.getLayer(layer)) map.setLayoutProperty(layer, 'visibility', 'none');
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
    });

    // Sidebar Toggle
    document.getElementById('btn-toggle-sidebar')?.addEventListener('click', () => {
        document.getElementById('dashboard-sidebar')?.classList.toggle('collapsed');
        document.getElementById('btn-toggle-sidebar')?.classList.toggle('collapsed');
    });

    // Helper para toggles simples
    const toggleLayer = (id, layerId) => {
        document.getElementById(id)?.addEventListener('change', (e) => {
            if (map && isLayersLoaded() && map.getLayer(layerId)) {
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
        if (map && isLayersLoaded() && map.getLayer('depth-layer')) {
            map.setLayoutProperty('depth-layer', 'visibility', e.target.checked ? 'visible' : 'none');
        }
    });

    toggleLayer('toggle-owm-precip', 'owm-precip-layer');
    toggleLayer('toggle-owm-clouds', 'owm-clouds-layer');
    toggleLayer('toggle-buoys', 'buoys-layer');

    document.getElementById('toggle-base-map')?.addEventListener('change', (e) => {
        if (map && isLayersLoaded() && map.getLayer('opentopo-layer')) {
            map.setLayoutProperty('opentopo-layer', 'visibility', e.target.checked ? 'visible' : 'none');
        }
    });

    document.getElementById('toggle-riesgo-zonas')?.addEventListener('change', (e) => {
        if (map && isLayersLoaded() && map.getLayer('zonas-riesgo-layer')) {
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
        if (map && isLayersLoaded() && map.getLayer('sgr-celestes-layer')) {
            const vis = e.target.checked ? 'visible' : 'none';
            map.setLayoutProperty('sgr-celestes-layer', 'visibility', vis);
            map.setLayoutProperty('sgr-celestes-outline', 'visibility', vis);
            map.setLayoutProperty('sgr-celestes-labels', 'visibility', vis);
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
