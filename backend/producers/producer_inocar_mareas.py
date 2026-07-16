"""
Productor -> topic 'mareas-inocar'

Fuente real sin API key: INOCAR publica tablas oficiales de predicción de
mareas para el estuario de Guayaquil como PDFs trimestrales públicos.

Este productor descarga el PDF del trimestre actual, extrae el texto con
pdfplumber, reconstruye los eventos de marea por subcolumna del cuadro y
publica la altura interpolada para el instante actual. Si el PDF no está
disponible o cambia de formato, cae a un modelo armónico simplificado.

Además expone `cargar_historico()` para extraer todos los eventos reales
disponibles desde 2022 hasta hoy.
"""

import math
from datetime import datetime, timezone
from io import BytesIO

import pdfplumber
import requests

from common.kafka_client import build_producer, run_loop

TOPIC = "mareas-inocar"
INTERVAL_SECONDS = 15 * 60 * 60

PDF_URL_TEMPLATE = (
    "https://www.inocar.mil.ec/mareas/TM/{anio}/trimestral/"
    "GUAYAQUIL_RIO_{trimestre}.pdf"
)
MESES_POR_TRIMESTRE = {
    1: ["ENERO", "FEBRERO", "MARZO"],
    2: ["ABRIL", "MAYO", "JUNIO"],
    3: ["JULIO", "AGOSTO", "SEPTIEMBRE"],
    4: ["OCTUBRE", "NOVIEMBRE", "DICIEMBRE"],
}
MES_A_NUMERO = {
    "ENERO": 1,
    "FEBRERO": 2,
    "MARZO": 3,
    "ABRIL": 4,
    "MAYO": 5,
    "JUNIO": 6,
    "JULIO": 7,
    "AGOSTO": 8,
    "SEPTIEMBRE": 9,
    "OCTUBRE": 10,
    "NOVIEMBRE": 11,
    "DICIEMBRE": 12,
}
DIA_SEMANA_ABREV = {"LU", "MA", "MI", "JU", "VI", "SA", "DO"}

NIVEL_MEDIO_M = 1.8
AMPLITUD_M2_M = 1.4
AMPLITUD_S2_M = 0.4
PERIODO_M2_H = 12.42
PERIODO_S2_H = 12.0

_cache_eventos: dict[tuple[int, int], list[tuple[datetime, float]]] = {}


def _trimestre_actual(fecha: datetime) -> int:
    return (fecha.month - 1) // 3 + 1


def _descargar_pdf(anio: int, trimestre: int) -> bytes:
    url = PDF_URL_TEMPLATE.format(anio=anio, trimestre=trimestre)
    respuesta = requests.get(
        url,
        timeout=20,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/127.0.0.0 Safari/537.36"
            )
        },
    )
    respuesta.raise_for_status()
    return respuesta.content


def _extraer_texto(pdf_bytes: bytes) -> str:
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        return "\n".join(pagina.extract_text() or "" for pagina in pdf.pages)


