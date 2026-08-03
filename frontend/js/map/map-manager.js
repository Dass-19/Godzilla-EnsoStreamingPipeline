// ==========================================
// GESTOR DE MAPA (MAPLIBRE GL)
// ==========================================

import { CONFIG } from '../config.js?v=18';

export let map = null;
let layersLoaded = false;
let safeZonesGeoJSON = null;

export function isLayersLoaded() {
    return layersLoaded;
}

export function getSafeZonesGeoJSON() {
    return safeZonesGeoJSON;
}

export function initMap() {
    map = new maplibregl.Map({
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

    // Cargar Zonas Seguras para cálculo de rutas
    fetch(CONFIG.API_BASE + 'capas/zonas-seguras')
        .then(r => r.json())
        .then(d => { safeZonesGeoJSON = d.data ? d.data : (d.datos ? d.datos : d); })
        .catch(e => console.error('Error cargando zonas seguras:', e));

    function extractGeoJSON(d) {
        if (!d) return { type: 'FeatureCollection', features: [] };
        let curr = d;
        if (curr.data && typeof curr.data === 'object' && !curr.features) {
            curr = curr.data;
        }
        if (curr.data && typeof curr.data === 'object' && (curr.data.features || curr.data.type)) {
            curr = curr.data;
        }
        if (curr.datos && typeof curr.datos === 'object' && (curr.datos.features || curr.datos.type)) {
            curr = curr.datos;
        }
        if (curr && Array.isArray(curr.features)) {
            return curr;
        }
        if (Array.isArray(curr)) {
            return { type: 'FeatureCollection', features: curr };
        }
        return { type: 'FeatureCollection', features: [] };
    }

    const ENDPOINT_MAP = {
        'sgr_parroquias_guayaquil.geojson': 'capas/parroquias',
        'sgr_sectores_celestes.geojson': 'capas/sectores',
        'sgr_zonas_inundables.geojson': 'capas/zonas-inundables',
        'sgr_zonas_seguras.geojson': 'capas/zonas-seguras',
        'sgr_vias_inundables.geojson': 'capas/vias-inundables',
        'sgr_vias_vulnerables_marea_alta.geojson': 'capas/vias-vulnerables-marea',
        'sgr_eventos.json': 'eventos/sgr',
        'guayas_osm.geojson': 'capas/guayas-osm',
        'ndbc_buoys.json': 'boyas/ndbc'
    };

    const getEndpointUrl = (name) => {
        const route = ENDPOINT_MAP[name];
        if (route) return CONFIG.API_BASE + route;
        return CONFIG.API_BASE + name;
    };

    const loadGeoJSONSource = (sourceId, filename) => {
        const url = getEndpointUrl(filename);
        fetch(url)
            .then(r => r.json())
            .then(d => {
                const geojson = extractGeoJSON(d);
                if (filename.includes('parroquias')) {
                    window.parroquiasGeoJSON = geojson;
                } else if (filename.includes('celestes')) {
                    window.sectoresGeoJSON = geojson;
                } else if (filename.includes('eventos')) {
                    window.sgrEventsData = geojson.features || [];
                }
                if (map && map.getSource(sourceId)) {
                    map.getSource(sourceId).setData(geojson);
                }
            })
            .catch(e => console.error(`Error cargando capa ${filename}:`, e));
    };

    map.on('load', () => {
        // Icono de Pin
        const pinSvg = `<svg width="24" height="34" viewBox="0 0 24 34" xmlns="http://www.w3.org/2000/svg"><path d="M12 0C5.373 0 0 5.373 0 12c0 9 12 22 12 22s12-13 12-22C24 5.373 18.627 0 12 0zm0 17a5 5 0 1 1 0-10 5 5 0 0 1 0 10z" fill="#EF4444"/><circle cx="12" cy="12" r="5" fill="white"/></svg>`;
        const img = new Image();
        img.onload = () => { if (!map.hasImage('pin-icon')) map.addImage('pin-icon', img); };
        img.src = 'data:image/svg+xml;base64,' + btoa(pinSvg);

        // Terreno 3D
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

        map.addSource('owm-precip', { type: 'raster', tiles: [`${CONFIG.API_BASE}clima/tiles/precipitation_new/{z}/{x}/{y}.png`], tileSize: 256 });
        map.addLayer({ id: 'owm-precip-layer', type: 'raster', source: 'owm-precip', paint: { 'raster-opacity': 1.0 }, layout: { 'visibility': 'none' } });

        map.addSource('owm-clouds', { type: 'raster', tiles: [`${CONFIG.API_BASE}clima/tiles/clouds_new/{z}/{x}/{y}.png`], tileSize: 256 });
        map.addLayer({ id: 'owm-clouds-layer', type: 'raster', source: 'owm-clouds', paint: { 'raster-opacity': 0.7 }, layout: { 'visibility': 'none' } });

        // Regiones El Niño
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

        // Ruta Evacuación OSRM
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

        // Capas Locales GeoJSON
        map.addSource('sgr-events', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
        map.addLayer({ id: 'sgr-events-layer', type: 'circle', source: 'sgr-events', paint: { 'circle-radius': 6, 'circle-color': '#f97316', 'circle-stroke-width': 2, 'circle-stroke-color': '#ffffff' }, layout: { 'visibility': 'visible' } });
        loadGeoJSONSource('sgr-events', 'sgr_eventos.json');

        map.addSource('sgr-celestes', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
        map.addLayer({ id: 'sgr-celestes-layer', type: 'fill', source: 'sgr-celestes', paint: { 'fill-color': '#38bdf8', 'fill-opacity': 0.3 }, layout: { 'visibility': 'visible' } });
        map.addLayer({ id: 'sgr-celestes-outline', type: 'line', source: 'sgr-celestes', paint: { 'line-color': '#0284c7', 'line-width': 2 }, layout: { 'visibility': 'visible' } });
        map.addLayer({ id: 'sgr-celestes-labels', type: 'symbol', source: 'sgr-celestes', layout: { 'text-field': ['get', 'AGA'], 'text-size': 12, 'visibility': 'visible' }, paint: { 'text-color': '#0f172a', 'text-halo-color': '#ffffff', 'text-halo-width': 2 } });
        loadGeoJSONSource('sgr-celestes', 'sgr_sectores_celestes.geojson');

        map.addSource('sgr-parroquias', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
        map.addLayer({ id: 'sgr-parroquias-layer', type: 'fill', source: 'sgr-parroquias', paint: { 'fill-color': '#818cf8', 'fill-opacity': 0.25 }, layout: { 'visibility': 'visible' } });
        map.addLayer({ id: 'sgr-parroquias-outline', type: 'line', source: 'sgr-parroquias', paint: { 'line-color': '#6366f1', 'line-width': 1.8, 'line-dasharray': [2, 2] }, layout: { 'visibility': 'visible' } });
        map.addLayer({ id: 'sgr-parroquias-labels', type: 'symbol', source: 'sgr-parroquias', layout: { 'text-field': ['get', 'name'], 'text-size': 11, 'visibility': 'visible' }, paint: { 'text-color': '#ffffff', 'text-halo-color': '#0f172a', 'text-halo-width': 2 } });
        loadGeoJSONSource('sgr-parroquias', 'sgr_parroquias_guayaquil.geojson');

        map.addSource('sgr-zonasegura', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
        map.addLayer({ id: 'sgr-zonasegura-layer', type: 'circle', source: 'sgr-zonasegura', paint: { 'circle-color': '#22c55e', 'circle-radius': 6, 'circle-stroke-width': 2, 'circle-stroke-color': '#ffffff' }, layout: { 'visibility': 'visible' } });
        loadGeoJSONSource('sgr-zonasegura', 'sgr_zonas_seguras.geojson');

        map.addSource('sgr-zonasinundables', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
        map.addLayer({ id: 'sgr-zonasinundables-layer', type: 'fill', source: 'sgr-zonasinundables', paint: { 'fill-color': '#40e0d0', 'fill-opacity': 0.5 }, layout: { 'visibility': 'visible' } });
        loadGeoJSONSource('sgr-zonasinundables', 'sgr_zonas_inundables.geojson');

        map.addSource('sgr-viasinundables', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
        map.addLayer({ id: 'sgr-viasinundables-layer', type: 'line', source: 'sgr-viasinundables', paint: { 'line-color': '#ef4444', 'line-width': 3 }, layout: { 'visibility': 'visible' } });
        loadGeoJSONSource('sgr-viasinundables', 'sgr_vias_inundables.geojson');

        // Capa Dinámica de Zonas de Riesgo (Polígonos generados con Turf.js)
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

        // Boyas Oceánicas (NDBC)
        map.addSource('buoys-source', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
        map.addLayer({
            id: 'buoys-layer',
            type: 'symbol',
            source: 'buoys-source',
            layout: { 'icon-image': 'pin-icon', 'icon-anchor': 'bottom', 'icon-offset': [0, 0], 'text-field': '{name}\n{water_temp_c}°C', 'text-size': 12, 'text-offset': [0, 0.5], 'text-anchor': 'top', 'visibility': 'none' },
            paint: { 'text-color': '#ffffff', 'text-halo-color': '#000000', 'text-halo-width': 1 }
        });
        loadGeoJSONSource('buoys-source', 'ndbc_buoys.json');

        // Profundidad Subsuperficial (Ondas Kelvin simuladas)
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
    });
}
