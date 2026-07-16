// ==========================================
// CONFIGURACIÓN CENTRALIZADA
// ==========================================
const CONFIG = {
    API_BASE: "http://localhost:8000/api/",
    DATA_BASE: "http://localhost:8000/data/",
    OWM_API_KEY: "9d62ba9628c53f73cea9b19ba1b40849",
    MAP_CENTER_REGIONAL: [-95.0, -1.5],
    MAP_CENTER_LOCAL: [-79.9, -2.18],
    REFRESH_RATE_MS: 5 * 60 * 1000 // 5 minutos
};

// ==========================================
// INICIALIZACIÓN DEL MAPA
// ==========================================
const map = new maplibregl.Map({
    container: 'map',
    style: {
        version: 8,
        glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
        sources: {
            'opentopo': {
                type: 'raster',
                tiles: [
                    'https://a.tile.opentopomap.org/{z}/{x}/{y}.png',
                    'https://b.tile.opentopomap.org/{z}/{x}/{y}.png',
                    'https://c.tile.opentopomap.org/{z}/{x}/{y}.png'
                ],
                tileSize: 256,
                attribution: 'Map data: &copy; OSM contributors'
            }
        },
        layers: [{
            id: 'opentopo-layer',
            type: 'raster',
            source: 'opentopo',
            minzoom: 0,
            maxzoom: 17
        }]
    },
    center: CONFIG.MAP_CENTER_REGIONAL,
    zoom: 4,
    pitch: 0,
    bearing: 0
});

map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }));

let layersLoaded = false;
let globalRiskChart = null;
let historyChart = null;
let currentPopup = null;
let safeZonesGeoJSON = null;

// Cargar Zonas Seguras para cálculo de rutas
fetch(CONFIG.DATA_BASE + 'sgr_zonas_seguras.geojson')
    .then(r => r.json())
    .then(d => safeZonesGeoJSON = d)
    .catch(e => console.error('Error cargando zonas seguras:', e));