def _parsear_eventos(texto: str, anio: int, trimestre: int):
    meses = MESES_POR_TRIMESTRE[trimestre]
    lineas = [linea.strip() for linea in texto.splitlines() if linea.strip()]

    eventos = []
    dias_actuales: list[int | None] = [None, None, None, None, None, None]

    for linea in lineas:
        if (
            linea in meses
            or linea.startswith("TABLA")
            or linea.startswith("GUAYAQUIL")
            or linea.startswith("HORA")
            or linea.startswith("*")
        ):
            continue

        tokens = linea.split()
        grupos = len(tokens) // 3
        if grupos == 0:
            continue

        for columna in range(min(grupos, 6)):
            inicio = columna * 3
            token_1, token_2, token_3 = tokens[inicio:inicio + 3]

            if token_1.isdigit():
                dias_actuales[columna] = int(token_1)
                hhmm = token_2
                altura = float(token_3)
            elif token_1 in DIA_SEMANA_ABREV:
                if dias_actuales[columna] is None:
                    continue
                hhmm = token_2
                altura = float(token_3)
            else:
                continue

            dia = dias_actuales[columna]
            if dia is None:
                continue

            mes_num = MES_A_NUMERO[meses[columna // 2]]
            try:
                fecha = datetime(
                    anio,
                    mes_num,
                    dia,
                    int(hhmm[:2]),
                    int(hhmm[2:]),
                    tzinfo=timezone.utc,
                )
            except ValueError:
                continue

            eventos.append((fecha, altura))

    return sorted(eventos, key=lambda evento: evento[0])


def _interpolar_altura(eventos, ahora: datetime):
    anteriores = [evento for evento in eventos if evento[0] <= ahora]
    posteriores = [evento for evento in eventos if evento[0] > ahora]
    if not anteriores or not posteriores:
        return None

    (t0, h0), (t1, h1) = anteriores[-1], posteriores[0]
    total_segundos = (t1 - t0).total_seconds()
    if total_segundos <= 0:
        return None

    fraccion = (ahora - t0).total_seconds() / total_segundos
    altura_actual = h0 + (h1 - h0) * fraccion
    tendencia = "subiendo" if h1 > h0 else "bajando"
    return {
        "altura_marea_m": altura_actual,
        "tendencia": tendencia,
        "evento_anterior": (t0, h0),
        "evento_siguiente": (t1, h1),
    }


def _modelo_armonico_fallback() -> list[dict]:
    ahora = datetime.now(timezone.utc)
    horas = (
        ahora - datetime(1970, 1, 1, tzinfo=timezone.utc)
    ).total_seconds() / 3600.0

    def _altura(horas_relativas: float) -> float:
        m2 = AMPLITUD_M2_M * math.sin(
            2 * math.pi * horas_relativas / PERIODO_M2_H
        )
        s2 = AMPLITUD_S2_M * math.sin(
            2 * math.pi * horas_relativas / PERIODO_S2_H
        )
        return NIVEL_MEDIO_M + m2 + s2

    altura = _altura(horas)
    altura_en_1h = _altura(horas + 1)
    tendencia = "subiendo" if altura_en_1h > altura else "bajando"

    return [{
        "fuente": "modelo_armonico_fallback",
        "puerto": "Guayaquil",
        "altura_marea_m": round(altura, 3),
        "tendencia": tendencia,
        "pleamar": altura >= (NIVEL_MEDIO_M + 1.0),
    }]


def _iterar_trimestres_desde(anio_inicio: int = 2022):
    ahora = datetime.now(timezone.utc)
    for anio in range(anio_inicio, ahora.year + 1):
        trimestre_final = _trimestre_actual(ahora) if anio == ahora.year else 4
        for trimestre in range(1, trimestre_final + 1):
            yield anio, trimestre


def cargar_historico(anio_inicio: int = 2022) -> list[dict]:
    eventos = []
    for anio, trimestre in _iterar_trimestres_desde(anio_inicio):
        try:
            pdf_bytes = _descargar_pdf(anio, trimestre)
            texto = _extraer_texto(pdf_bytes)
            for fecha, altura in _parsear_eventos(texto, anio, trimestre):
                eventos.append({
                    "fuente": "INOCAR_pdf",
                    "anio": anio,
                    "trimestre": trimestre,
                    "altura_marea_m": round(altura, 3),
                })
        except Exception as error:
            print(f"[salta] {anio}-T{trimestre}: {error}")

    return eventos


def fetch_marea() -> list[dict]:
    ahora = datetime.now(timezone.utc)
    anio, trimestre = ahora.year, _trimestre_actual(ahora)

    try:
        clave_cache = (anio, trimestre)
        if clave_cache not in _cache_eventos:
            pdf_bytes = _descargar_pdf(anio, trimestre)
            texto = _extraer_texto(pdf_bytes)
            _cache_eventos[clave_cache] = _parsear_eventos(
                texto,
                anio,
                trimestre,
            )

        eventos = _cache_eventos[clave_cache]
        resultado = _interpolar_altura(eventos, ahora)
        if resultado is None:
            return _modelo_armonico_fallback()

        altura = resultado["altura_marea_m"]
        t0, h0 = resultado["evento_anterior"]
        t1, h1 = resultado["evento_siguiente"]
        es_pleamar = altura >= max(h0, h1) - 0.3

        return [{
            "fuente": "INOCAR_pdf",
            "puerto": "Guayaquil",
            "altura_marea_m": round(altura, 3),
            "tendencia": resultado["tendencia"],
            "pleamar": bool(es_pleamar),
        }]
    except Exception:
        return _modelo_armonico_fallback()


if __name__ == "__main__":
    producer = build_producer()
    run_loop(producer, TOPIC, fetch_marea, INTERVAL_SECONDS)
