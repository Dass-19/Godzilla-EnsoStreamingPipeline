"""
Contrato de datos entre productores y consumidores (job de Spark / API).

Este módulo es la ÚNICA definición del shape de los payloads que alimentan el
índice de riesgo de inundación. Lo importan los dos lados:

  - los productores, para CONSTRUIR el payload (`construir_*`)
  - el job de Spark, para LEERLO (`parse_*`)

Ninguna función de aquí levanta excepciones por datos ausentes: devuelven
`None`, y es responsabilidad del llamador registrar la procedencia
(`real` vs `default`) en la salida.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Marcadores de procedencia que se persisten junto al índice de riesgo.
ORIGEN_REAL = "real"
ORIGEN_DEFAULT = "default"

# NASA POWER usa -999 como centinela de "sin dato" en vez de null.
CENTINELA_NASA_POWER = -999.0

# Topics de los que se leen las entradas dinámicas del índice.
TOPIC_MAREA = "mareas-inocar"
TOPIC_EMBALSE = "nivel-embalse-celec"
TOPIC_PRECIPITACION = "nasa-power-data"
TOPIC_PRECIP_ESTACIONES = "inamhi-precipitacion"
TOPIC_PRECIP_PRONOSTICO = "pronostico-precipitacion"
TOPIC_MAREA_OBSERVADA = "marea-observada"
TOPIC_CAUDAL = "caudal-geoglows"
TOPIC_SST_SEMANAL = "sst-semanal"

# Nombres de fuente (= carpeta bajo /enso_data/raw/) correspondientes.
FUENTE_MAREA = "inocar_mareas"
FUENTE_EMBALSE = "celec_embalse"
FUENTE_PRECIPITACION = "nasa_power"
FUENTE_PRECIP_ESTACIONES = "inamhi_precipitacion"
FUENTE_PRECIP_PRONOSTICO = "pronostico_precipitacion"
FUENTE_MAREA_OBSERVADA = "marea_observada"
FUENTE_CAUDAL = "caudal_geoglows"
FUENTE_SST_SEMANAL = "sst_semanal"


@dataclass(frozen=True)
class LluviaEstacion:
    """
    Estación meteorológica de INAMHI con acumulación reciente en mm.
    """

    id_estacion: str
    codigo: str
    lat: float
    lon: float
    precip_24h_mm: float
    fecha_ultimo_dato: str


@dataclass(frozen=True)
class Lectura:
    """
    Una entrada del índice de riesgo junto con su procedencia.

    `origen` vale `"real"` si el valor vino de una fuente y `"default"` si es
    el valor de respaldo. Se persiste en el parquet para que una fila
    calculada con tres defaults no sea indistinguible de una fila real.
    """

    valor: float = 0.0
    origen: str = ""
    detalle: str = ""

    @property
    def es_real(self) -> bool:
        return self.origen == ORIGEN_REAL

    @classmethod
    def real(cls, valor: float, detalle: str = "") -> "Lectura":
        return cls(valor=float(valor), origen=ORIGEN_REAL, detalle=detalle)

    @classmethod
    def por_defecto(cls, valor: float, detalle: str = "") -> "Lectura":
        return cls(valor=float(valor), origen=ORIGEN_DEFAULT, detalle=detalle)

    @classmethod
    def desde(
        cls,
        valor: float | None,
        respaldo: float,
        detalle_default: str = "",
    ) -> "Lectura":
        """Envuelve el resultado de un `parse_*`: None -> respaldo marcado."""
        if valor is None:
            return cls.por_defecto(respaldo, detalle_default)
        return cls.real(valor)


def _a_float(valor: Any) -> float | None:
    """Convierte a float sin levantar; None/''/no numérico -> None."""
    if valor is None or isinstance(valor, bool):
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    if numero != numero:  # NaN
        return None
    return numero


# ---------------------------------------------------------------------------
# Marea — INOCAR (topic `mareas-inocar`)
# ---------------------------------------------------------------------------

def construir_marea(
    altura_m: float,
    tendencia: str,
    pleamar: bool,
    fuente: str,
    puerto: str = "Guayaquil",
) -> dict:
    """Payload que publica `producer_inocar_mareas`."""
    return {
        "fuente": fuente,
        "puerto": puerto,
        "altura_marea_m": round(float(altura_m), 3),
        "tendencia": tendencia,
        "pleamar": bool(pleamar),
    }


def parse_marea(payload: dict) -> float | None:
    """Altura de marea en metros, o None si el payload no la trae."""
    if not isinstance(payload, dict):
        return None
    return _a_float(payload.get("altura_marea_m"))


# ---------------------------------------------------------------------------
# Embalse — CELEC EP Daule-Peripa (topic `nivel-embalse-celec`)
# ---------------------------------------------------------------------------

def construir_embalse(
    nivel_msnm: float,
    descripcion: str,
    url_fuente: str | None,
    fecha_noticia: str | None,
    fuente: str = "CELEC_wp_api",
    nivel_maximo_msnm: float | None = None,
) -> dict:
    """
    Payload que publica `producer_celec_embalse`.

    Ojo con las unidades: `nivel_msnm` es una COTA (metros sobre el nivel del
    mar, ~70-85 para Daule-Peripa), no un caudal. La fuente no publica caudal
    de descarga, así que el índice de riesgo se calcula sobre la cota.
    """
    registro = {
        "fuente": fuente,
        "embalse": "Daule-Peripa",
        "descripcion": descripcion,
        "url_fuente": url_fuente,
        "fecha_noticia": fecha_noticia,
        "nivel_msnm": float(nivel_msnm),
    }
    if nivel_maximo_msnm is not None:
        registro["nivel_maximo_msnm"] = float(nivel_maximo_msnm)
    return registro


def parse_embalse(payload: dict) -> float | None:
    """Cota del embalse en msnm, o None si el payload no la trae."""
    if not isinstance(payload, dict):
        return None
    return _a_float(payload.get("nivel_msnm"))


# ---------------------------------------------------------------------------
# Precipitación — NASA POWER en Guayaquil (topic `nasa-power-data`)
# ---------------------------------------------------------------------------
#
# Se usa NASA POWER y no Open-Meteo: el productor de Open-Meteo consulta la
# región Niño 3.4 (lat 0, lon -143, Pacífico central), que no dice nada sobre
# la lluvia en Guayaquil. NASA POWER sí consulta el punto (-2.1, -79.9).
# INAMHI, la otra candidata, expone pronóstico cualitativo (`rain: bool`) pero
# no un acumulado en mm.

def construir_precipitacion_diaria(
    fecha: str,
    precipitacion_mm: float | None,
    **otras_variables: Any,
) -> dict:
    """Un registro diario de `producer_nasa_power` (dentro de `data`)."""
    registro = {"date": fecha, "precipitation_mm": precipitacion_mm}
    registro.update(otras_variables)
    return registro


def parse_precipitacion(payload: dict) -> float | None:
    """
    Acumulado de lluvia en mm del día más reciente del payload de NASA POWER.

    Descarta el centinela -999 y los negativos, y recorre los días de más
    reciente a más antiguo: la serie de NASA POWER tiene varios días de
    latencia y los últimos suelen venir sin dato.
    """
    if not isinstance(payload, dict):
        return None

    registros = payload.get("data")
    if not isinstance(registros, list):
        return None

    fechados = [r for r in registros if isinstance(r, dict)]
    fechados.sort(key=lambda r: str(r.get("date", "")), reverse=True)

    for registro in fechados:
        valor = _a_float(registro.get("precipitation_mm"))
        if valor is None or valor <= CENTINELA_NASA_POWER or valor < 0:
            continue
        return valor

    return None


# ---------------------------------------------------------------------------
# Estaciones INAMHI — Precipitación observada (topic `inamhi-precipitacion`)
# ---------------------------------------------------------------------------

def construir_lluvia_estacion(
    id_estacion: str,
    codigo: str,
    lat: float,
    lon: float,
    precip_24h_mm: float,
    fecha_ultimo_dato: str,
    serie_diaria_15d: list[dict] | None = None,
) -> dict:
    """Payload de una estación meteorológica de INAMHI."""
    return {
        "id_estacion": str(id_estacion),
        "codigo": str(codigo),
        "lat": float(lat),
        "lon": float(lon),
        "precip_24h_mm": float(precip_24h_mm),
        "fecha_ultimo_dato": str(fecha_ultimo_dato),
        "serie_diaria_15d": serie_diaria_15d or [],
    }


def parse_lluvia_estaciones(
    payload: dict, max_antiguedad_horas: int = 72
) -> list[LluviaEstacion]:
    """
    Lista de estaciones con lluvia reciente válida.

    Descarta estaciones sin coordenadas, valores negativos o cuya fecha del
    último dato exceda `max_antiguedad_horas`.
    """
    if not isinstance(payload, dict):
        return []

    estaciones = payload.get("estaciones")
    if not isinstance(estaciones, list):
        return []

    resultado: list[LluviaEstacion] = []
    for est in estaciones:
        if not isinstance(est, dict):
            continue
        lat = _a_float(est.get("lat"))
        lon = _a_float(est.get("lon"))
        precip = _a_float(est.get("precip_24h_mm"))

        if lat is None or lon is None or precip is None or precip < 0:
            continue

        id_est = str(est.get("id_estacion", ""))
        cod = str(est.get("codigo", ""))
        fecha = str(est.get("fecha_ultimo_dato", ""))

        resultado.append(
            LluviaEstacion(
                id_estacion=id_est,
                codigo=cod,
                lat=lat,
                lon=lon,
                precip_24h_mm=precip,
                fecha_ultimo_dato=fecha,
            )
        )

    return resultado


def parse_saturacion_antecedente(payload: dict, k: float = 0.9) -> float | None:
    """
    Índice de Precipitación Antecedente (API = Σ k^i * P_i) sobre 15 días.

    Proxy empírico de saturación de suelo. Devuelve el máximo API entre las
    estaciones de INAMHI válidas presentes en el payload.
    """
    if not isinstance(payload, dict):
        return None

    estaciones = payload.get("estaciones")
    if not isinstance(estaciones, list):
        return None

    max_api: float | None = None
    for est in estaciones:
        if not isinstance(est, dict):
            continue
        serie = est.get("serie_diaria_15d")
        if not isinstance(serie, list) or not serie:
            continue

        api_valor = 0.0
        dias_contados = 0
        for i, dia in enumerate(serie, start=1):
            if not isinstance(dia, dict):
                continue
            precip = _a_float(dia.get("precip_mm"))
            if precip is None or precip < 0:
                continue
            api_valor += (k**i) * precip
            dias_contados += 1

        if dias_contados > 0:
            if max_api is None or api_valor > max_api:
                max_api = api_valor

    return max_api


# ---------------------------------------------------------------------------
# Pronóstico de precipitación — Open-Meteo (topic `pronostico-precipitacion`)
# ---------------------------------------------------------------------------

def construir_pronostico_precip(
    fecha: str,
    lat: float,
    lon: float,
    precip_sum_mm: float,
    precip_probability_max: float | None = None,
    horizonte_h: int = 24,
) -> dict:
    """Payload de pronóstico de lluvia de Open-Meteo."""
    res = {
        "fecha": str(fecha),
        "lat": float(lat),
        "lon": float(lon),
        "horizonte_h": int(horizonte_h),
        "precip_sum_mm": float(precip_sum_mm),
    }
    if precip_probability_max is not None:
        res["precip_probability_max"] = float(precip_probability_max)
    return res


def parse_pronostico_precip(
    payload: dict, horizonte_h: int = 24
) -> float | None:
    """Acumulado de lluvia pronosticado en mm para el horizonte pedido."""
    if not isinstance(payload, dict):
        return None
    val = _a_float(payload.get("precip_sum_mm"))
    if val is None or val < 0:
        return None
    return val


# ---------------------------------------------------------------------------
# Marea observada — Mareógrafo IOC `gyer` (topic `marea-observada`)
# ---------------------------------------------------------------------------

def construir_marea_observada(
    altura_m: float,
    estacion: str = "gyer",
    puerto: str = "Guayaquil - Rio Guayas",
    sensor: str = "radar",
    fecha_utc: str | None = None,
) -> dict:
    """Payload de marea real observada por sensor mareográfico IOC."""
    return {
        "estacion": estacion,
        "puerto": puerto,
        "sensor": sensor,
        "altura_marea_m": round(float(altura_m), 3),
        "fecha_utc": fecha_utc,
    }


def parse_marea_observada(payload: dict) -> float | None:
    """Altura de marea observada en metros, o None si no viene en el payload."""
    if not isinstance(payload, dict):
        return None
    return _a_float(payload.get("altura_marea_m"))


# ---------------------------------------------------------------------------
# Caudal fluvial — GEOGLOWS (topic `caudal-geoglows`)
# ---------------------------------------------------------------------------

def construir_caudal(
    river_id: int,
    caudal_m3s: float,
    tramo: str = "Guayas",
    caudal_lower_m3s: float | None = None,
    caudal_upper_m3s: float | None = None,
) -> dict:
    """Payload de caudal de río de GEOGLOWS v2 (ECMWF)."""
    res = {
        "river_id": int(river_id),
        "tramo": str(tramo),
        "caudal_m3s": round(float(caudal_m3s), 2),
    }
    if caudal_lower_m3s is not None:
        res["caudal_lower_m3s"] = round(float(caudal_lower_m3s), 2)
    if caudal_upper_m3s is not None:
        res["caudal_upper_m3s"] = round(float(caudal_upper_m3s), 2)
    return res


def parse_caudal(payload: dict) -> float | None:
    """Caudal fluvial del río Guayas en m3/s, o None si no está presente."""
    if not isinstance(payload, dict):
        return None
    val = _a_float(payload.get("caudal_m3s"))
    if val is None or val < 0:
        return None
    return val


# ---------------------------------------------------------------------------
# SST Semanal — NOAA CPC `wksst9120.for` (topic `sst-semanal`)
# ---------------------------------------------------------------------------

def construir_sst_semanal(
    fecha_semana: str,
    sst_nino12_c: float,
    anomalia_nino12_c: float,
    **otras_regiones: Any,
) -> dict:
    """Payload de temperatura e índice de anomalía semanal de NOAA CPC."""
    res = {
        "fecha_semana": str(fecha_semana),
        "sst_nino12_c": round(float(sst_nino12_c), 2),
        "anomalia_nino12_c": round(float(anomalia_nino12_c), 2),
    }
    res.update(otras_regiones)
    return res


def parse_anomalia_nino12(payload: dict) -> float | None:
    """Anomalía de temperatura en °C de la región Niño 1+2."""
    if not isinstance(payload, dict):
        return None
    return _a_float(payload.get("anomalia_nino12_c"))

