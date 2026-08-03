// ==========================================
// PUNTO DE ENTRADA PRINCIPAL (MAIN ORCHESTRATOR)
// ==========================================

import { CONFIG } from './config.js?v=16';
import { initMap, map } from './map/map-manager.js?v=16';
import { initMapInteractions } from './map/map-popups.js?v=16';
import { initUIControls } from './ui/controls.js?v=16';
import { initTimeLapse } from './ui/timelapse.js?v=16';
import { initSimulationControls } from './ui/simulation.js?v=16';
import { initGlobalRiskGauge } from './components/charts.js?v=16';
import { updateDashboard } from './dashboard.js?v=16';

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
