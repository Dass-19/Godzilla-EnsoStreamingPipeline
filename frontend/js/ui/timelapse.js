// ==========================================
// CONTROLADOR DE TIME-LAPSE (SST / NASA GIBS)
// ==========================================

import { map } from '../map/map-manager.js?v=18';

let timeLapseInterval = null;

export function updateSSTLayerDate(offsetDays) {
    if (!map || !map.getLayer('nino34-layer') || !window.noaaAnomalies) return;

    const baseDate = new Date(Date.now());
    baseDate.setDate(baseDate.getDate() + offsetDays);
    const newDateStr = baseDate.toISOString().split('T')[0];

    const dateSpan = document.getElementById('time-lapse-date');
    if (dateSpan) dateSpan.innerText = newDateStr;

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

    // NASA GIBS
    if (map.getLayer('nasa-sst-layer')) {
        const nasaDate = new Date(Date.now() - 2 * 86400000);
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

        map.addLayer({
            id: 'nasa-sst-layer',
            type: 'raster',
            source: 'nasa-sst',
            paint: { 'raster-opacity': opacity },
            layout: { 'visibility': isVisible }
        }, map.getLayer('nino34-layer') ? 'nino34-layer' : undefined);
    }
}

export function initTimeLapse() {
    const dateSpan = document.getElementById('time-lapse-date');
    if (dateSpan) {
        dateSpan.innerText = new Date(Date.now()).toISOString().split('T')[0];
    }

    const btnPlay = document.getElementById('btn-play-time');
    const slider = document.getElementById('time-lapse-slider');

    btnPlay?.addEventListener('click', () => {
        if (timeLapseInterval) {
            clearInterval(timeLapseInterval);
            timeLapseInterval = null;
            btnPlay.innerText = '▶';
        } else {
            btnPlay.innerText = '⏸';
            if (parseInt(slider.value) === 0) {
                slider.value = -30;
                updateSSTLayerDate(-30);
            }

            timeLapseInterval = setInterval(() => {
                let val = parseInt(slider.value);
                if (val >= 0) {
                    clearInterval(timeLapseInterval);
                    timeLapseInterval = null;
                    btnPlay.innerText = '▶';
                } else {
                    slider.value = val + 1;
                    updateSSTLayerDate(val + 1);
                }
            }, 1000);
        }
    });

    slider?.addEventListener('input', (e) => {
        if (timeLapseInterval) {
            clearInterval(timeLapseInterval);
            timeLapseInterval = null;
            if (btnPlay) btnPlay.innerText = '▶';
        }
        updateSSTLayerDate(parseInt(e.target.value));
    });
}
