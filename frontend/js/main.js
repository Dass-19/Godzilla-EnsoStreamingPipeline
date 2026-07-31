// ==========================================
// PUNTO DE ENTRADA PRINCIPAL (MAIN ORCHESTRATOR)
// ==========================================

import { CONFIG } from './config.js';
import { initMap, map } from './map/map-manager.js';
import { initMapInteractions } from './map/map-popups.js';
import { initUIControls } from './ui/controls.js';
import { initTimeLapse } from './ui/timelapse.js';
import { initSimulationControls } from './ui/simulation.js';
import { initGlobalRiskGauge } from './components/charts.js';
import { updateDashboard } from './dashboard.js';

document.addEventListener('DOMContentLoaded', () => {
    // 1. Inicializar mapa
    initMap();

    // 2. Inicializar controles UI y paneles
    initUIControls();
    initTimeLapse();
    initSimulationControls();

    // 3. Inicializar interacciones en el mapa cuando esté listo
    if (map) {
        map.on('load', () => {
            initGlobalRiskGauge();
            initMapInteractions();
            updateDashboard();
            setInterval(updateDashboard, CONFIG.REFRESH_RATE_MS);
        });
    }
});
