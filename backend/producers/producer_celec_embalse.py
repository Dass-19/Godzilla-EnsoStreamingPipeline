"""
Productor -> topic 'nivel-embalse-celec'

Fuente real, SIN API KEY: CELEC EP - Hidronación expone su contenido de
prensa en una REST API pública de WordPress en:
    https://www.celec.gob.ec/hidronacion/wp-json/wp/v2/posts

Este productor:
    1. Consulta publicaciones recientes relacionadas con el embalse.
    2. Combina título, extracto y contenido del post.

Si la API no responde o no hay un post útil, el productor no inventa un
dato: retorna una lista vacía, igual que el productor de alertas SNGR.
Cuando sí logra extraer un valor real de una publicación, lo marca como
"fuente": "CELEC_wp_api" y agrega la URL del post como referencia para
que sea auditable en el dashboard/informe.
"""

import html
import re
import requests

from common.kafka_client import build_producer, run_loop

TOPIC = "nivel-embalse-celec"
INTERVAL_SECONDS = 15 * 60 * 60

WP_API_URL = "https://www.celec.gob.ec/hidronacion/wp-json/wp/v2/posts"

PALABRAS_CLAVE_BUSQUEDA = "embalse Daule Peripa"
PALABRAS_CLAVE_EMBALSE = [
    "embalse",
    "daule",
    "peripa",
    "cota",
    "compuertas",
    "descarga",
]

# Patrón 1: "el embalse se encuentra en los X metros sobre el nivel del mar / m.s.n.m"
RE_NIVEL_ACTUAL = re.compile(
    r"embalse\s+se\s+encuentra\s+en\s+(?:los|el)?\s*"
    r"(\d{1,3}(?:[.,]\d{1,2})?)\s*"
    r"(?:metros(?:\s+sobre\s+el\s+nivel\s+del\s+mar)?\s*)?"
    r"\(?m\.?\s*s\.?\s*n\.?\s*m\.?\)?",
    re.IGNORECASE,
)

# Patrón 2: "Su nivel máximo es X m.s.n.m."
RE_NIVEL_MAXIMO = re.compile(
    r"nivel\s+m[aá]ximo\s+es\s+"
    r"(\d{1,3}(?:[.,]\d{1,2})?)\s*"
    r"\(?m\.?\s*s\.?\s*n\.?\s*m\.?\)?",
    re.IGNORECASE,
)

# Patrón 3: "la cota del embalse ... alcanzó su máximo nivel normal de operación, es decir X m.s.n.m."
# También cubre variantes sin "es decir": "...alcanzó los X m.s.n.m."
RE_COTA_ALCANZO = re.compile(
    r"cota\s+del\s+embalse[^.]{0,120}?"
    r"alcanz[oó]\s+(?:su\s+m[aá]ximo\s+nivel\s+normal\s+de\s+operaci[oó]n\s*,?\s*)?"
    r"(?:es\s+decir\s+|los\s+|el\s+)?"
    r"(\d{1,3}(?:[.,]\d{1,2})?)\s*"
    r"\(?m\.?\s*s\.?\s*n\.?\s*m\.?\)?",
    re.IGNORECASE,
)

# Patrón 4: "la cota del embalse se ubica/registra en X m.s.n.m." (variante frecuente en otros boletines)
RE_COTA_UBICA = re.compile(
    r"cota\s+del\s+embalse[^.]{0,80}?"
    r"(?:se\s+ubic[ao]|se\s+registr[ao]|registr[ao]|se\s+encuentra)\s+en\s+"
    r"(\d{1,3}(?:[.,]\d{1,2})?)\s*"
    r"\(?m\.?\s*s\.?\s*n\.?\s*m\.?\)?",
    re.IGNORECASE,
)


def _extraer_nivel_embalse(texto_limpio: str) -> dict | None:
    resultado = {}

    # Nivel actual: probamos los 3 patrones específicos, en orden de prioridad
    for patron in (RE_NIVEL_ACTUAL, RE_COTA_ALCANZO, RE_COTA_UBICA):
        match = patron.search(texto_limpio)
        if match:
            resultado["nivel_msnm"] = float(match.group(1).replace(",", "."))
            break

    # Nivel máximo (capacidad de diseño de la presa), si el boletín lo menciona
    match_max = RE_NIVEL_MAXIMO.search(texto_limpio)
    if match_max:
        resultado["nivel_maximo_msnm"] = float(match_max.group(1).replace(",", "."))

    return resultado or None


def _limpiar_html(texto: str) -> str:
    texto = html.unescape(texto or "")
    return re.sub(r"<[^>]+>", " ", texto).strip()


def _dejar_solo_palabras(texto: str) -> str:
    texto = re.sub(r"[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ\s]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _es_post_relevante(texto: str) -> bool:
    texto_lower = texto.lower()
    return any(palabra in texto_lower for palabra in PALABRAS_CLAVE_EMBALSE)


def _extraer_desde_post(post: dict) -> dict | None:
    titulo = _limpiar_html(post.get("title", {}).get("rendered", ""))
    extracto = _limpiar_html(post.get("excerpt", {}).get("rendered", ""))
    content = _limpiar_html(post.get("content", {}).get("rendered", ""))
    texto_limpio = f"{titulo} {extracto} {content}"          # <- sin dejar_solo_palabras
    texto_para_keywords = _dejar_solo_palabras(texto_limpio)  # <- solo para el filtro de relevancia

    if not _es_post_relevante(texto_para_keywords):
        return None

    nivel = _extraer_nivel_embalse(texto_limpio)
    if nivel is None:
        return None

    return {
        "descripcion": titulo,
        "url_fuente": post.get("link"),
        "fecha_noticia": post["date_gmt"],
        **nivel,
    }


def fetch_nivel_embalse() -> list[dict]:
    try:
        resp = requests.get(
            WP_API_URL,
            params={
                "search": PALABRAS_CLAVE_BUSQUEDA,
                "per_page": 15,
                "orderby": "date",
                "order": "desc",
            },
            timeout=50,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/127.0.0.0 Safari/537.36"
                )
            },
        )
        resp.raise_for_status()
        posts = resp.json()

    except Exception:
        return []

    registros = []

    for post in posts:
        datos = _extraer_desde_post(post)

        if datos is None:
            continue

        registro = {
            "fuente": "CELEC_wp_api",
            "embalse": "Daule-Peripa",
            "descripcion": datos["descripcion"],
            "url_fuente": datos["url_fuente"],
            "fecha_noticia": datos["fecha_noticia"],
            "nivel_msnm": datos["nivel_msnm"],
        }

        # nivel_maximo_msnm es opcional (no todos los boletines lo mencionan)
        if "nivel_maximo_msnm" in datos:
            registro["nivel_maximo_msnm"] = datos["nivel_maximo_msnm"]

        registros.append(registro)

    return registros


if __name__ == "__main__":
    producer = build_producer()
    run_loop(producer, TOPIC, fetch_nivel_embalse, INTERVAL_SECONDS)
