// ==========================================
// CONTROLADOR DE SIMULACIÓN (WHAT-IF)
// ==========================================

import { map } from '../map/map-manager.js?v=22';
import { fetchSimulacion } from '../api/client.js?v=22';
import { updateGlobalRiskGauge } from '../components/charts.js?v=22';
import { updateRiskZonesAndGauge } from '../dashboard.js?v=22';

let isSimulating = false;

export function getIsSimulating() {
    return isSimulating;
}

export function setIsSimulating(val) {
    isSimulating = val;
}

export async function runSimulation(rain, tide, dam, btnId, btnText) {
    isSimulating = true;
    const btn = document.getElementById(btnId);
    if (btn) {
        btn.innerText = 'Calculando...';
        btn.style.background = '#facc15';
    }

    try {
        const data = await fetchSimulacion(rain, tide, dam);
        let totalRiesgo = 0;
        const features = [];
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
        updateGlobalRiskGauge(totalRiesgo / data.zonas.length);
        if (map && map.getSource('zonas-riesgo')) {
            map.getSource('zonas-riesgo').setData({ type: 'FeatureCollection', features: features });
        }

        const toggleRiesgo = document.getElementById('toggle-riesgo-zonas');
        if (toggleRiesgo && !toggleRiesgo.checked) {
            toggleRiesgo.checked = true;
            toggleRiesgo.dispatchEvent(new Event('change'));
        }
    } catch (e) {
        console.error("Error en simulación:", e);
    }

    if (btn) {
        btn.innerText = btnText;
        btn.style.background = btnId === 'btn-simular-historico' ? '#ef4444' : '#38bdf8';
    }
}

export function initSimulationControls() {
    document.getElementById('sim-rain')?.addEventListener('input', e => {
        const el = document.getElementById('sim-rain-val');
        if (el) el.innerText = e.target.value;
    });
    document.getElementById('sim-tide')?.addEventListener('input', e => {
        const el = document.getElementById('sim-tide-val');
        if (el) el.innerText = e.target.value;
    });
    document.getElementById('sim-dam')?.addEventListener('input', e => {
        const el = document.getElementById('sim-dam-val');
        if (el) el.innerText = e.target.value;
    });

    ['sim-rain', 'sim-tide', 'sim-dam'].forEach(id => {
        document.getElementById(id)?.addEventListener('change', () => {
            const rain = document.getElementById('sim-rain').value;
            const tide = document.getElementById('sim-tide').value;
            const dam = document.getElementById('sim-dam').value;
            runSimulation(rain, tide, dam, 'btn-simular', '⚡ Proyectar Impacto Manual');
        });
    });

    document.getElementById('btn-simular')?.addEventListener('click', () => {
        const rain = document.getElementById('sim-rain').value;
        const tide = document.getElementById('sim-tide').value;
        const dam = document.getElementById('sim-dam').value;
        runSimulation(rain, tide, dam, 'btn-simular', '⚡ Proyectar Impacto Manual');
    });

    document.getElementById('btn-simular-historico')?.addEventListener('click', () => {
        const rain = 150;
        const tide = 5.0;
        const dam = 85.5;

        document.getElementById('sim-rain').value = rain;
        document.getElementById('sim-tide').value = tide;
        document.getElementById('sim-dam').value = dam;

        document.getElementById('sim-rain-val').innerText = rain;
        document.getElementById('sim-tide-val').innerText = tide;
        document.getElementById('sim-dam-val').innerText = dam;

        runSimulation(rain, tide, dam, 'btn-simular-historico', '🔥 Simular El Niño 1997/98');
    });

    document.getElementById('btn-reset-sim')?.addEventListener('click', () => {
        isSimulating = false;
        document.getElementById('sim-rain').value = 0;
        document.getElementById('sim-tide').value = 0;
        document.getElementById('sim-dam').value = 70;
        document.getElementById('sim-rain-val').innerText = '0';
        document.getElementById('sim-tide-val').innerText = '0';
        document.getElementById('sim-dam-val').innerText = '70';
        updateRiskZonesAndGauge();
    });
}
