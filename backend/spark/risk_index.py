"""
Índice compuesto de riesgo de inundación por zona.

Combina, todos normalizados a [0, 1]:
  - precip_24h_norm: acumulado de lluvia en 24h relativo a un umbral de saturación
  - marea_norm: altura de marea relativa al rango pleamar-bajamar del estuario
  - embalse_norm: nivel/descarga del embalse Daule-Peripa relativo a su umbral de alerta
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

from dataclasses import dataclass

# Umbrales de normalización (ajustables; documentar la justificación en el informe)
PRECIP_24H_SATURACION_MM = 150.0     # acumulado que ya se considera crítico en 24h
MAREA_MIN_M = 0.4                    # bajamar típica del modelo armónico
MAREA_MAX_M = 3.6                    # pleamar típica del modelo armónico
EMBALSE_NIVEL_ALERTA_MSNM = 85.0     # nivel crítico de embalse Daule-Peripa

PESO_PRECIP = 0.35
PESO_MAREA = 0.15
PESO_EMBALSE = 0.15
PESO_TOPOGRAFIA = 0.20
PESO_HISTORICO = 0.15

# Amplifica el riesgo cuando lluvia y marea alta coinciden (objetivo 5 del enunciado)
FACTOR_INTERACCION_LLUVIA_MAREA = 0.25

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


def normalizar_embalse(caudal_descargado_m3s: float) -> float:
    return _clip01(caudal_descargado_m3s / EMBALSE_NIVEL_ALERTA_MSNM)


def calcular_indice_riesgo(
    precip_24h_mm: float,
    altura_marea_m: float,
    caudal_descargado_m3s: float,
    cota_media_msnm: float,
    pendiente_clase: str,
    cercania_estero_m: float,
    historicamente_inundable: bool,
) -> dict:
    precip_norm = normalizar_precip(precip_24h_mm)
    marea_norm = normalizar_marea(altura_marea_m)
    embalse_norm = normalizar_embalse(caudal_descargado_m3s)
    topo_norm = FactorTopografico(cota_media_msnm, pendiente_clase, cercania_estero_m).normalizado()
    historico_norm = 1.0 if historicamente_inundable else 0.0

    base = (
        PESO_PRECIP * precip_norm
        + PESO_MAREA * marea_norm
        + PESO_EMBALSE * embalse_norm
        + PESO_TOPOGRAFIA * topo_norm
        + PESO_HISTORICO * historico_norm
    )

    # Término de interacción: solo se activa si tanto la lluvia como la marea son altas
    interaccion = FACTOR_INTERACCION_LLUVIA_MAREA * precip_norm * marea_norm

    score = _clip01(base + interaccion)
    nivel = _clasificar_nivel(score)

    return {
        "indice_riesgo": round(score, 4),
        "nivel_riesgo": nivel,
        "componentes": {
            "precip_norm": round(precip_norm, 4),
            "marea_norm": round(marea_norm, 4),
            "embalse_norm": round(embalse_norm, 4),
            "topografia_norm": round(topo_norm, 4),
            "historico_norm": historico_norm,
            "interaccion_lluvia_marea": round(interaccion, 4),
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
