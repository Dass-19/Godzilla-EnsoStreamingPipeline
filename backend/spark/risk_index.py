"""
Índice compuesto de riesgo de inundación por zona.

Combina, todos normalizados a [0, 1]:
  - precip_24h_norm: acumulado de lluvia en 24h relativo a un umbral de saturación
  - marea_norm: altura de marea relativa al rango pleamar-bajamar del estuario
  - embalse_norm: cota del embalse Daule-Peripa dentro de su rango de operación
  - factor_topografico: derivado de cota + pendiente + cercanía a estero (estático por zona)
  - historico_flag: 1.0 si la zona tiene antecedentes de inundación, 0 si no

La idea clave del proyecto (objetivo específico 5 del enunciado) es que
marea alta y lluvia intensa se refuerzan: con marea alta el sistema pluvial
pierde capacidad de descarga por gravedad hacia el estuario, así que el
peso de la lluvia se amplifica cuando la marea también está alta. Eso se
modela con un término de interacción explícito, no solo una suma lineal.

Pesos y umbrales son deliberadamente simples y documentados para que el
informe técnico pueda justificarlos y, si hace falta, calibrarlos contra
las zonas históricamente inundables como validación.
"""

from __future__ import annotations

from dataclasses import dataclass

# Umbrales de normalización (ajustables; documentar la justificación en el informe)
PRECIP_24H_SATURACION_MM = 150.0     # acumulado que ya se considera crítico en 24h
MAREA_MIN_M = 0.4                    # bajamar típica del modelo armónico
MAREA_MAX_M = 3.6                    # pleamar típica del modelo armónico

CAUDAL_BASE_M3S = 400.0              # caudal base típico del río Guayas
CAUDAL_CRECIDA_M3S = 1800.0          # caudal de crecida crítica
SATURACION_SUELO_MM = 120.0          # API acumulado para saturación de suelo
ANOMALIA_NINO12_EXTREMA_C = 4.0      # anomalía costera de El Niño de gran magnitud (°C)

# La fuente (CELEC EP) publica la cota del embalse en msnm. Se conserva como referencia.
EMBALSE_NIVEL_MIN_MSNM = 70.0
EMBALSE_NIVEL_ALERTA_MSNM = 85.0

# Pesos base re-normalizados (suman exactamente 1.00)
PESO_PRECIP = 0.28
PESO_MAREA = 0.12
PESO_RIO = 0.15
PESO_SUELO = 0.10
PESO_TOPOGRAFIA = 0.20
PESO_HISTORICO = 0.15

# Factores de interacción
FACTOR_INTERACCION_LLUVIA_MAREA = 0.15
FACTOR_INTERACCION_RIO_MAREA = 0.15
FACTOR_AMPLIFICACION_ENSO = 0.10

SLOPE_CLASS_A_FACTOR = {
    "plana": 1.0,
    "suave": 0.6,
    "moderada": 0.3,
    "pronunciada": 0.1,
}


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


@dataclass
class FactorTopografico:
    cota_media_msnm: float
    pendiente_clase: str
    cercania_estero_m: float

    def normalizado(self) -> float:
        # cotas bajas (<=5m) y cercanía a estero (<=200m) aumentan el factor
        factor_cota = _clip01(1.0 - self.cota_media_msnm / 20.0)
        factor_pendiente = SLOPE_CLASS_A_FACTOR.get(self.pendiente_clase, 0.5)
        factor_cercania = _clip01(1.0 - self.cercania_estero_m / 1000.0)
        return _clip01(0.5 * factor_cota + 0.3 * factor_pendiente + 0.2 * factor_cercania)


def normalizar_precip(precip_24h_mm: float) -> float:
    return _clip01(precip_24h_mm / PRECIP_24H_SATURACION_MM)


def normalizar_marea(altura_marea_m: float) -> float:
    return _clip01((altura_marea_m - MAREA_MIN_M) / (MAREA_MAX_M - MAREA_MIN_M))


