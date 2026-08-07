// ==========================================
// PÁGINA DE AUDITORÍA DE LOGS DE PRODUCERS (/logs)
// ==========================================

import { mensajeVacio } from './config.js?v=22';
import { fetchLogProducers, fetchLogs } from './api/client.js?v=22';
import { cargarResumen } from './logs-resumen.js?v=22';

const REFRESCO_MS = 60 * 1000;
const LIMITE_LINEAS = 1000;

// Últimas líneas traídas del servidor; el buscador filtra sobre esto sin
// volver a pedirlas.
let registrosCargados = [];

function nivelClase(nivel) {
    if (nivel === 'ERROR' || nivel === 'CRITICAL') return 'nivel-error';
    if (nivel === 'WARNING') return 'nivel-warning';
    return 'nivel-info';
}

function pintarLogs(registros) {
    const listEl = document.getElementById('logs-audit-list');
    const conteoEl = document.getElementById('logs-conteo');
    listEl.innerHTML = '';

    if (conteoEl) {
        conteoEl.textContent = registros.length
            ? `${registros.length} línea${registros.length === 1 ? '' : 's'}`
            : '';
    }

    if (!registros.length) {
        listEl.appendChild(mensajeVacio('Sin líneas para ese filtro.'));
        return;
    }

    for (const r of registros) {
        const card = document.createElement('div');
        card.className = `event-card-item ${nivelClase(r.nivel)}`;

        const fecha = document.createElement('div');
        fecha.className = 'event-date';
        fecha.textContent = `${r.fecha} · ${r.nivel}`;

        const logger = document.createElement('div');
        logger.className = 'event-title';
        logger.textContent = r.logger;

        const mensaje = document.createElement('div');
        mensaje.className = 'event-desc';
        mensaje.textContent = r.mensaje;

        card.append(fecha, logger, mensaje);
        listEl.appendChild(card);
    }
}

function aplicarBusqueda() {
    const termino = (document.getElementById('logs-buscar')?.value ?? '').trim().toLowerCase();
    pintarLogs(
        termino
            ? registrosCargados.filter(r => r.mensaje.toLowerCase().includes(termino))
            : registrosCargados
    );
}

async function cargarLogs() {
    const listEl = document.getElementById('logs-audit-list');
    const producer = document.getElementById('logs-select-producer')?.value;
    const nivel = document.getElementById('logs-select-nivel')?.value;
    if (!listEl) return;

    if (!producer) {
        registrosCargados = [];
        listEl.innerHTML = '';
        listEl.appendChild(mensajeVacio('Selecciona un producer para ver sus logs.'));
        return;
    }

    listEl.innerHTML = '';
    listEl.appendChild(mensajeVacio('Cargando…'));

    try {
        registrosCargados = await fetchLogs({ producer, nivel, limite: LIMITE_LINEAS }) ?? [];
    } catch (e) {
        // Con el 404-si-vacío corregido, un fallo acá es un fallo real (HDFS
        // caído, producer inexistente) y no "no hay líneas".
        registrosCargados = [];
        listEl.innerHTML = '';
        listEl.appendChild(mensajeVacio(`No se pudieron cargar los logs: ${e.message}`));
        return;
    }
    aplicarBusqueda();
}

function seleccionarProducer(nombre) {
    const select = document.getElementById('logs-select-producer');
    if (!select) return;
    select.value = nombre;
    cargarLogs();
}

async function poblarProducers() {
    const select = document.getElementById('logs-select-producer');
    if (!select) return;
    try {
        const nombres = await fetchLogProducers();
        for (const nombre of nombres ?? []) {
            const opt = document.createElement('option');
            opt.value = nombre;
            opt.textContent = nombre;
            select.appendChild(opt);
        }
    } catch {
        // Aún no hay logs en HDFS: el select queda solo con la opción vacía.
    }
}

async function refrescarTablero() {
    await cargarResumen(seleccionarProducer);
    const sello = document.getElementById('logs-actualizado');
    if (sello) {
        sello.textContent = `actualizado ${new Date().toLocaleTimeString('es-EC')}`;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    poblarProducers();
    refrescarTablero();
    setInterval(refrescarTablero, REFRESCO_MS);

    document.getElementById('logs-select-producer')?.addEventListener('change', cargarLogs);
    document.getElementById('logs-select-nivel')?.addEventListener('change', cargarLogs);
    document.getElementById('logs-buscar')?.addEventListener('input', aplicarBusqueda);
});
