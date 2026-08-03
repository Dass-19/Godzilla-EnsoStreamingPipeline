"""
Tests unitarios para la interpolación espacial IDW.
"""

from dataclasses import dataclass

from interpolacion import haversine_km, interpolar_idw


@dataclass
class EstacionTest:
    lat: float
    lon: float
    precip_24h_mm: float


def test_haversine_distancia_conocida():
    # Distancia entre Guayaquil (-2.19, -79.89) y Durán (-2.17, -79.83) es ~8.7 km
    d = haversine_km(-2.19, -79.89, -2.17, -79.83)
    assert 7.0 < d < 10.0


def test_idw_estacion_exacta_devuelve_su_valor():
    estaciones = [
        EstacionTest(lat=-2.19, lon=-79.89, precip_24h_mm=50.0),
        EstacionTest(lat=-2.15, lon=-79.90, precip_24h_mm=10.0),
    ]
    val, n = interpolar_idw(estaciones, lat=-2.19, lon=-79.89)
    assert val == 50.0
    assert n == 1


def test_idw_interpola_entre_minimo_y_maximo():
    estaciones = [
        EstacionTest(lat=-2.19, lon=-79.89, precip_24h_mm=10.0),
        EstacionTest(lat=-2.15, lon=-79.90, precip_24h_mm=50.0),
    ]
    val, n = interpolar_idw(estaciones, lat=-2.17, lon=-79.895)
    assert val is not None
    assert 10.0 < val < 50.0
    assert n == 2


def test_idw_fuera_de_radio_devuelve_none():
    estaciones = [
        EstacionTest(lat=-1.0, lon=-78.0, precip_24h_mm=100.0),
    ]
    val, n = interpolar_idw(estaciones, lat=-2.19, lon=-79.89, radio_km=25.0)
    assert val is None
    assert n == 0