def normalizar_embalse(nivel_embalse_msnm: float) -> float:
    rango = EMBALSE_NIVEL_ALERTA_MSNM - EMBALSE_NIVEL_MIN_MSNM
    return _clip01((nivel_embalse_msnm - EMBALSE_NIVEL_MIN_MSNM) / rango)


def normalizar_caudal(caudal_m3s: float) -> float:
    rango = CAUDAL_CRECIDA_M3S - CAUDAL_BASE_M3S
    return _clip01((caudal_m3s - CAUDAL_BASE_M3S) / rango)


def normalizar_saturacion(saturacion_antecedente_mm: float) -> float:
    return _clip01(saturacion_antecedente_mm / SATURACION_SUELO_MM)


def normalizar_anomalia_nino12(anomalia_c: float) -> float:
    return _clip01(anomalia_c / ANOMALIA_NINO12_EXTREMA_C)


def calcular_exposicion(poblacion: int | float, poblacion_maxima: int | float = 200000) -> float:
    return _clip01(float(poblacion) / float(poblacion_maxima))


def calcular_indice_riesgo(
    precip_24h_mm: float,
    altura_marea_m: float,
    nivel_embalse_msnm: float = 70.0,
    cota_media_msnm: float = 5.0,
    pendiente_clase: str = "plana",
    cercania_estero_m: float = 200.0,
    historicamente_inundable: bool = False,
    caudal_rio_m3s: float = 500.0,
    saturacion_antecedente_mm: float = 0.0,
    anomalia_nino12_c: float = 0.0,
    poblacion: int = 0,
) -> dict:
    precip_norm = normalizar_precip(precip_24h_mm)
    marea_norm = normalizar_marea(altura_marea_m)
    embalse_norm = normalizar_embalse(nivel_embalse_msnm)
    caudal_norm = normalizar_caudal(caudal_rio_m3s)
    suelo_norm = normalizar_saturacion(saturacion_antecedente_mm)
    enso12_norm = normalizar_anomalia_nino12(anomalia_nino12_c)
    topo_norm = FactorTopografico(cota_media_msnm, pendiente_clase, cercania_estero_m).normalizado()
    historico_norm = 1.0 if historicamente_inundable else 0.0

    base = (
        PESO_PRECIP * precip_norm
        + PESO_MAREA * marea_norm
        + PESO_RIO * caudal_norm
        + PESO_SUELO * suelo_norm
        + PESO_TOPOGRAFIA * topo_norm
        + PESO_HISTORICO * historico_norm
    )

    interaccion = (
        FACTOR_INTERACCION_LLUVIA_MAREA * precip_norm * marea_norm
        + FACTOR_INTERACCION_RIO_MAREA * caudal_norm * marea_norm
        + FACTOR_AMPLIFICACION_ENSO * enso12_norm * precip_norm
    )

    score = _clip01(base + interaccion)
    nivel = _clasificar_nivel(score)
    exposicion_norm = calcular_exposicion(poblacion)
    indice_impacto = round(score * exposicion_norm, 4)

    return {
        "indice_riesgo": round(score, 4),
        "nivel_riesgo": nivel,
        "exposicion_norm": round(exposicion_norm, 4),
        "indice_impacto": indice_impacto,
        "componentes": {
            "precip_norm": round(precip_norm, 4),
            "marea_norm": round(marea_norm, 4),
            "embalse_norm": round(embalse_norm, 4),
            "caudal_norm": round(caudal_norm, 4),
            "suelo_norm": round(suelo_norm, 4),
            "topografia_norm": round(topo_norm, 4),
            "historico_norm": historico_norm,
            "interaccion": round(interaccion, 4),
        },
    }


def _clasificar_nivel(score: float) -> str:
    if score < 0.25:
        return "bajo"
    if score < 0.5:
        return "medio"
    if score < 0.75:
        return "alto"
    return "critico"