map.on('load', () => {
    // Cargar icono de Pin
    const pinSvg = `<svg width="24" height="34" viewBox="0 0 24 34" xmlns="http://www.w3.org/2000/svg"><path d="M12 0C5.373 0 0 5.373 0 12c0 9 12 22 12 22s12-13 12-22C24 5.373 18.627 0 12 0zm0 17a5 5 0 1 1 0-10 5 5 0 0 1 0 10z" fill="#EF4444"/><circle cx="12" cy="12" r="5" fill="white"/></svg>`;
    const img = new Image();
    img.onload = () => { if (!map.hasImage('pin-icon')) map.addImage('pin-icon', img); };
    img.src = 'data:image/svg+xml;base64,' + btoa(pinSvg);

    // RESTAURADO: Terreno 3D
    map.addSource('terrainSource', {
        type: 'raster-dem',
        tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'],
        encoding: 'terrarium',
        tileSize: 256,
        maxzoom: 14
    });
    map.setTerrain({ source: 'terrainSource', exaggeration: 1.5 });

    const dateStr = new Date(Date.now() - 2 * 86400000).toISOString().split('T')[0];

    // Fuentes y Capas Regionales
    map.addSource('nasa-sst', {
        type: 'raster',
        tiles: [`https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/GHRSST_L4_MUR_Sea_Surface_Temperature/default/${dateStr}/GoogleMapsCompatible_Level7/{z}/{y}/{x}.png`],
        tileSize: 256
    });
    map.addLayer({ id: 'nasa-sst-layer', type: 'raster', source: 'nasa-sst', paint: { 'raster-opacity': 0.65 }, layout: { 'visibility': 'visible' } });


    map.addSource('owm-precip', { type: 'raster', tiles: [`https://tile.openweathermap.org/map/precipitation_new/{z}/{x}/{y}.png?appid=${CONFIG.OWM_API_KEY}`], tileSize: 256 });
    map.addLayer({ id: 'owm-precip-layer', type: 'raster', source: 'owm-precip', paint: { 'raster-opacity': 1.0 }, layout: { 'visibility': 'none' } });

    map.addSource('owm-clouds', { type: 'raster', tiles: [`https://tile.openweathermap.org/map/clouds_new/{z}/{x}/{y}.png?appid=${CONFIG.OWM_API_KEY}`], tileSize: 256 });
    map.addLayer({ id: 'owm-clouds-layer', type: 'raster', source: 'owm-clouds', paint: { 'raster-opacity': 0.7 }, layout: { 'visibility': 'none' } });

    // RESTAURADO: Todas las Regiones El Niño
    const regions = {
        'nino34': { label: 'Niño 3.4', coords: [[-170, -5], [-120, -5], [-120, 5], [-170, 5], [-170, -5]], color: '#38bdf8' },
        'nino12': { label: 'Niño 1+2', coords: [[-90, -10], [-80, -10], [-80, 0], [-90, 0], [-90, -10]], color: '#f43f5e' },
        'nino3': { label: 'Niño 3', coords: [[-150, -5], [-90, -5], [-90, 5], [-150, 5], [-150, -5]], color: '#a855f7' },
        'nino4': { label: 'Niño 4', coords: [[160, -5], [210, -5], [210, 5], [160, 5], [160, -5]], color: '#10b981' }
    };
    for (const [id, data] of Object.entries(regions)) {
        map.addSource(id, { type: 'geojson', data: { type: 'Feature', properties: { label: data.label }, geometry: { type: 'Polygon', coordinates: [data.coords] } } });
        map.addLayer({ id: `${id}-layer`, type: 'fill', source: id, paint: { 'fill-color': data.color, 'fill-opacity': 0.3 }, layout: { 'visibility': 'visible' } });
        map.addLayer({ 
            id: `${id}-label`, 
            type: 'symbol', 
            source: id, 
            layout: { 
                'text-field': ['get', 'label'], 
                'text-size': 16, 
                'visibility': 'visible',
                'symbol-placement': 'point',
                'text-allow-overlap': true,
                'text-ignore-placement': true
            }, 
            paint: { 
                'text-color': '#ffffff', 
                'text-halo-color': '#000000', 
                'text-halo-width': 1.5 
            } 
        });
    }

    // RESTAURADO: Ruta Evacuación OSRM
    map.addSource('route', {
        type: 'geojson',
        data: { type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: [] } }
    });
    map.addLayer({
        id: 'route-layer',
        type: 'line',
        source: 'route',
        paint: { 'line-color': '#4ade80', 'line-width': 5 },
        layout: { 'visibility': 'visible', 'line-join': 'round', 'line-cap': 'round' }
    });

    // RESTAURADO: Capas Locales GeoJSON desde la API


    map.addSource('sgr-events', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
    map.addLayer({ id: 'sgr-events-layer', type: 'circle', source: 'sgr-events', paint: { 'circle-radius': 6, 'circle-color': '#f97316', 'circle-stroke-width': 2, 'circle-stroke-color': '#ffffff' }, layout: { 'visibility': 'visible' } });

    fetch(CONFIG.DATA_BASE + 'sgr_eventos.json')
        .then(r => r.json())
        .then(d => {
            const geojson = d.data ? d.data : d;
            map.getSource('sgr-events').setData(geojson);
        })
        .catch(e => console.error("Error cargando sgr_eventos:", e));

    map.addSource('sgr-celestes', { type: 'geojson', data: CONFIG.DATA_BASE + 'sgr_sectores_celestes.geojson' });
    map.addLayer({ id: 'sgr-celestes-layer', type: 'fill', source: 'sgr-celestes', paint: { 'fill-color': '#38bdf8', 'fill-opacity': 0.3 }, layout: { 'visibility': 'visible' } });
    map.addLayer({ id: 'sgr-celestes-outline', type: 'line', source: 'sgr-celestes', paint: { 'line-color': '#0284c7', 'line-width': 2 }, layout: { 'visibility': 'visible' } });
    map.addLayer({ id: 'sgr-celestes-labels', type: 'symbol', source: 'sgr-celestes', layout: { 'text-field': ['get', 'AGA'], 'text-size': 12, 'visibility': 'visible' }, paint: { 'text-color': '#0f172a', 'text-halo-color': '#ffffff', 'text-halo-width': 2 } });

    map.addSource('sgr-zonasegura', { type: 'geojson', data: CONFIG.DATA_BASE + 'sgr_zonas_seguras.geojson' });
    map.addLayer({ id: 'sgr-zonasegura-layer', type: 'circle', source: 'sgr-zonasegura', paint: { 'circle-color': '#22c55e', 'circle-radius': 6, 'circle-stroke-width': 2, 'circle-stroke-color': '#ffffff' }, layout: { 'visibility': 'visible' } });

    map.addSource('sgr-zonasinundables', { type: 'geojson', data: CONFIG.DATA_BASE + 'sgr_zonas_inundables.geojson' });
    map.addLayer({ id: 'sgr-zonasinundables-layer', type: 'fill', source: 'sgr-zonasinundables', paint: { 'fill-color': '#40e0d0', 'fill-opacity': 0.5 }, layout: { 'visibility': 'visible' } });

    map.addSource('sgr-viasinundables', { type: 'geojson', data: CONFIG.DATA_BASE + 'sgr_vias_inundables.geojson' });
    map.addLayer({ id: 'sgr-viasinundables-layer', type: 'line', source: 'sgr-viasinundables', paint: { 'line-color': '#ef4444', 'line-width': 3 }, layout: { 'visibility': 'visible' } });

    // NUEVO: Capa Dinámica de Zonas de Riesgo (Polígonos generados con Turf.js)
    map.addSource('zonas-riesgo', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
    map.addLayer({
        id: 'zonas-riesgo-layer',
        type: 'fill',
        source: 'zonas-riesgo',
        paint: {
            'fill-color': [
                'interpolate', ['linear'], ['get', 'indice_riesgo'],
                0, '#4ade80',
                40, '#facc15',
                70, '#f97316',
                100, '#ef4444'
            ],
            'fill-opacity': 0.5,
            'fill-outline-color': '#ffffff'
        },
        layout: { 'visibility': 'visible' }
    });
    map.addLayer({
        id: 'zonas-riesgo-labels',
        type: 'symbol',
        source: 'zonas-riesgo',
        layout: {
            'text-field': ['concat', ['get', 'nombre_sector'], '\n', ['round', ['get', 'indice_riesgo']], '%'],
            'text-size': 11,
            'visibility': 'visible'
        },
        paint: {
            'text-color': '#ffffff',
            'text-halo-color': '#000000',
            'text-halo-width': 1.5
        }
    });

    new maplibregl.Marker({ color: '#fbbf24' }).setLngLat([-79.886, -2.196]).setPopup(new maplibregl.Popup().setHTML("<b>Guayaquil</b>")).addTo(map);
    // FASE 3: Capas Avanzadas


    // 2. Boyas Oceánicas (NDBC)
    map.addSource('buoys-source', { type: 'geojson', data: CONFIG.DATA_BASE + 'ndbc_buoys.json' });
    map.addLayer({
        id: 'buoys-layer',
        type: 'symbol',
        source: 'buoys-source',
        layout: { 'icon-image': 'pin-icon', 'icon-anchor': 'bottom', 'icon-offset': [0, 0], 'text-field': '{name}\n{water_temp_c}°C', 'text-size': 12, 'text-offset': [0, 0.5], 'text-anchor': 'top', 'visibility': 'none' },
        paint: { 'text-color': '#ffffff', 'text-halo-color': '#000000', 'text-halo-width': 1 }
    });

    // 3. Profundidad Subsuperficial (Ondas Kelvin simuladas)
    map.addSource('depth-source', {
        type: 'geojson',
        data: {
            type: 'FeatureCollection',
            features: [
                { type: 'Feature', properties: { temp: 1 }, geometry: { type: 'Point', coordinates: [-120, 0] } },
                { type: 'Feature', properties: { temp: 1 }, geometry: { type: 'Point', coordinates: [-100, 0] } },
                { type: 'Feature', properties: { temp: 1 }, geometry: { type: 'Point', coordinates: [-85, 0] } }
            ]
        }
    });
    map.addLayer({
        id: 'depth-layer',
        type: 'heatmap',
        source: 'depth-source',
        layout: { 'visibility': 'none' },
        paint: {
            'heatmap-weight': 1,
            'heatmap-intensity': 1,
            'heatmap-color': ['interpolate', ['linear'], ['heatmap-density'], 0, 'rgba(0,0,255,0)', 0.5, 'cyan', 1, 'purple'],
            'heatmap-radius': 150,
            'heatmap-opacity': 0.7
        }
    });

    layersLoaded = true;

    initGlobalRiskGauge();
    updateDashboard();
    setInterval(updateDashboard, CONFIG.REFRESH_RATE_MS);
});

// ==========================================
// CONTROLES DE VISTA
// ==========================================
document.getElementById('btn-regional').addEventListener('click', () => {
    map.flyTo({ center: CONFIG.MAP_CENTER_REGIONAL, zoom: 4, pitch: 0, duration: 2000 });
    document.getElementById('layer-control').classList.remove('hidden');
    document.getElementById('local-layer-control').classList.add('hidden');
    document.getElementById('tracker-cards').classList.remove('hidden');
    document.getElementById('local-cards').classList.add('hidden');

    // Manejar leyenda Térmica y TimeLapse
    const thermalCheckbox = document.getElementById('toggle-thermal');
    const sstCheckbox = document.getElementById('toggle-sst');
    if ((thermalCheckbox && thermalCheckbox.checked) || (sstCheckbox && sstCheckbox.checked)) {
        document.getElementById('sst-legend').classList.remove('hidden');
        document.getElementById('time-lapse-panel').classList.remove('hidden');
        if (thermalCheckbox && thermalCheckbox.checked) {
            ['nino34-layer', 'nino12-layer', 'nino3-layer', 'nino4-layer', 'nino34-label', 'nino12-label', 'nino3-label', 'nino4-label', 'depth-layer', 'buoys-layer'].forEach(l => {
                if (map.getLayer(l)) map.setLayoutProperty(l, 'visibility', 'visible');
            });
        }
        if (sstCheckbox && sstCheckbox.checked) {
            if (map.getLayer('nasa-sst-layer')) map.setLayoutProperty('nasa-sst-layer', 'visibility', 'visible');
        }
    }

    // Cambiar estilos de botones
    document.getElementById('btn-regional').classList.add('active');
    document.getElementById('btn-local').classList.remove('active');
});

document.getElementById('btn-local').addEventListener('click', () => {
    map.flyTo({ center: CONFIG.MAP_CENTER_LOCAL, zoom: 11, pitch: 65, bearing: -15, duration: 2000 });
    document.getElementById('layer-control').classList.add('hidden');
    document.getElementById('local-layer-control').classList.remove('hidden');
    document.getElementById('tracker-cards').classList.add('hidden');
    document.getElementById('local-cards').classList.remove('hidden');
    document.getElementById('sst-legend').classList.add('hidden');
    document.getElementById('time-lapse-panel').classList.add('hidden');

    // Cambiar estilos de botones
    document.getElementById('btn-local').classList.add('active');
    document.getElementById('btn-regional').classList.remove('active');

    // Apagar capas oceánicas
    const regionalLayers = [
        'nasa-sst-layer', 'depth-layer', 'owm-precip-layer', 'owm-clouds-layer', 'buoys-layer',
        'nino34-layer', 'nino12-layer', 'nino3-layer', 'nino4-layer', 'nino34-label', 'nino12-label', 'nino3-label', 'nino4-label'
    ];
    regionalLayers.forEach(layer => {
        if (map.getLayer(layer)) map.setLayoutProperty(layer, 'visibility', 'none');
    });
});

// Toggle Sidebar
document.getElementById('btn-toggle-sidebar').addEventListener('click', () => {
    document.getElementById('dashboard-sidebar').classList.toggle('collapsed');
    document.getElementById('btn-toggle-sidebar').classList.toggle('collapsed');
});

// ==========================================
// TOGGLES DE CAPAS
// ==========================================
const toggleLayer = (id, layerId) => {
    document.getElementById(id)?.addEventListener('change', (e) => {
        if (layersLoaded && map.getLayer(layerId)) {
            map.setLayoutProperty(layerId, 'visibility', e.target.checked ? 'visible' : 'none');
        }
        // Manejar leyenda Térmica y TimeLapse
        if (layerId === 'nino34-layer' || layerId === 'nasa-sst-layer') {
            const legend = document.getElementById('sst-legend');
            const timePanel = document.getElementById('time-lapse-panel');
            const isLocal = !document.getElementById('local-layer-control').classList.contains('hidden');
            if (legend && timePanel && !isLocal) {
                const thermalChecked = document.getElementById('toggle-thermal')?.checked;
                const sstChecked = document.getElementById('toggle-sst')?.checked;
                if (thermalChecked || sstChecked) {
                    legend.classList.remove('hidden');
                    timePanel.classList.remove('hidden');
                } else {
                    legend.classList.add('hidden');
                    timePanel.classList.add('hidden');
                }
            }
        }
    });
};

document.getElementById('toggle-thermal')?.addEventListener('change', (e) => {
    ['nino34-layer', 'nino12-layer', 'nino3-layer', 'nino4-layer', 'nino34-label', 'nino12-label', 'nino3-label', 'nino4-label'].forEach(l => {
        if (map.getLayer(l)) {
            map.setLayoutProperty(l, 'visibility', e.target.checked ? 'visible' : 'none');
        }
    });

    // También habilitar/deshabilitar la información oceánica automáticamente
    const buoysToggle = document.getElementById('toggle-buoys');
    if (buoysToggle) {
        buoysToggle.checked = e.target.checked;
        buoysToggle.dispatchEvent(new Event('change'));
    }
    
    // Habilitar Temp. Subsuperficial
    if (map.getLayer('depth-layer')) {
        map.setLayoutProperty('depth-layer', 'visibility', e.target.checked ? 'visible' : 'none');
    }

    const legend = document.getElementById('sst-legend');
    const timePanel = document.getElementById('time-lapse-panel');
    const isLocal = !document.getElementById('local-layer-control').classList.contains('hidden');
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
    if (map.getLayer('nasa-sst-layer')) {
        map.setLayoutProperty('nasa-sst-layer', 'visibility', e.target.checked ? 'visible' : 'none');
    }
    const legend = document.getElementById('sst-legend');
    const timePanel = document.getElementById('time-lapse-panel');
    const isLocal = !document.getElementById('local-layer-control').classList.contains('hidden');
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
    if (layersLoaded && map.getLayer('depth-layer')) {
        map.setLayoutProperty('depth-layer', 'visibility', e.target.checked ? 'visible' : 'none');
    }
});
toggleLayer('toggle-sst', 'nasa-sst-layer');
toggleLayer('toggle-owm-precip', 'owm-precip-layer');
toggleLayer('toggle-owm-clouds', 'owm-clouds-layer');
toggleLayer('toggle-buoys', 'buoys-layer');

// (Eliminado toggle-regions listener)

document.getElementById('toggle-base-map')?.addEventListener('change', (e) => {
    if (layersLoaded && map.getLayer('opentopo-layer')) {
        map.setLayoutProperty('opentopo-layer', 'visibility', e.target.checked ? 'visible' : 'none');
    }
});

document.getElementById('toggle-riesgo-zonas')?.addEventListener('change', (e) => {
    if (layersLoaded && map.getLayer('zonas-riesgo-layer')) {
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
    if (layersLoaded && map.getLayer('sgr-celestes-layer')) {
        const vis = e.target.checked ? 'visible' : 'none';
        map.setLayoutProperty('sgr-celestes-layer', 'visibility', vis);
        map.setLayoutProperty('sgr-celestes-outline', 'visibility', vis);
        map.setLayoutProperty('sgr-celestes-labels', 'visibility', vis);
    }
});

// Menús Desplegables
['layer-control', 'local-layer-control'].forEach(prefix => {
    document.getElementById(`toggle-${prefix}-btn`)?.addEventListener('click', () => {
        document.getElementById(`${prefix}-content`).classList.toggle('hidden');
    });
});

// ==========================================
// RESTAURADO: INTERACCIÓN MAPA (HOVER / CLICS)
// ==========================================
map.on('mousemove', (e) => {
    const isLocal = !document.getElementById('local-layer-control').classList.contains('hidden');
    if (isLocal) {
        const elevation = map.queryTerrainElevation(e.lngLat);
        const elSpan = document.getElementById('hover-elevation');
        if (elSpan) {
            if (elevation !== null) {
                const val = Math.max(0, elevation);
                elSpan.innerText = `${val.toFixed(1)} m s.n.m.`;
                elSpan.style.color = val < 2 ? '#f87171' : (val < 5 ? '#facc15' : '#4ade80');
            } else {
                elSpan.innerText = `-- m s.n.m.`;
                elSpan.style.color = '#fff';
            }
        }
    }
});

map.on('click', async (e) => {
    const isLocal = !document.getElementById('local-layer-control').classList.contains('hidden');

    // Ignorar si el click fue sobre un popup de evento o zona segura
    const eventLayers = ['sgr-events-layer', 'seguraep-zonasegura-layer', 'zonas-riesgo-layer'];
    const activeLayers = eventLayers.filter(l => map.getLayer(l) && map.getLayoutProperty(l, 'visibility') === 'visible');
    if (activeLayers.length > 0) {
        const features = map.queryRenderedFeatures(e.point, { layers: activeLayers });
        if (features.length > 0) return; // Permitir que el handler especifico lo procese
    }

    // Si estamos en vista local, lanzamos el pop-up de evacuación
    if (isLocal) {
        const elevation = map.queryTerrainElevation(e.lngLat);
        if (elevation === null) return;

        const val = Math.max(0, elevation);
        let riskLevel = "Bajo";
        let riskColor = "#4ade80";

        if (val < 2) { riskLevel = "Alto / Crítico"; riskColor = "#f87171"; }
        else if (val < 5) { riskLevel = "Medio"; riskColor = "#facc15"; }

        const popupHtml = `
            <div style="color: #1e293b; font-family: Inter;">
                <h4 style="margin:0 0 5px 0;">Análisis de Vulnerabilidad</h4>
                <p style="margin:0 0 5px 0; font-size: 12px;">Altitud Terreno: <b>${val.toFixed(1)} m</b></p>
                <p style="margin:0 0 10px 0; font-size: 12px;">Riesgo Inundación: <b style="color: ${riskColor};">${riskLevel}</b></p>
                ${val < 5 ? `<button id="btn-evac" style="background:#ef4444; color:white; border:none; padding:8px; border-radius:4px; cursor:pointer; width:100%; font-size:11px; font-weight:bold;">🚨 Trazar Ruta Evacuación</button>` : '<p style="font-size:11px; color:#64748b; margin:0;">Zona segura (No requiere evacuación)</p>'}
            </div>
        `;

        if (currentPopup) currentPopup.remove();
        currentPopup = new maplibregl.Popup()
            .setLngLat(e.lngLat)
            .setHTML(popupHtml)
            .addTo(map);

        setTimeout(() => {
            const btnEvac = document.getElementById('btn-evac');
            if (btnEvac) {
                btnEvac.addEventListener('click', () => {
                    btnEvac.innerText = "Calculando ruta...";
                    calculateEvacuationRoute(e.lngLat);
                });
            }
        }, 100);
    } else {
        // En vista regional, mostrar información marítima/climática al hacer click
        const lat = e.lngLat.lat;
        const lon = e.lngLat.lng;

        // Mostrar popup temporal
        if (currentPopup) currentPopup.remove();
        currentPopup = new maplibregl.Popup()
            .setLngLat(e.lngLat)
            .setHTML(`<div style="color: #1e293b; font-family: Inter; font-size: 12px; padding: 5px;">Consultando datos marinos...</div>`)
            .addTo(map);

        try {
            // Datos actuales OWM
            const response = await fetch(`https://api.openweathermap.org/data/2.5/weather?lat=${lat}&lon=${lon}&appid=${CONFIG.OWM_API_KEY}&units=metric&lang=es`);
            if (!response.ok) throw new Error("Error en API OWM");
            const data = await response.json();

            // Datos históricos 7 días Open-Meteo
            const histRes = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&hourly=temperature_2m&past_days=7&forecast_days=1`);
            const histData = await histRes.json();

            const labels = [];
            const temps = [];
            if (histData.hourly && histData.hourly.time) {
                histData.hourly.time.forEach((t, i) => {
                    if (t.endsWith('12:00')) {
                        labels.push(t.substring(5, 10)); // MM-DD
                        temps.push(histData.hourly.temperature_2m[i]);
                    }
                });
            }

            const popupHtml = `
                <div style="color: #1e293b; font-family: Inter; min-width: 220px;">
                    <h4 style="margin:0 0 8px 0; border-bottom: 1px solid #cbd5e1; padding-bottom: 4px;">Información Oceánica</h4>
                    <p style="margin:0 0 4px 0; font-size: 12px;"><b>Coord:</b> ${lat.toFixed(2)}, ${lon.toFixed(2)}</p>
                    <p style="margin:0 0 4px 0; font-size: 12px;"><b>Temperatura:</b> ${data.main?.temp ? data.main.temp.toFixed(1) + '°C' : '--'}</p>
                    <p style="margin:0 0 4px 0; font-size: 12px;"><b>Viento:</b> ${data.wind?.speed ? data.wind.speed.toFixed(1) + ' m/s' : '--'}</p>
                    <p style="margin:0 0 4px 0; font-size: 12px;"><b>Humedad:</b> ${data.main?.humidity ? data.main.humidity + '%' : '--'}</p>
                    <p style="margin:0 0 4px 0; font-size: 12px; text-transform: capitalize;"><b>Condición:</b> ${data.weather && data.weather[0] ? data.weather[0].description : '--'}</p>
                    <div style="margin-top: 10px; height: 100px; width: 100%;">
                        <canvas id="popupChart"></canvas>
                    </div>
                </div>
            `;

            currentPopup.setHTML(popupHtml);

            if (labels.length > 0) {
                setTimeout(() => {
                    const ctx = document.getElementById('popupChart')?.getContext('2d');
                    if (ctx) {
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
                }, 100);
            }

        } catch (error) {
            console.error("Error fetching marine info:", error);
            currentPopup.setHTML(`<div style="color: #ef4444; font-family: Inter; font-size: 12px; padding: 5px;">No se pudo obtener información de esta zona.</div>`);
        }
    }
});

function getDistanceFromLatLonInKm(lat1, lon1, lat2, lon2) {
    const R = 6371;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return R * (2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a)));
}

async function calculateEvacuationRoute(startLngLat) {
    let endLngLat = [-79.88, -2.175]; // Zona alta simulada (fallback)

    // Buscar la zona segura más cercana
    try {
        const res = await fetch(CONFIG.DATA_BASE + 'sgr_zonas_seguras.geojson');
        if (res.ok) {
            const data = await res.json();
            let minDist = Infinity;
            data.features.forEach(f => {
                let lng, lat;
                if (f.geometry.type === 'Point') {
                    lng = f.geometry.coordinates[0];
                    lat = f.geometry.coordinates[1];
                } else if (f.geometry.type === 'Polygon' || f.geometry.type === 'MultiPolygon') {
                    const coords = f.geometry.type === 'Polygon' ? f.geometry.coordinates[0][0] : f.geometry.coordinates[0][0][0];
                    lng = coords[0]; lat = coords[1];
                }
                if (lng && lat) {
                    const dist = getDistanceFromLatLonInKm(startLngLat.lat, startLngLat.lng, lat, lng);
                    if (dist < minDist) {
                        minDist = dist;
                        endLngLat = [lng, lat];
                    }
                }
            });
        }
    } catch (e) {
        console.error("Error buscando zonas seguras:", e);
    }

    const url = `http://router.project-osrm.org/route/v1/driving/${startLngLat.lng},${startLngLat.lat};${endLngLat[0]},${endLngLat[1]}?overview=full&geometries=geojson`;

    try {
        const response = await fetch(url);
        const data = await response.json();
        if (data.routes && data.routes.length > 0) {
            const routeGeoJSON = data.routes[0].geometry;
            map.getSource('route').setData({
                type: 'Feature', properties: {}, geometry: routeGeoJSON
            });
            if (currentPopup) currentPopup.remove();

            new maplibregl.Marker({ color: '#4ade80' })
                .setLngLat(endLngLat)
                .setPopup(new maplibregl.Popup().setHTML("<b>Zona Segura</b><br>Albergue sugerido"))
                .addTo(map);
        } else {
            alert("OSRM: No se encontró ruta terrestre.");
        }
    } catch (err) {
        console.error("OSRM Routing Error:", err);
        alert("Error al conectar con OSRM.");
    }
}

// RESTAURADO: Popups de Capas Locales
map.on('click', 'sgr-events-layer', (e) => {
    const p = e.features[0].properties;
    const html = `<div style="color: #1e293b; font-family: Inter; max-width: 250px;">
        <h4 style="margin:0 0 5px 0; color: #ea580c;">🚨 ${p.evento || 'Evento SGR'}</h4>
        <p style="margin:0 0 5px 0; font-size: 12px;"><b>Fecha:</b> ${p.fechadelevento || 'N/A'}</p>
        <p style="margin:0 0 5px 0; font-size: 12px;"><b>Cantón:</b> ${p.canton || 'N/A'}</p>
        <p style="margin:0 0 5px 0; font-size: 12px;"><b>Afectados:</b> ${p.personasafectadasdirectamente || '0'}</p>
        <p style="margin:0; font-size: 11px; color: #475569;">${p.descripciongeneraldeevento || ''}</p>
    </div>`;
    if (currentPopup) currentPopup.remove();
    currentPopup = new maplibregl.Popup().setLngLat(e.lngLat).setHTML(html).addTo(map);
});
map.on('mouseenter', 'sgr-events-layer', () => { map.getCanvas().style.cursor = 'pointer'; });
map.on('mouseleave', 'sgr-events-layer', () => { map.getCanvas().style.cursor = ''; });

map.on('click', 'seguraep-zonasegura-layer', (e) => {
    const p = e.features[0].properties;
    let ubicacion = p['UBICACIÓN'] || p['UBICACION'] || '';
    if (!ubicacion) {
        const uKey = Object.keys(p).find(k => k.includes('UBICACI'));
        if (uKey) ubicacion = p[uKey];
    }
    const html = `<div style="color: #1e293b; font-family: Inter; max-width: 250px;">
        <h4 style="margin: 0 0 8px 0; color: #16a34a; font-size: 14px; border-bottom: 2px solid #22c55e; padding-bottom: 4px;">🟩 Zona Segura #${p.N_ZONA || 'N/A'}</h4>
        <div style="font-size: 12px; margin-bottom: 4px;"><strong>Lugar:</strong> ${p.N_LUGAR || 'Desconocido'}</div>
        <div style="font-size: 12px; margin-bottom: 4px;"><strong>Ubicación:</strong> ${ubicacion || 'Desconocida'}</div>
        <div style="font-size: 12px; margin-bottom: 4px;"><strong>Área Útil:</strong> ${p.AREA_UTI_1 || p.AREA_UTIL || 'N/A'}</div>
    </div>`;
    if (currentPopup) currentPopup.remove();
    currentPopup = new maplibregl.Popup({ closeButton: true }).setLngLat(e.lngLat).setHTML(html).addTo(map);
});
map.on('mouseenter', 'seguraep-zonasegura-layer', () => { map.getCanvas().style.cursor = 'pointer'; });
map.on('mouseleave', 'seguraep-zonasegura-layer', () => { map.getCanvas().style.cursor = ''; });

map.on('click', 'zonas-riesgo-layer', async (e) => {
    const p = e.features[0].properties;
    showHistoryChart(p.zona_id);

    if (typeof turf !== 'undefined' && safeZonesGeoJSON) {
        const startPoint = turf.point([p.lon_centroide, p.lat_centroide]);
        const nearest = turf.nearestPoint(startPoint, safeZonesGeoJSON);
        
        if (nearest) {
            const dest = nearest.geometry.coordinates;
            try {
                const osrmUrl = `http://router.project-osrm.org/route/v1/driving/${p.lon_centroide},${p.lat_centroide};${dest[0]},${dest[1]}?geometries=geojson`;
                const res = await fetch(osrmUrl);
                const data = await res.json();
                
                if (data.routes && data.routes.length > 0) {
                    const routeGeoJSON = {
                        type: 'Feature',
                        geometry: data.routes[0].geometry
                    };
                    
                    if (map.getSource('evacuation-route')) {
                        map.getSource('evacuation-route').setData(routeGeoJSON);
                    } else {
                        map.addSource('evacuation-route', {
                            'type': 'geojson',
                            'data': routeGeoJSON
                        });
                        map.addLayer({
                            'id': 'evacuation-route-layer',
                            'type': 'line',
                            'source': 'evacuation-route',
                            'layout': {
                                'line-join': 'round',
                                'line-cap': 'round'
                            },
                            'paint': {
                                'line-color': '#3b82f6', /* Azul */
                                'line-width': 6,
                                'line-opacity': 1.0,
                                'line-dasharray': [2, 1]
                            }
                        });
                    }

                    if(currentPopup) currentPopup.remove();
                    currentPopup = new maplibregl.Popup({ closeButton: true })
                        .setLngLat([p.lon_centroide, p.lat_centroide])
                        .setHTML(`
                            <div style="font-family: Inter; color: #1e293b;">
                                <h4 style="margin:0 0 5px 0;">Ruta de Evacuación Trazada</h4>
                                <p style="margin:0; font-size:12px;">Destino: <b>${nearest.properties.N_LUGAR}</b></p>
                                <p style="margin:0; font-size:12px;">Distancia: ${(data.routes[0].distance / 1000).toFixed(2)} km</p>
                            </div>
                        `)
                        .addTo(map);
                }
            } catch (err) {
                console.error("OSRM Error:", err);
            }
        }
    }
});
map.on('mouseenter', 'zonas-riesgo-layer', () => { map.getCanvas().style.cursor = 'pointer'; });
map.on('mouseleave', 'zonas-riesgo-layer', () => { map.getCanvas().style.cursor = ''; });

// ==========================================
// FUNCIONES DE ACTUALIZACIÓN (API FETCH)
// ==========================================
async function updateDashboard() {
    await Promise.all([
        updateEnsoData(),
        updateMacroIndexes(),
        updateOpenMeteoData(),
        updateInamhiData(),
        updateTideData(),
        updateEmbalseData(),
        updateRiskZonesAndGauge()
    ]);
}

// ==========================================
// LÓGICA DE SIMULACIÓN (WHAT-IF)
// ==========================================
let isSimulating = false;

async function runSimulation(rain, tide, dam, btnId, btnText) {
    isSimulating = true;
    const btn = document.getElementById(btnId);
    if(btn) {
        btn.innerText = 'Calculando...';
        btn.style.background = '#facc15';
    }

    try {
        const res = await fetch(`${CONFIG.API_BASE}escenario/simular?precip_24h_mm=${rain}&altura_marea_m=${tide}&caudal_embalse_m3s=${dam}`);
        if (res.ok) {
            const data = await res.json();
            let totalRiesgo = 0;
            const features = [];
            data.zonas.forEach(z => {
                z.indice_riesgo = (z.indice_riesgo || 0) * 100;
                totalRiesgo += z.indice_riesgo;
                if (z.lon_centroide && z.lat_centroide) {
                    // Usar Turf.js para crear un polígono sombreado (buffer de 1.5 km) alrededor del centroide
                    if (typeof turf !== 'undefined') {
                        const pt = turf.point([z.lon_centroide, z.lat_centroide]);
                        const buffered = turf.buffer(pt, 1.5, {units: 'kilometers'});
                        buffered.properties = z;
                        features.push(buffered);
                    } else {
                        // Fallback a punto si Turf no cargó
                        features.push({
                            type: 'Feature',
                            geometry: { type: 'Point', coordinates: [z.lon_centroide, z.lat_centroide] },
                            properties: z
                        });
                    }
                }
            });
            updateGlobalRiskGauge(totalRiesgo / data.zonas.length);
            if (map.getSource('zonas-riesgo')) {
                map.getSource('zonas-riesgo').setData({ type: 'FeatureCollection', features: features });
            }

            // Habilitar automáticamente el mapa de vulnerabilidades si estaba apagado
            const toggleRiesgo = document.getElementById('toggle-riesgo-zonas');
            if (toggleRiesgo && !toggleRiesgo.checked) {
                toggleRiesgo.checked = true;
                toggleRiesgo.dispatchEvent(new Event('change'));
            }
        }
    } catch (e) {
        console.error("Error en simulación:", e);
    }

    if(btn) {
        btn.innerText = btnText;
        btn.style.background = btnId === 'btn-simular-historico' ? '#ef4444' : '#38bdf8';
    }
}

document.getElementById('sim-rain')?.addEventListener('input', e => {
    document.getElementById('sim-rain-val').innerText = e.target.value;
});
document.getElementById('sim-tide')?.addEventListener('input', e => {
    document.getElementById('sim-tide-val').innerText = e.target.value;
});
document.getElementById('sim-dam')?.addEventListener('input', e => {
    document.getElementById('sim-dam-val').innerText = e.target.value;
});

// Auto-simular cuando el usuario suelta el slider ("pone los datos en la barra")
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
    // Valores extremos basados en El Niño 1997/98
    const rain = 150;
    const tide = 5.0;
    const dam = 1500;
    
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
    document.getElementById('sim-dam').value = 0;
    document.getElementById('sim-rain-val').innerText = '0';
    document.getElementById('sim-tide-val').innerText = '0';
    document.getElementById('sim-dam-val').innerText = '0';
    updateRiskZonesAndGauge();
});

async function updateEnsoData() {
    try {
        const res = await fetch(CONFIG.API_BASE + 'enso/estado');
        if (!res.ok) return;
        const data = await res.json();
        const parsed = JSON.parse(data.json_str);
        const currentData = parsed.data[parsed.data.length - 1];
        const r = currentData.regions || {};
        const n34 = r.nino_3_4?.anomaly ?? 0;
        const n12 = r.nino_1_2?.anomaly ?? 0;
        const n3 = r.nino_3?.anomaly;
        const n4 = r.nino_4?.anomaly;
        
        // Cacheamos las anomalías reales del día de hoy
        window.noaaAnomalies = { n34, n12, n3: n3 ?? 0, n4: n4 ?? 0 };

        const getColor = anom => anom >= 1.5 ? '#dc2626' : (anom >= 0.5 ? '#f87171' : (anom >= -0.5 ? '#facc15' : '#60a5fa'));
        const getBgColor = anom => anom >= 1.5 ? 'rgba(220, 38, 38, 0.4)' : (anom >= 0.5 ? 'rgba(248, 113, 113, 0.4)' : (anom >= -0.5 ? 'rgba(250, 204, 21, 0.4)' : 'rgba(96, 165, 250, 0.4)'));

        const formatAnom = anom => `${anom > 0 ? '+' : ''}${anom.toFixed(2)} °C`;

        document.getElementById('val-nino34').innerText = formatAnom(n34);
        if(document.getElementById('block-nino34')) document.getElementById('block-nino34').style.background = getBgColor(n34);

        document.getElementById('val-nino12').innerText = formatAnom(n12);
        if(document.getElementById('block-nino12')) document.getElementById('block-nino12').style.background = getBgColor(n12);

        if (n3 !== undefined) {
            document.getElementById('val-nino3').innerText = formatAnom(n3);
            if(document.getElementById('block-nino3')) document.getElementById('block-nino3').style.background = getBgColor(n3);
        }
        if (n4 !== undefined) {
            document.getElementById('val-nino4').innerText = formatAnom(n4);
            if(document.getElementById('block-nino4')) document.getElementById('block-nino4').style.background = getBgColor(n4);
        }

        if (layersLoaded) {
            map.setPaintProperty('nino34-layer', 'fill-color', getColor(n34));
            map.setPaintProperty('nino12-layer', 'fill-color', getColor(n12));
            if (n3 !== undefined) map.setPaintProperty('nino3-layer', 'fill-color', getColor(n3));
            if (n4 !== undefined) map.setPaintProperty('nino4-layer', 'fill-color', getColor(n4));
            
            // Actualizar labels en el mapa para identificar los bloques rectangulares
            const updateLabel = (id, labelName, anom, coords) => {
                const src = map.getSource(id);
                if(src) {
                    src.setData({ type: 'Feature', properties: { label: `${labelName}\n${formatAnom(anom)}` }, geometry: { type: 'Polygon', coordinates: [coords] } });
                }
            };
            updateLabel('nino34', 'Niño 3.4', n34, [[-170, -5], [-120, -5], [-120, 5], [-170, 5], [-170, -5]]);
            updateLabel('nino12', 'Niño 1+2', n12, [[-90, -10], [-80, -10], [-80, 0], [-90, 0], [-90, -10]]);
            if (n3 !== undefined) updateLabel('nino3', 'Niño 3', n3, [[-150, -5], [-90, -5], [-90, 5], [-150, 5], [-150, -5]]);
            if (n4 !== undefined) updateLabel('nino4', 'Niño 4', n4, [[160, -5], [210, -5], [210, 5], [160, 5], [160, -5]]);
        }
    } catch (e) { console.error("Error NOAA:", e); }
}

async function updateMacroIndexes() {
    try {
        const res = await fetch(CONFIG.DATA_BASE + 'enso_indexes.json');
        if (!res.ok) return;
        const json = await res.json();
        if (json.data && json.data.length > 0) {
            const data = json.data[0];
            document.getElementById('val-soi').innerText = `${data.soi_proxy_diff.toFixed(2)} hPa`;
            document.getElementById('val-darwin').innerHTML = `${data.darwin_mslp_hpa.toFixed(1)}<br>hPa`;
            document.getElementById('val-tahiti').innerHTML = `${data.tahiti_mslp_hpa.toFixed(1)}<br>hPa`;
            document.getElementById('val-enso-status').innerText = data.enso_status.toUpperCase();
        }
    } catch (e) { console.error("Error Macro Indexes:", e); }
}

async function updateOpenMeteoData() {
    try {
        const res = await fetch(CONFIG.DATA_BASE + 'open_meteo_data.json');
        if (!res.ok) return;
        const json = await res.json();
        if (json.data && json.data.length > 0) {
            const data = json.data[json.data.length - 1]; // Obtener el último registro
            document.getElementById('val-meteo-rain').innerText = `${data.precipitation_sum_mm.toFixed(1)} mm`;
            document.getElementById('val-meteo-wind').innerText = `${data.max_wind_speed_ms.toFixed(1)} m/s`;
            // Los campos de GPM e INAMHI los dejamos con un placeholder visual o puedes agregarlos si hay data en el futuro
            document.getElementById('val-gpm-rain').innerText = `0.0 mm/día`;
        }
    } catch (e) { console.error("Error Open Meteo:", e); }
}

async function updateInamhiData() {
    try {
        const res = await fetch(CONFIG.DATA_BASE + 'inamhi_data.json');
        if (!res.ok) return;
        const json = await res.json();

        const cantonesInteres = ["GUAYAQUIL", "DAULE", "DURAN", "SAMBORONDON"];
        const activas = json.estaciones.estaciones.filter(e =>
            e.estado_transmision === "TRANSMITIENDO" &&
            cantonesInteres.includes(e.canton)
        );

        const listContainer = document.getElementById('inamhi-list');
        listContainer.innerHTML = '';

        if (activas.length === 0) {
            listContainer.innerHTML = '<div style="text-align: center; color: #94a3b8; font-size: 12px; margin-top: 20px;">No hay estaciones transmitiendo en esta zona.</div>';
            return;
        }

        activas.forEach(est => {
            const el = document.createElement('div');
            el.style.borderBottom = "1px solid rgba(255,255,255,0.1)";
            el.style.padding = "8px 0";
            el.style.fontSize = "11px";

            const catColor = est.categoria.includes("METEORO") ? "#60a5fa" : "#34d399";

            el.innerHTML = `
                <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                    <span style="font-weight: bold; color: #e2e8f0;">${est.punto_obs}</span>
                    <span style="color: #94a3b8;">${est.canton} | Alt: ${est.altitud}m</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: ${catColor}; font-weight: 600;">${est.categoria}</span>
                    <span style="color: #4ade80;">● Transmitiendo</span>
                </div>
            `;
            listContainer.appendChild(el);
        });

        // Parte 2: Pronóstico Diario
        if (json.pronostico_diario && json.pronostico_diario.pronostico) {
            const guayaquil = json.pronostico_diario.pronostico.find(p => p.locality_name === "Guayaquil");
            if (guayaquil) {
                document.getElementById('val-inamhi-temp').innerText = `${guayaquil.min_temperature} / ${guayaquil.max_temperature} °C`;

                let uvColor = '#4ade80';
                if (guayaquil.uv_radiation >= 8) uvColor = '#ef4444';
                else if (guayaquil.uv_radiation >= 5) uvColor = '#facc15';
                document.getElementById('val-inamhi-uv').innerHTML = `<span style="color: ${uvColor}">${guayaquil.uv_radiation}</span>`;

                document.getElementById('val-inamhi-lluvia').innerText = guayaquil.rain ? "Sí 🌧️" : "No ☀️";
                document.getElementById('val-inamhi-lluvia').style.color = guayaquil.rain ? "#60a5fa" : "#4ade80";

                const tarde = guayaquil.forecast.find(f => f.period_name === "Tarde") || guayaquil.forecast[0];
                if (tarde) {
                    document.getElementById('val-inamhi-cond').innerText = tarde.condition_name;
                    const iconEl = document.getElementById('val-inamhi-icon');
                    if (tarde.condition_icon_url) {
                        iconEl.src = tarde.condition_icon_url;
                        iconEl.style.display = 'block';
                    }
                }
            }
        }

    } catch (e) { console.error("Error INAMHI:", e); }
}

async function updateTideData() {
    try {
        const res = await fetch(CONFIG.API_BASE + 'mareas/actual');
        if (!res.ok) return;
        const data = await res.json();
        const parsed = JSON.parse(data.json_str);
        const altura = parsed.altura_marea_m ?? 0;
        document.getElementById('val-surge').innerText = `${altura > 0 ? '+' : ''}${altura.toFixed(2)} m`;
        const descEl = document.getElementById('val-surge-desc');
        if (altura > 2.5) {
            descEl.innerText = "⚠️ Marea Alta";
            descEl.style.color = "#f87171";
        } else {
            descEl.innerText = "✓ Marea normal";
            descEl.style.color = "#4ade80";
        }
        document.getElementById('val-pleamar').innerText = `${altura.toFixed(2)} m`;
    } catch (e) { console.error("Error Mareas:", e); }
}

async function updateEmbalseData() {
    try {
        const res = await fetch(CONFIG.API_BASE + 'embalse/actual');
        if (!res.ok) return;
        const data = await res.json();
        const parsed = JSON.parse(data.json_str);
        const cota = parsed.nivel_msnm ?? 0;
        const caudal = parsed.caudal_m3s ?? 0;
        document.getElementById('val-cota-embalse').innerText = `${cota} m`;
        document.getElementById('val-caudal-embalse').innerText = `${caudal} m³/s`;

        const alertEl = document.getElementById('embalse-alert');
        if (cota > 80) {
            alertEl.innerText = "⚠️ Nivel Crítico. Posible desfogue.";
            alertEl.style.color = "#f87171";
        } else {
            alertEl.innerText = "✓ Nivel Operativo Normal";
            alertEl.style.color = "#4ade80";
        }
    } catch (e) { console.error("Error Embalse:", e); }
}

async function updateRiskZonesAndGauge() {
    if (isSimulating) return; // Evitar que el loop pise la simulación
    try {
        const res = await fetch(CONFIG.API_BASE + 'riesgo/zonas');
        if (!res.ok) return;
        const data = await res.json();

        let totalRiesgo = 0;
        const features = [];
        if (data.zonas && data.zonas.length > 0) {
            data.zonas.forEach(z => {
                z.indice_riesgo = (z.indice_riesgo || 0) * 100;
                totalRiesgo += z.indice_riesgo;
                if (z.lon_centroide && z.lat_centroide) {
                    if (typeof turf !== 'undefined') {
                        const pt = turf.point([z.lon_centroide, z.lat_centroide]);
                        const buffered = turf.buffer(pt, 1.5, {units: 'kilometers'});
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
            const avgRiesgo = totalRiesgo / data.zonas.length;
            updateGlobalRiskGauge(avgRiesgo);

            if (map.getSource('zonas-riesgo')) {
                map.getSource('zonas-riesgo').setData({ type: 'FeatureCollection', features: features });
            }
        }
    } catch (e) { console.error("Error Riesgo Zonas:", e); }
}

// updateRawSensorsData removed

// ==========================================
// CHART.JS: GAUGE GLOBAL
// ==========================================
function initGlobalRiskGauge() {
    const ctx = document.getElementById('globalRiskGauge').getContext('2d');
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

function updateGlobalRiskGauge(riskIndex) {
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
    textEl.innerText = text;
    textEl.style.color = color;
}

// ==========================================
// MODAL & HISTÓRICO
// ==========================================
document.getElementById('close-modal-btn').addEventListener('click', () => {
    document.getElementById('chart-modal').classList.add('hidden');
});

async function showHistoryChart(zona_id) {
    document.getElementById('chart-modal').classList.remove('hidden');
    document.getElementById('chart-modal-title').innerText = `Histórico - ${zona_id}`;

    try {
        const res = await fetch(`${CONFIG.API_BASE}riesgo/zonas/${zona_id}/historico`);
        const data = await res.ok ? await res.json() : [];

        const mockData = data.length > 0 ? data : [
            { calculado_en: '10:00', indice_riesgo: 20 },
            { calculado_en: '11:00', indice_riesgo: 35 },
            { calculado_en: '12:00', indice_riesgo: 50 },
            { calculado_en: '13:00', indice_riesgo: 80 }
        ];

        const labels = mockData.map(d => {
            const date = new Date(d.calculado_en);
            return isNaN(date) ? d.calculado_en : date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        });
        const values = data.length > 0 ? data.map(d => (d.indice_riesgo || 0) * 100) : mockData.map(d => d.indice_riesgo);

        if (historyChart) historyChart.destroy();

        const ctx = document.getElementById('historyChart').getContext('2d');
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
                    data: mockData.map(d => d.altura_marea_m || 0),
                    backgroundColor: 'rgba(96, 165, 250, 0.5)',
                    yAxisID: 'y1'
                },
                {
                    type: 'bar',
                    label: 'Lluvia (mm)',
                    data: mockData.map(d => d.precip_acumulada_24h_mm || 0),
                    backgroundColor: 'rgba(52, 211, 153, 0.5)',
                    yAxisID: 'y2'
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
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


// ==========================================
// TIME-LAPSE SLIDER LOGIC
// ==========================================
function updateSSTLayerDate(offsetDays) {
    if (!map.getLayer('nino34-layer') || !window.noaaAnomalies) return;

    // Lógica para Mapa Térmico
    const baseDate = new Date(Date.now());
    baseDate.setDate(baseDate.getDate() + offsetDays);
    const newDateStr = baseDate.toISOString().split('T')[0];
    document.getElementById('time-lapse-date').innerText = newDateStr;

    const fraction = (30 + offsetDays) / 30; 
    const factor = 0.5 + (0.5 * fraction); 

    const getColor = anom => {
        const val = anom * factor;
        if(val >= 1.5) return '#dc2626';
        if(val >= 0.5) return '#f87171';
        if(val >= -0.5) return '#facc15';
        if(val >= -1.5) return '#60a5fa';
        return '#2563eb';
    };

    map.setPaintProperty('nino34-layer', 'fill-color', getColor(window.noaaAnomalies.n34));
    map.setPaintProperty('nino12-layer', 'fill-color', getColor(window.noaaAnomalies.n12));
    map.setPaintProperty('nino3-layer', 'fill-color', getColor(window.noaaAnomalies.n3));
    map.setPaintProperty('nino4-layer', 'fill-color', getColor(window.noaaAnomalies.n4));

    // Lógica para NASA GIBS
    if (map.getLayer('nasa-sst-layer')) {
        const nasaDate = new Date(Date.now() - 2 * 86400000); // lag de NASA
        nasaDate.setDate(nasaDate.getDate() + offsetDays);
        const nasaDateStr = nasaDate.toISOString().split('T')[0];

        const isVisible = map.getLayoutProperty('nasa-sst-layer', 'visibility');
        const opacity = map.getPaintProperty('nasa-sst-layer', 'raster-opacity');

        map.removeLayer('nasa-sst-layer');
        map.removeSource('nasa-sst');

        map.addSource('nasa-sst', {
            type: 'raster',
            tiles: [`https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/GHRSST_L4_MUR_Sea_Surface_Temperature/default/${nasaDateStr}/GoogleMapsCompatible_Level7/{z}/{y}/{x}.png`],
            tileSize: 256
        });

        // Insertamos antes de nino34-layer para que los rectangulos nativos salgan encima si ambos estan activos
        map.addLayer({
            id: 'nasa-sst-layer',
            type: 'raster',
            source: 'nasa-sst',
            paint: { 'raster-opacity': opacity },
            layout: { 'visibility': isVisible }
        }, map.getLayer('nino34-layer') ? 'nino34-layer' : undefined);
    }
}

// Inicializar fecha
if (document.getElementById('time-lapse-date')) {
    document.getElementById('time-lapse-date').innerText = new Date(Date.now()).toISOString().split('T')[0];
}

let timeLapseInterval = null;
document.getElementById('btn-play-time')?.addEventListener('click', () => {
    const btn = document.getElementById('btn-play-time');
    const slider = document.getElementById('time-lapse-slider');

    if (timeLapseInterval) {
        clearInterval(timeLapseInterval);
        timeLapseInterval = null;
        btn.innerText = '▶';
    } else {
        btn.innerText = '⏸';
        if (parseInt(slider.value) === 0) {
            slider.value = -30;
            updateSSTLayerDate(-30);
        }

        timeLapseInterval = setInterval(() => {
            let val = parseInt(slider.value);
            if (val >= 0) {
                clearInterval(timeLapseInterval);
                timeLapseInterval = null;
                btn.innerText = '▶';
            } else {
                slider.value = val + 1;
                updateSSTLayerDate(val + 1);
            }
        }, 1000); // 1 segundo por día
    }
});

document.getElementById('time-lapse-slider')?.addEventListener('input', (e) => {
    if (timeLapseInterval) {
        clearInterval(timeLapseInterval);
        timeLapseInterval = null;
        document.getElementById('btn-play-time').innerText = '▶';
    }
    updateSSTLayerDate(parseInt(e.target.value));
});
