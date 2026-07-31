"""
Contrato de datos entre productores y consumidores (job de Spark / API).

Este módulo es la ÚNICA definición del shape de los payloads que alimentan el
índice de riesgo de inundación. Lo importan los dos lados:

  - los productores, para CONSTRUIR el payload (`construir_*`)
  - el job de Spark, para LEERLO (`parse_*`)

Por qué existe: el acoplamiento entre productor y consumidor era por strings
anidados escritos a mano en cada lado. Los tres accesos del job apuntaban a
rutas que ningún productor emitía nunca:

    Spark leía                                     Productor emitía
    ---------------------------------------------  ---------------------------
    data.mareas.pleamar.altura_m                   altura_marea_m (plano)
    pronostico_diario.pronostico[0].precipitacion_mm  (INAMHI no expone lluvia)
    nivel_msnm -> parámetro caudal_descargado_m3s  nivel_msnm (cota, no caudal)

Como cada acceso estaba envuelto en `try/except -> valor por defecto`, el
índice de riesgo quedó constante por zona durante toda la vida del pipeline,
sin un solo error en los logs. Con este módulo, un cambio de shape rompe los
tests de contrato (`tests/test_contracts.py`) en vez de degradar en silencio.

Ninguna función de aquí levanta excepciones por datos ausentes: devuelven
`None`, y es responsabilidad del llamador registrar la procedencia
(`real` vs `default`) en la salida.
"""

from dataclasses import dataclass
from typing import Any

# Marcadores de procedencia que se persisten junto al índice de riesgo.
ORIGEN_REAL = "real"
ORIGEN_DEFAULT = "default"

# NASA POWER usa -999 como centinela de "sin dato" en vez de null.
CENTINELA_NASA_POWER = -999.0

# Topics de los que se leen las tres entradas dinámicas del índice.
TOPIC_MAREA = "mareas-inocar"
TOPIC_EMBALSE = "nivel-embalse-celec"
TOPIC_PRECIPITACION = "nasa-power-data"

# Nombres de fuente (= carpeta bajo /enso_data/raw/) correspondientes.
FUENTE_MAREA = "inocar_mareas"
FUENTE_EMBALSE = "celec_embalse"
FUENTE_PRECIPITACION = "nasa_power"


@dataclass(frozen=True)
class Lectura:
    """
    Una entrada del índice de riesgo junto con su procedencia.

    `origen` vale `"real"` si el valor vino de una fuente y `"default"` si es
    el valor de respaldo. Se persiste en el parquet para que una fila
    calculada con tres defaults no sea indistinguible de una fila real.
    """

    valor: float
    origen: str
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
