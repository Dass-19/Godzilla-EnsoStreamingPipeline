"""
Productor -> topic 'alertas-sngr'

Fuente real, SIN API KEY: el sitio de la Secretaría Nacional de Gestión de
Riesgos (gestionderiesgos.gob.ec) corre sobre WordPress, y WordPress
expone por defecto (desde la versión 4.7, sin necesidad de plugin) una
REST API pública de solo lectura en /wp-json/wp/v2/posts. La usamos para
traer las publicaciones más recientes relacionadas a alertas/lluvias en
la provincia de Guayas, en vez de intentar un scraping frágil de HTML.

Documentación general de la API: https://developer.wordpress.org/rest-api/

Este productor:
    1. Pide los últimos posts que contengan alguna palabra clave de
       riesgo/alerta.
    2. Extrae cantón/provincia/severidad de forma heurística a partir del
        título y el contenido, buscando nombres de cantones de la cuenca del
        Guayas y palabras como "roja"/"naranja"/"amarilla" para la
        severidad.

Si la API no responde o cambia de estructura, el productor no inventa una
alerta: retorna una lista vacía (igual que "no hubo alertas nuevas este
ciclo"), que es semánticamente correcto para una fuente event-driven.
"""

import re
from datetime import datetime, timedelta, timezone

import requests

from common.kafka_client import build_producer, run_loop

TOPIC = "alertas-sngr"
INTERVAL_SECONDS = 15 * 60 * 60

WP_API_URL = "https://www.gestionderiesgos.gob.ec/wp-json/wp/v2/posts"
PALABRAS_CLAVE_BUSQUEDA = "lluvias alerta Guayas"

CANTONES_CUENCA_GUAYAS = [
    "Guayaquil", "Daule", "Samborondón", "Durán", "Nobol", "Salitre",
    "Santa Lucía", "Palestina", "Balzar", "Colimes", "El Empalme",
]

SEVERIDAD_POR_PALABRA = [
    ("roja", "critica"),
    ("naranja", "alta"),
    ("amarilla", "media"),
]

TIPOS_EVENTO_POR_PALABRA = [
    ("inundaci", "inundacion"),
    ("desliz", "deslizamiento"),
    ("desbord", "desbordamiento_rio"),
    ("alcantarill", "colapso_alcantarillado"),
]


def _detectar_canton(texto: str) -> str | None:
    texto_lower = texto.lower()
    for canton in CANTONES_CUENCA_GUAYAS:
        if canton.lower() in texto_lower:
            return canton
    return None


def _detectar_severidad(texto: str) -> str:
    texto_lower = texto.lower()
    for palabra, severidad in SEVERIDAD_POR_PALABRA:
        if palabra in texto_lower:
            return severidad
    return "media"  # severidad neutra si no se menciona explícitamente


def _detectar_tipo_evento(texto: str) -> str:
    texto_lower = texto.lower()
    for palabra, tipo in TIPOS_EVENTO_POR_PALABRA:
        if palabra in texto_lower:
            return tipo
    # tipo por defecto, es el más frecuente en la cuenca del Guayas
    return "inundacion"


def _detectar_ubicacion(texto: str) -> str | None:
    canton = _detectar_canton(texto)
    if canton is not None:
        return canton
    return None


def _limpiar_html(texto: str) -> str:
    return re.sub(r"<[^>]+>", " ", texto).strip()


def _dejar_solo_palabras(texto: str) -> str:
    texto = re.sub(r"[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ\s]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def fetch_alertas() -> list[dict]:
    try:
        resp = requests.get(
            WP_API_URL,
            params={
                "search": PALABRAS_CLAVE_BUSQUEDA,
                "per_page": 10,
                "orderby": "date",
                "order": "desc",
            },
            timeout=50,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"},
        )
        resp.raise_for_status()
        posts = resp.json()

    except Exception:
        # fuente event-driven: sin conexión = "sin novedades", no se simula
        return []

    registros = []

    for post in posts:
        titulo = _limpiar_html(post.get("title", {}).get("rendered", ""))
        extracto = _limpiar_html(post.get("excerpt", {}).get("rendered", ""))
        content = _limpiar_html(post.get("content", {}).get("rendered", ""))
        texto_completo = _dejar_solo_palabras(
            f"{titulo} {extracto} {content}"
        )

        ubicacion = _detectar_ubicacion(texto_completo)
        if ubicacion is None:
            # solo nos interesan boletines que mencionen Guayas o sus cantones
            continue

        registros.append({
            "fuente": "SNGR_wp_api",
            "canton": ubicacion,
            "tipo_evento": _detectar_tipo_evento(texto_completo),
            "severidad": _detectar_severidad(texto_completo),
            "descripcion": titulo,
            "url_fuente": post.get("link"),
            "hora_evento": post["date_gmt"],
        })

    return registros


if __name__ == "__main__":
    producer = build_producer()
    run_loop(producer, TOPIC, fetch_alertas, INTERVAL_SECONDS)
