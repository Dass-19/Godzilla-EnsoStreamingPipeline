"""
Módulo de interpolación espacial por IDW (Inverse Distance Weighting).

Python puro sin dependencias de Spark, igual que `risk_index.py`: lo importa
el job de PySpark (`spark_streaming_job.py`) para resolver `precip_24h_mm` por
zona a partir de las estaciones INAMHI vigentes.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Protocol, TypeVar


class PuntoConCoordenadas(Protocol):
    lat: float
    lon: float
    precip_24h_mm: float


T = TypeVar("T", bound=PuntoConCoordenadas)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula la distancia en kilómetros entre dos puntos en la Tierra."""
    r_earth = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r_earth * c


def interpolar_idw(
    estaciones: Sequence[T],
    lat: float,
    lon: float,
    potencia: float = 2.0,
    radio_km: float = 25.0,
    minimo_estaciones: int = 1,
) -> tuple[float | None, int]:
    """
    Interpola el valor de lluvia en (lat, lon) usando estaciones cercanas.

    Devuelve una tupla `(valor_interpolado, n_estaciones_usadas)`. Si no hay
    estaciones dentro de `radio_km` o no se alcanza `minimo_estaciones`, devuelve
    `(None, 0)`.
    """
    if not estaciones:
        return None, 0

    pesos_valores: list[tuple[float, float]] = []

    for est in estaciones:
        dist = haversine_km(lat, lon, est.lat, est.lon)
        if dist > radio_km:
            continue

        # Si coincide exactamente con una estación, devolvemos su valor directo
        if dist < 1e-6:
            return float(est.precip_24h_mm), 1

        peso = 1.0 / (dist**potencia)
        pesos_valores.append((peso, float(est.precip_24h_mm)))

    if len(pesos_valores) < minimo_estaciones:
        return None, 0

    suma_pesos = sum(p for p, _ in pesos_valores)
    suma_ponderada = sum(p * v for p, v in pesos_valores)

    if suma_pesos <= 0:
        return None, 0

    return round(suma_ponderada / suma_pesos, 2), len(pesos_valores)
