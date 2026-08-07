// ==========================================
// TABLERO DE INDICADORES DE LA AUDITORÍA
// ==========================================

import { fetchLogResumen } from './api/client.js?v=22';

// Icono + texto, nunca color solo: el color no puede ser el único canal que
// distinga "degradado" de "ok".
const ESTADOS = {
    ok: { icono: '●', texto: 'OK' },
    atrasado: { icono: '◷', texto: 'Atrasado' },
    degradado: { icono: '▲', texto: 'Degradado' },
    error: { icono: '✕', texto: 'Error' },
    sin_senal: { icono: '○', texto: 'Sin señal' },
};

const COLOR_NIVEL = { INFO: '#4ade80', WARNING: '#f59e0b', ERROR: '#ef4444' };
const SUPERFICIE = '#0f172a';
const GRIS = '#94a3b8';

let chartActividad = null;

function badge(estado) {
    const { icono, texto } = ESTADOS[estado] ?? ESTADOS.sin_senal;
    const el = document.createElement('span');
    el.className = `badge badge-${estado}`;
    el.textContent = `${icono} ${texto}`;
    return el;
}

function tiempoRelativo(segundos) {
    if (segundos == null) return '—';
    if (segundos < 90) return 'recién';
    const min = Math.round(segundos / 60);
    if (min < 60) return `hace ${min} min`;
    const horas = Math.round(min / 60);
    return horas < 48 ? `hace ${horas} h` : `hace ${Math.round(horas / 24)} d`;
}

function numero(n) {
    return Number(n).toLocaleString('es-EC');
}

function pintarKpis(totales) {
    const grid = document.getElementById('kpi-grid');
    if (!grid) return;
    grid.innerHTML = '';

    const tarjetas = [
        ['Producers sanos', `${totales.ok}/${totales.producers}`,
            totales.ok === totales.producers ? '#4ade80' : '#f1f5f9'],
        ['Degradados', totales.degradados, totales.degradados ? '#f59e0b' : GRIS],
        ['Con error', totales.con_error, totales.con_error ? '#ef4444' : GRIS],
        ['Ciclos completados', numero(totales.ciclos_ok), '#f1f5f9'],
        ['Ciclos vacíos', numero(totales.ciclos_vacios), totales.ciclos_vacios ? '#f59e0b' : GRIS],
        ['Registros publicados', numero(totales.registros_publicados), '#38bdf8'],
    ];

    for (const [etiqueta, valor, color] of tarjetas) {
        const card = document.createElement('div');
        card.className = 'card text-center';

        const l = document.createElement('span');
        l.className = 'label';
        l.textContent = etiqueta;

        const v = document.createElement('span');
        v.className = 'value';
        v.textContent = valor;
        v.style.color = color;

        card.append(l, v);
        grid.appendChild(card);
    }
}

function pintarTabla(producers, alSeleccionar) {
    const tbody = document.getElementById('tabla-producers-body');
    if (!tbody) return;
    tbody.innerHTML = '';

    for (const p of producers) {
        const tr = document.createElement('tr');
        tr.dataset.producer = p.producer;
        if (p.degradaciones.length) tr.title = p.degradaciones.join(' · ');

        const nombre = document.createElement('td');
        nombre.className = 'producer-nombre';
        nombre.textContent = p.producer;

        const estado = document.createElement('td');
        estado.appendChild(badge(p.estado));

        const ciclos = document.createElement('td');
        ciclos.className = 'num';
        ciclos.textContent = p.ciclos_vacios
            ? `${p.ciclos_ok} / ${p.ciclos_vacios} vacíos`
            : String(p.ciclos_ok);

        const publicados = document.createElement('td');
        publicados.className = 'num';
        publicados.textContent = numero(p.registros_publicados);

        const ultimo = document.createElement('td');
        ultimo.textContent = tiempoRelativo(p.atraso_s);

        tr.append(nombre, estado, ciclos, publicados, ultimo);
        tr.addEventListener('click', () => {
            tbody.querySelectorAll('tr.activa').forEach(f => f.classList.remove('activa'));
            tr.classList.add('activa');
            alSeleccionar(p.producer);
        });
        tbody.appendChild(tr);
    }
}

function pintarErrores(errores) {
    const card = document.getElementById('card-errores');
    const lista = document.getElementById('lista-errores');
    if (!card || !lista) return;

    lista.innerHTML = '';
    card.classList.toggle('hidden', errores.length === 0);

    for (const e of errores) {
        const fila = document.createElement('div');
        fila.className = 'error-item';

        const veces = document.createElement('span');
        veces.className = 'veces';
        veces.textContent = `×${e.veces}`;

        const origen = document.createElement('span');
        origen.className = 'origen';
        origen.textContent = e.producer;

        const texto = document.createElement('span');
        texto.className = 'texto';
        texto.textContent = e.mensaje;

        fila.append(veces, origen, texto);
        lista.appendChild(fila);
    }
}

function pintarActividad(horas) {
    const canvas = document.getElementById('chart-actividad');
    if (!canvas || typeof Chart === 'undefined') return;

    // El número de horas cambia entre refrescos: destruir antes de recrear.
    if (chartActividad) chartActividad.destroy();

    chartActividad = new Chart(canvas, {
        type: 'bar',
        data: {
            labels: horas.map(h => h.hora.slice(11, 16)),
            datasets: ['INFO', 'WARNING', 'ERROR'].map(nivel => ({
                label: nivel,
                data: horas.map(h => h[nivel]),
                backgroundColor: COLOR_NIVEL[nivel],
                borderColor: SUPERFICIE,   // 2px de superficie entre segmentos
                borderWidth: 2,
                borderRadius: 4,
                borderSkipped: false,
            })),
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { stacked: true, grid: { display: false }, ticks: { color: GRIS } },
                y: {
                    stacked: true,
                    beginAtZero: true,
                    grid: { color: 'rgba(255,255,255,0.06)' },
                    ticks: { color: GRIS, precision: 0 },
                },
            },
            plugins: {
                legend: { labels: { color: '#cbd5e1', boxWidth: 12, padding: 14 } },
                tooltip: { mode: 'index', intersect: false },
            },
        },
    });
}

export async function cargarResumen(alSeleccionar) {
    let resumen;
    try {
        resumen = await fetchLogResumen(1);
    } catch {
        // Sin resumen la página sigue sirviendo como visor de líneas.
        const grid = document.getElementById('kpi-grid');
        if (grid) {
            grid.innerHTML = '';
            const aviso = document.createElement('div');
            aviso.className = 'card text-center';
            aviso.style.gridColumn = '1 / -1';
            aviso.style.color = '#94a3b8';
            aviso.textContent = 'Sin indicadores: no hay logs archivados en HDFS todavía.';
            grid.appendChild(aviso);
        }
        return;
    }

    pintarKpis(resumen.totales);
    pintarTabla(resumen.producers, alSeleccionar);
    pintarErrores(resumen.top_errores);
    pintarActividad(resumen.actividad_por_hora);
}
