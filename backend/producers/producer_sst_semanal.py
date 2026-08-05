"""
Productor de SST y anomalía semanal desde NOAA CPC (wksst9120.for).

Prioriza la región Niño 1+2 (90°O–80°O, 10°S–0°), que es la que gobierna la
convección profunda y la lluvia en la costa ecuatoriana y Guayaquil. Usa el
archivo `wksst9120.for` (base 1991-2020), ya que `wksst8110.for` está congelado
en 2021.
"""

import os

import requests
from common.kafka_client import build_producer, logger, run_loop
from contracts import TOPIC_SST_SEMANAL, construir_sst_semanal

INTERVAL_SECONDS = int(os.environ.get("INTERVALO_SST_SEMANAL", 12 * 60 * 60))
URL_CPC_SEMANAL = "https://www.cpc.ncep.noaa.gov/data/indices/wksst9120.for"


def parse_wksst9120(contenido_txt: str) -> list[dict]:
    """Parseador de ancho fijo para el reporte de NOAA CPC wksst9120.for."""
    lineas = contenido_txt.strip().splitlines()
    registros = []

    for linea in lineas:
        linea_str = linea.strip()
        if not linea_str or "Nino" in linea_str or "Week" in linea_str or "=====" in linea_str:
            continue

        partes = linea_str.split()
        if len(partes) < 9:
            continue

        try:
            fecha_str = partes[0]
            # Columnas del archivo wksst9120.for:
            # 0: Week, 1: Nino1+2 SST, 2: Nino1+2 SSTA, 3: Nino3 SST, 4: Nino3 SSTA,
            # 5: Nino3.4 SST, 6: Nino3.4 SSTA, 7: Nino4 SST, 8: Nino4 SSTA
            sst_12 = float(partes[1])
            anom_12 = float(partes[2])
            sst_3 = float(partes[3])
            anom_3 = float(partes[4])
            sst_34 = float(partes[5])
            anom_34 = float(partes[6])
            sst_4 = float(partes[7])
            anom_4 = float(partes[8])

            payload = construir_sst_semanal(
                fecha_semana=fecha_str,
                sst_nino12_c=sst_12,
                anomalia_nino12_c=anom_12,
                sst_nino3_c=sst_3,
                anomalia_nino3_c=anom_3,
                sst_nino34_c=sst_34,
                anomalia_nino34_c=anom_34,
                sst_nino4_c=sst_4,
                anomalia_nino4_c=anom_4,
            )
            registros.append(payload)
        except (ValueError, IndexError):
            continue

    return registros


def fetch_sst_semanal() -> list[dict]:
    try:
        resp = requests.get(URL_CPC_SEMANAL, timeout=12)
        if not resp.ok:
            logger.error("NOAA CPC semanal respondió %s", resp.status_code)
            return []

        registros = parse_wksst9120(resp.text)
        if registros:
            mas_reciente = registros[-1]
            logger.info(
                "NOAA SST semanal (%s): Niño 1+2 SSTA=%s °C",
                mas_reciente["fecha_semana"],
                mas_reciente["anomalia_nino12_c"],
            )
            return [mas_reciente]

        logger.error("NOAA CPC semanal: sin registros parseables")
        return []
    except Exception:
        logger.exception("Error consultando NOAA CPC semanal")
        return []


def run_producer():
    producer = build_producer()
    run_loop(producer, TOPIC_SST_SEMANAL, fetch_sst_semanal, INTERVAL_SECONDS)


if __name__ == "__main__":
    run_producer()
