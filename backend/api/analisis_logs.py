"""
Agregación de los logs de producers en indicadores para /api/logs/resumen.

Python puro, sin FastAPI ni HDFS: CI no instala las dependencias de la API, así
que la lógica que merece test vive acá y no en el router.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from datetime import datetime

# Los tres literales que `run_loop` garantiza en todo productor que pasa por él
# (backend/producers/common/kafka_client.py).
RE_CICLO = re.compile(
    r"^ciclo topic=(?P<topic>\S+) obtenidos=(?P<obtenidos>\d+) publicados=(?P<publicados>\d+)$"
)
RE_CICLO_VACIO = re.compile(r"^ciclo sin registros topic=(?P<topic>\S+)$")
RE_INTERVALO = re.compile(
    r"^iniciando loop de productor topic=(?P<topic>\S+) intervalo=(?P<intervalo>\d+)s$"
)

FORMATO_FECHA = "%Y-%m-%d %H:%M:%S,%f"

# Degradaciones que la línea de ciclo NO refleja: el ciclo se cierra "sano"
# mientras el dato publicado es un respaldo. Al agregar un productor que degrade,
# sumar acá su literal o quedará indistinguible de uno sano.
DEGRADACIONES = [
    (
        "modelo_armonico",
        re.compile(r"se usa el modelo armónico"),
        "Marea calculada con el modelo armónico, no con el PDF de INOCAR",
    ),
    (
        "precip_cero",
        re.compile(r"se degrada a 0 mm"),
        "Precipitación satelital degradada a 0 mm por falta de imágenes",
    ),
    (
        "estacion_respaldo",
        re.compile(r"respaldo puna"),
        "Mareógrafo principal sin dato, usando la estación de respaldo",
    ),
    (
        "fuente_vacia",
        re.compile(
            r"sin datos vigentes|ninguna estación devolvió datos|no devolvió features"
            r"|sin registros parseables|payload sin datos|respuesta sin"
        ),
        "La fuente respondió sin datos utilizables",
    ),
    (
        "http_error",
        re.compile(r"respondió \d{3}|devolvió HTTP \d{3}"),
        "La fuente respondió con un código HTTP de error",
    ),
    (
        "capa_conservada",
        re.compile(r"se conserva la capa anterior"),
        "Capa geográfica no actualizada; se conservó la versión previa",
    ),
    (
        "sin_arranque",
        re.compile(r"no arranca el loop"),
        "El productor no llegó a iniciar su ciclo",
    ),
]

# Mayor gana. `degradado` por encima de `atrasado` a propósito: un dato sintético
# entrando puntualmente es peor que uno real que llega tarde.
SEVERIDAD = {"ok": 0, "atrasado": 1, "degradado": 2, "error": 3, "sin_senal": 4}

# Múltiplo de la cadencia propia a partir del cual se considera atrasado.
FACTOR_ATRASO = 2


def _a_datetime(fecha: str) -> datetime | None:
    try:
        return datetime.strptime(fecha, FORMATO_FECHA)
    except (ValueError, TypeError):
        return None


def resumir_producer(nombre: str, registros: list[dict], ahora: datetime) -> dict:
    """Indicadores de un producer a partir de sus líneas ya parseadas."""
    niveles = Counter(r.get("nivel", "") for r in registros)
    ciclos_ok = ciclos_vacios = obtenidos = publicados = 0
    cadencia_s: int | None = None
    marcas: list[datetime] = []
    degradaciones: dict[str, str] = {}

    for r in registros:
        mensaje = r.get("mensaje", "")
        if m := RE_CICLO.match(mensaje):
            ciclos_ok += 1
            obtenidos += int(m["obtenidos"])
            publicados += int(m["publicados"])
        elif RE_CICLO_VACIO.match(mensaje):
            ciclos_vacios += 1
        elif m := RE_INTERVALO.match(mensaje):
            cadencia_s = int(m["intervalo"])

        for clave, patron, descripcion in DEGRADACIONES:
            if patron.search(mensaje):
                degradaciones[clave] = descripcion

        if (dt := _a_datetime(r.get("fecha", ""))) is not None:
            marcas.append(dt)

    ultimo = max(marcas) if marcas else None
    # La línea `intervalo=` sale una sola vez por proceso y puede caer fuera de la
    # ventana; se infiere de la cadencia observada. Sin ninguna de las dos no se
    # evalúa atraso: mejor no decir nada que levantar una falsa alarma.
    if cadencia_s is None and len(marcas) >= 3:
        orden = sorted(marcas)
        huecos = [(b - a).total_seconds() for a, b in zip(orden, orden[1:], strict=False)]
        cadencia_s = int(statistics.median(huecos)) or None

    atraso_s = (ahora - ultimo).total_seconds() if ultimo else None
    atrasado = bool(cadencia_s and atraso_s and atraso_s > cadencia_s * FACTOR_ATRASO)

    if not registros:
        estado = "sin_senal"
    elif niveles.get("ERROR") or niveles.get("CRITICAL"):
        estado = "error"
    elif degradaciones:
        estado = "degradado"
    elif atrasado:
        estado = "atrasado"
    else:
        estado = "ok"

    return {
        "producer": nombre,
        "estado": estado,
        "ultimo_evento": ultimo.isoformat() if ultimo else None,
        "atraso_s": int(atraso_s) if atraso_s is not None else None,
        "cadencia_s": cadencia_s,
        "ciclos_ok": ciclos_ok,
        "ciclos_vacios": ciclos_vacios,
        "registros_obtenidos": obtenidos,
        # >0 significa que Kafka rechazó lo que la fuente sí entregó: separa un
        # problema de infraestructura de uno de la fuente.
        "registros_publicados": publicados,
        "no_publicados": obtenidos - publicados,
        "errores": niveles.get("ERROR", 0) + niveles.get("CRITICAL", 0),
        "advertencias": niveles.get("WARNING", 0),
        "total_lineas": len(registros),
        "degradaciones": sorted(degradaciones.values()),
    }


def construir_resumen(por_producer: dict[str, list[dict]], ahora: datetime) -> dict:
    """Agrega los indicadores de todos los producers en un solo payload."""
    producers = [resumir_producer(n, regs, ahora) for n, regs in sorted(por_producer.items())]
    producers.sort(key=lambda p: (-SEVERIDAD[p["estado"]], p["producer"]))

    por_hora: dict[str, Counter] = {}
    errores: Counter = Counter()
    for nombre, registros in por_producer.items():
        for r in registros:
            if (dt := _a_datetime(r.get("fecha", ""))) is not None:
                por_hora.setdefault(dt.strftime("%Y-%m-%d %H:00"), Counter())[
                    r.get("nivel", "")
                ] += 1
            if r.get("nivel") in ("ERROR", "CRITICAL"):
                errores[(nombre, r.get("mensaje", ""))] += 1

    estados = Counter(p["estado"] for p in producers)
    return {
        "generado_en": ahora.isoformat(),
        "totales": {
            "producers": len(producers),
            "ok": estados.get("ok", 0),
            "atrasados": estados.get("atrasado", 0),
            "degradados": estados.get("degradado", 0),
            "con_error": estados.get("error", 0),
            "sin_senal": estados.get("sin_senal", 0),
            "ciclos_ok": sum(p["ciclos_ok"] for p in producers),
            "ciclos_vacios": sum(p["ciclos_vacios"] for p in producers),
            "registros_publicados": sum(p["registros_publicados"] for p in producers),
            "errores": sum(p["errores"] for p in producers),
            "advertencias": sum(p["advertencias"] for p in producers),
        },
        "producers": producers,
        "actividad_por_hora": [
            {
                "hora": hora,
                "INFO": conteo.get("INFO", 0),
                "WARNING": conteo.get("WARNING", 0),
                "ERROR": conteo.get("ERROR", 0) + conteo.get("CRITICAL", 0),
            }
            for hora, conteo in sorted(por_hora.items())
        ],
        "top_errores": [
            {"producer": prod, "mensaje": mensaje, "veces": veces}
            for (prod, mensaje), veces in errores.most_common(10)
        ],
    }
