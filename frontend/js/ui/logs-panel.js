// ==========================================
// PANEL DE AUDITORÍA DE LOGS DE PRODUCERS
// ==========================================

import { mensajeVacio } from '../config.js?v=20';
import { fetchLogProducers, fetchLogs } from '../api/client.js?v=20';

function nivelClase(nivel) {
    if (nivel === 'ERROR') return 'nivel-error';
    if (nivel === 'WARNING') return 'nivel-warning';
    return 'nivel-info';
}

function pintarLogs(listEl, registros) {
    listEl.innerHTML = '';
    if (!registros || registros.length === 0) {
        listEl.appendChild(mensajeVacio('Sin logs para ese filtro.'));
        return;
    }

    registros.forEach(r => {
        const card = document.createElement('div');
        card.className = `event-card-item ${nivelClase(r.nivel)}`;

        const fechaEl = document.createElement('div');
        fechaEl.className = 'event-date';
        fechaEl.textContent = `${r.fecha} · ${r.nivel}`;

        const loggerEl = document.createElement('div');
        loggerEl.className = 'event-title';
        loggerEl.textContent = r.logger;

        const mensajeEl = document.createElement('div');
        mensajeEl.className = 'event-desc';
        mensajeEl.textContent = r.mensaje;

        card.append(fechaEl, loggerEl, mensajeEl);
        listEl.appendChild(card);
    });
}

async function cargarLogs() {
    const listEl = document.getElementById('logs-audit-list');
    const producer = document.getElementById('logs-select-producer')?.value;
    const nivel = document.getElementById('logs-select-nivel')?.value;
    if (!listEl) return;

    if (!producer) {
        listEl.innerHTML = '';
        listEl.appendChild(mensajeVacio('Selecciona un producer para ver sus logs.'));
        return;
    }

    listEl.innerHTML = '';
    listEl.appendChild(mensajeVacio('Cargando...'));

    let registros = [];
    try {
        registros = await fetchLogs({ producer, nivel });
    } catch {
        registros = [];
    }
    pintarLogs(listEl, registros);
}

async function poblarProducers() {
    const select = document.getElementById('logs-select-producer');
    if (!select) return;
    try {
        const nombres = await fetchLogProducers();
        (nombres || []).forEach(nombre => {
            const opt = document.createElement('option');
            opt.value = nombre;
            opt.textContent = nombre;
            select.appendChild(opt);
        });
    } catch {
        // Aún no hay logs de ningún producer en HDFS: el select queda con solo
        // la opción vacía, sin romper el resto del panel.
    }
}

export function initLogsPanel() {
    document.getElementById('toggle-logs-panel-btn')?.addEventListener('click', () => {
        const panel = document.getElementById('logs-audit-panel');
        const select = document.getElementById('logs-select-producer');
        if (!panel) return;
        const seAbre = panel.classList.contains('hidden');
        panel.classList.toggle('hidden');
        if (seAbre && select && select.options.length <= 1) {
            poblarProducers();
        }
    });

    document.getElementById('btn-close-logs-panel')?.addEventListener('click', () => {
        document.getElementById('logs-audit-panel')?.classList.add('hidden');
    });

    document.getElementById('logs-select-producer')?.addEventListener('change', cargarLogs);
    document.getElementById('logs-select-nivel')?.addEventListener('change', cargarLogs);
}
