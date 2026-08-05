"""
Script de Ingesta para NOAA.
Descarga y procesa índices mensuales de temperatura superficial del mar (SST)
de El Niño (regiones 1+2, 3, 4 y 3.4) de la NOAA CPC.
"""

import datetime
import io
import os

import pandas as pd
import requests
from common.kafka_client import build_producer, logger, run_loop

ENDPOINT = "https://www.cpc.ncep.noaa.gov/data/indices/ersst5.nino.mth.91-20.ascii"
INTERVAL_SECONDS = int(os.environ.get("INTERVALO_INDICES", 60 * 60))


def ingest_data():
    logger.info("Descargando datos de NOAA...")
    try:
        response = requests.get(ENDPOINT, timeout=15)
        if response.status_code != 200:
            return None

        data_io = io.StringIO(response.text)
        df = pd.read_csv(data_io, sep=r"\s+", header=0)

        records = []
        for _, row in df.iterrows():
            record = {
                "year": int(row["YR"]),
                "month": int(row["MON"]),
                "regions": {
                    "nino_1_2": {"sst": float(row["NINO1+2"]), "anomaly": float(row["ANOM"])},
                    "nino_3": {"sst": float(row["NINO3"]), "anomaly": float(row["ANOM.1"])},
                    "nino_4": {"sst": float(row["NINO4"]), "anomaly": float(row["ANOM.2"])},
                    "nino_3_4": {"sst": float(row["NINO3.4"]), "anomaly": float(row["ANOM.3"])},
                },
            }
            records.append(record)

        return {
            "metadata": {
                "source": "NOAA SST Indices",
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            },
            "data": records,
        }
    except Exception:
        logger.exception("Error al descargar/procesar datos de NOAA")
        return None


def run_producer():
    producer = build_producer()

    def _fetch():
        data = ingest_data()
        if data:
            return [data]
        return []

    run_loop(producer, "noaa-data", _fetch, interval_seconds=INTERVAL_SECONDS)


if __name__ == "__main__":
    run_producer()
