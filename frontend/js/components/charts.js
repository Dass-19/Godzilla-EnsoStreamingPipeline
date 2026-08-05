// ==========================================
// INTEGRACIÓN DE GRÁFICOS (CHART.JS)
// ==========================================

import { setText } from '../config.js?v=21';
import { fetchHistoricoZona } from '../api/client.js?v=21';

let globalRiskChart = null;
let historyChart = null;

export function initGlobalRiskGauge() {
    const canvas = document.getElementById('globalRiskGauge');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    globalRiskChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Riesgo', 'Seguro'],
            datasets: [{
                data: [0, 100],
                backgroundColor: ['#4ade80', '#1e293b'],
                borderWidth: 0,
                cutout: '80%',
                circumference: 180,
                rotation: 270
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false }, tooltip: { enabled: false } }
        }
    });
}

export function updateGlobalRiskGauge(riskIndex) {
    if (!globalRiskChart) return;
    const safe = 100 - riskIndex;
    let color = '#4ade80';
    let text = 'Bajo';
    if (riskIndex > 40) { color = '#facc15'; text = 'Medio'; }
    if (riskIndex > 70) { color = '#ef4444'; text = 'Alto'; }

    globalRiskChart.data.datasets[0].data = [riskIndex, safe];
    globalRiskChart.data.datasets[0].backgroundColor[0] = color;
    globalRiskChart.update();

    const textEl = document.getElementById('global-risk-text');
    if (textEl) {
        textEl.innerText = text;
        textEl.style.color = color;
    }
}

export async function showHistoryChart(zonaId) {
    const modal = document.getElementById('chart-modal');
    if (!modal) return;
    modal.classList.remove('hidden');
    setText('chart-modal-title', `Histórico - ${zonaId}`);

    try {
        const data = await fetchHistoricoZona(zonaId);

        if (!Array.isArray(data) || data.length === 0) {
            if (historyChart) { historyChart.destroy(); historyChart = null; }
            setText('chart-modal-title', `Histórico - ${zonaId}: sin datos todavía`);
            return;
        }

        const labels = data.map(d => {
            const date = new Date(d.calculado_en);
            return isNaN(date) ? d.calculado_en : date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        });
        const values = data.map(d => (d.indice_riesgo || 0) * 100);

        if (historyChart) historyChart.destroy();

        const canvas = document.getElementById('historyChart');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        historyChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Índice de Riesgo',
                    data: values,
                    borderColor: '#f87171',
                    backgroundColor: 'rgba(248, 113, 113, 0.2)',
                    fill: true,
                    tension: 0.4,
                    yAxisID: 'y'
                },
                {
                    type: 'bar',
                    label: 'Marea (m)',
                    data: data.map(d => d.altura_marea_m || 0),
                    backgroundColor: 'rgba(96, 165, 250, 0.5)',
                    yAxisID: 'y1'
                },
                {
                    type: 'bar',
                    label: 'Lluvia (mm)',
                    data: data.map(d => d.precip_acumulada_24h_mm || 0),
                    backgroundColor: 'rgba(52, 211, 153, 0.5)',
                    yAxisID: 'y2'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { type: 'linear', position: 'left', beginAtZero: true, max: 100, grid: { color: 'rgba(255,255,255,0.1)' }, title: { display: true, text: 'Riesgo %' } },
                    y1: { type: 'linear', position: 'right', beginAtZero: true, max: 5, grid: { display: false }, title: { display: true, text: 'Marea (m)' } },
                    y2: { type: 'linear', position: 'right', beginAtZero: true, max: 200, grid: { display: false }, title: { display: true, text: 'Lluvia (mm)' } },
                    x: { grid: { display: false } }
                },
                plugins: { legend: { display: true, labels: { color: '#fff' } } }
            }
        });
    } catch (err) {
        console.error("Error historial:", err);
    }
}

export function createPopupChart(canvasId, labels, temps) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{ label: 'Temp (°C)', data: temps, borderColor: '#ef4444', borderWidth: 2, pointRadius: 1, tension: 0.3 }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { display: true, ticks: { font: { size: 9 } } },
                y: { display: true, ticks: { font: { size: 9 } } }
            }
        }
    });
}
