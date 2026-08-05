// ==========================================
// PUNTO DE ENTRADA PRINCIPAL (MAIN ORCHESTRATOR)
// ==========================================

import { CONFIG } from './config.js?v=20';
import { initMap, map } from './map/map-manager.js?v=20';
import { initMapInteractions } from './map/map-popups.js?v=20';
import { initUIControls } from './ui/controls.js?v=20';
import { initTimeLapse } from './ui/timelapse.js?v=20';
import { initSimulationControls } from './ui/simulation.js?v=20';
import { initLogsPanel } from './ui/logs-panel.js?v=20';
import { initGlobalRiskGauge } from './components/charts.js?v=20';
import { updateDashboard } from './dashboard.js?v=20';

document.addEventListener('DOMContentLoaded', () => {
    // 1. Inicializar mapa
    initMap();

    // 2. Inicializar controles UI y paneles
    initUIControls();
    initTimeLapse();
    initSimulationControls();
    initLogsPanel();

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
