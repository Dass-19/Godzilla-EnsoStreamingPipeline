"""
Trabajo de streaming con PySpark para procesar variables ENSO en tiempo real.

Ingesta datos desde tópicos de Kafka, escribe el crudo a HDFS en formato
Parquet, calcula el índice de riesgo de inundación por sector en Guayaquil y
almacena los resultados procesados en HDFS.
"""

from __future__ import annotations

import json
import logging
import os

from contracts import (
    FUENTE_CAUDAL,
    FUENTE_EMBALSE,
    FUENTE_MAREA,
    FUENTE_MAREA_OBSERVADA,
    FUENTE_PRECIP_ESTACIONES,
    FUENTE_PRECIP_PRONOSTICO,
    FUENTE_PRECIPITACION,
    FUENTE_SST_SEMANAL,
    TOPIC_CAUDAL,
    TOPIC_EMBALSE,
    TOPIC_MAREA,
    TOPIC_MAREA_OBSERVADA,
    TOPIC_PRECIP_ESTACIONES,
    TOPIC_PRECIP_PRONOSTICO,
    TOPIC_PRECIPITACION,
    TOPIC_SST_SEMANAL,
    Lectura,
    LluviaEstacion,
    parse_anomalia_nino12,
    parse_caudal,
    parse_embalse,
    parse_lluvia_estaciones,
    parse_marea,
    parse_marea_observada,
    parse_precipitacion,
    parse_pronostico_precip,
    parse_saturacion_antecedente,
)
from interpolacion import interpolar_idw
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    BooleanType,
    DoubleType,
    LongType,
    StringType,
    StructField,
    StructType,
)
from risk_index import calcular_indice_riesgo

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("enso.spark")

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
HDFS_BASE = os.environ.get("HDFS_BASE_PATH", "hdfs://localhost:8020/enso_data")
CKPT_BASE = os.environ.get(
    "CHECKPOINT_BASE_PATH",
    "hdfs://localhost:8020/enso_data/_checkpoints",
)
GEO_REF_PATH = os.environ.get("GEO_REF_PATH", "spark/data/geo_ref/zonas_guayaquil.csv")

# Alineado con la cadencia de publicación de las fuentes.
TRIGGER_INTERVAL = os.environ.get("TRIGGER_INTERVAL", "5 minutes")

# Valores de respaldo cuando todavía no llegó ningún dato real de una fuente.
# Se persisten marcados como `default` en las columnas `origen_*`.
RESPALDO_MAREA_M = 1.8
RESPALDO_EMBALSE_MSNM = 80.0
RESPALDO_PRECIP_MM = 0.0
RESPALDO_CAUDAL_M3S = 500.0
RESPALDO_SATURACION_MM = 0.0
RESPALDO_ANOMALIA_NINO12_C = 0.0

TOPICS_A_FUENTES = {
    "gee-data": "gee",
    "noaa-data": "noaa",
    "open-meteo-data": "open_meteo",
    TOPIC_PRECIPITACION: FUENTE_PRECIPITACION,
    "openweathermap-data": "openweathermap",
    "enso-indexes": "enso_indexes",
    "inamhi-data": "inamhi",
    "sgr-eventos": "sgr_eventos",
    "guayas-osm": "guayas_osm",
    TOPIC_EMBALSE: FUENTE_EMBALSE,
    TOPIC_MAREA: FUENTE_MAREA,
    "alertas-sngr": "sngr_alertas",
    "ndbc-buoys": "ndbc_buoys",
    TOPIC_PRECIP_ESTACIONES: FUENTE_PRECIP_ESTACIONES,
    TOPIC_PRECIP_PRONOSTICO: FUENTE_PRECIP_PRONOSTICO,
    TOPIC_MAREA_OBSERVADA: FUENTE_MAREA_OBSERVADA,
    TOPIC_CAUDAL: FUENTE_CAUDAL,
    "inamhi-nivel-rio": "inamhi_nivel_rio",
    TOPIC_SST_SEMANAL: FUENTE_SST_SEMANAL,
}

ESQUEMA_RIESGO = StructType([
    StructField("zona_id", StringType(), False),
    StructField("nombre_sector", StringType(), True),
    StructField("lat_centroide", DoubleType(), True),
    StructField("lon_centroide", DoubleType(), True),
    StructField("precip_acumulada_24h_mm", DoubleType(), True),
    StructField("altura_marea_m", DoubleType(), True),
    StructField("nivel_embalse_msnm", DoubleType(), True),
    StructField("origen_precip", StringType(), True),
    StructField("origen_marea", StringType(), True),
    StructField("origen_embalse", StringType(), True),
    StructField("indice_riesgo", DoubleType(), True),
    StructField("nivel_riesgo", StringType(), True),
    StructField("datos_completos", BooleanType(), True),
    StructField("epoch_id", LongType(), True),
    StructField("precip_pronostico_24h_mm", DoubleType(), True),
    StructField("marea_observada_m", DoubleType(), True),
    StructField("caudal_rio_m3s", DoubleType(), True),
    StructField("saturacion_antecedente_mm", DoubleType(), True),
    StructField("origen_rio", StringType(), True),
    StructField("origen_suelo", StringType(), True),
    StructField("origen_marea_obs", StringType(), True),
    StructField("n_estaciones_precip", LongType(), True),
    StructField("poblacion", LongType(), True),
    StructField("exposicion_norm", DoubleType(), True),
    StructField("indice_impacto", DoubleType(), True),
    StructField("anomalia_nino12_c", DoubleType(), True),
    StructField("origen_enso", StringType(), True),
])


def build_spark() -> SparkSession:
    return (
        SparkSession.builder
        .appName("GodzillaEnsoStreamingPipeline")
        .config("spark.hadoop.dfs.client.use.datanode.hostname", "true")
        .config("spark.sql.shuffle.partitions", "8")
        .getOrCreate()
    )


def read_topic_raw(spark: SparkSession, topic: str) -> DataFrame:
    raw = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
        .option("subscribe", topic)
        .option("startingOffsets", "earliest")
        .option("failOnDataLoss", "false")
        .load()
    )
    return raw.selectExpr(
        "CAST(value AS STRING) AS json_str",
        "timestamp AS kafka_timestamp",
        "topic",
    )


def write_raw_zone(df: DataFrame, nombre_fuente: str):
    df_con_fecha = (
        df.drop("topic").withColumn("fecha", F.to_date("kafka_timestamp"))
    )
    return (
        df_con_fecha.writeStream
        .format("parquet")
        .option("path", f"{HDFS_BASE}/raw/{nombre_fuente}")
        .option("checkpointLocation", f"{CKPT_BASE}/raw_{nombre_fuente}")
        .partitionBy("fecha")
        .trigger(processingTime=TRIGGER_INTERVAL)
        .outputMode("append")
        .start()
    )


class EstadoFuentes:
    """
    Últimos valores conocidos de todas las entradas dinámicas del índice.
    """

    def __init__(self):
        self._marea = None
        self._embalse = None
        self._precip_nasa = None
        self._estaciones_inamhi: list[LluviaEstacion] = []
        self._saturacion = None
        self._pronostico_precip = None
        self._marea_obs = None
        self._caudal = None
        self._anomalia_nino12 = None

    def actualizar(self, topic: str, payload: dict) -> None:
        if topic == TOPIC_MAREA:
            val = parse_marea(payload)
            if val is not None:
                self._marea = val
        elif topic == TOPIC_EMBALSE:
            val = parse_embalse(payload)
            if val is not None:
                self._embalse = val
        elif topic == TOPIC_PRECIPITACION:
            val = parse_precipitacion(payload)
            if val is not None:
                self._precip_nasa = val
        elif topic == TOPIC_PRECIP_ESTACIONES:
            estaciones = parse_lluvia_estaciones(payload)
            if estaciones:
                self._estaciones_inamhi = estaciones
            sat = parse_saturacion_antecedente(payload)
            if sat is not None:
                self._saturacion = sat
        elif topic == TOPIC_PRECIP_PRONOSTICO:
            val = parse_pronostico_precip(payload)
            if val is not None:
                self._pronostico_precip = val
        elif topic == TOPIC_MAREA_OBSERVADA:
            val = parse_marea_observada(payload)
            if val is not None:
                self._marea_obs = val
        elif topic == TOPIC_CAUDAL:
            val = parse_caudal(payload)
            if val is not None:
                self._caudal = val
        elif topic == TOPIC_SST_SEMANAL:
            val = parse_anomalia_nino12(payload)
            if val is not None:
                self._anomalia_nino12 = val

    def lecturas(self, lat: float | None = None, lon: float | None = None) -> dict:
        precip_val, n_est = None, 0
        if lat is not None and lon is not None and self._estaciones_inamhi:
            precip_val, n_est = interpolar_idw(self._estaciones_inamhi, lat, lon)

        if precip_val is None:
            precip_val = self._precip_nasa

        return {
            "precip": Lectura.desde(precip_val, RESPALDO_PRECIP_MM, "sin dato de lluvia"),
            "marea": Lectura.desde(self._marea, RESPALDO_MAREA_M, "sin dato de INOCAR"),
            "embalse": Lectura.desde(self._embalse, RESPALDO_EMBALSE_MSNM, "sin dato de CELEC"),
            "marea_obs": Lectura.desde(self._marea_obs, self._marea if self._marea is not None else RESPALDO_MAREA_M, "sin dato IOC"),
            "caudal": Lectura.desde(self._caudal, RESPALDO_CAUDAL_M3S, "sin dato GEOGLOWS"),
            "suelo": Lectura.desde(self._saturacion, RESPALDO_SATURACION_MM, "sin dato INAMHI"),
            "pronostico_precip": Lectura.desde(self._pronostico_precip, 0.0, "sin dato Open-Meteo"),
            "enso": Lectura.desde(self._anomalia_nino12, RESPALDO_ANOMALIA_NINO12_C, "sin dato NOAA CPC"),
            "n_estaciones": n_est,
        }

    def bootstrap(self, spark: SparkSession) -> None:
        fuentes = {
            TOPIC_MAREA: FUENTE_MAREA,
            TOPIC_EMBALSE: FUENTE_EMBALSE,
            TOPIC_PRECIPITACION: FUENTE_PRECIPITACION,
            TOPIC_PRECIP_ESTACIONES: FUENTE_PRECIP_ESTACIONES,
            TOPIC_PRECIP_PRONOSTICO: FUENTE_PRECIP_PRONOSTICO,
            TOPIC_MAREA_OBSERVADA: FUENTE_MAREA_OBSERVADA,
            TOPIC_CAUDAL: FUENTE_CAUDAL,
            TOPIC_SST_SEMANAL: FUENTE_SST_SEMANAL,
        }
        for topic, fuente in fuentes.items():
            ruta = f"{HDFS_BASE}/raw/{fuente}"
            try:
                fila = (
                    spark.read.parquet(ruta)
                    .orderBy(F.col("kafka_timestamp").desc())
                    .select("json_str")
                    .first()
                )
            except Exception as error:
                logger.info("bootstrap: %s todavía no existe (%s)", ruta, error)
                continue

            if fila is None:
                continue
            try:
                self.actualizar(topic, json.loads(fila["json_str"]))
            except (ValueError, TypeError) as error:
                logger.warning("bootstrap: json inválido en %s: %s", ruta, error)

        logger.info("bootstrap de estado de fuentes completado.")


def calcular_riesgo_batch(spark: SparkSession, zonas: list, estado: EstadoFuentes):
    def _procesar(df_batch: DataFrame, epoch_id: int) -> None:
        topics_riesgo = (
            TOPIC_MAREA,
            TOPIC_EMBALSE,
            TOPIC_PRECIPITACION,
            TOPIC_PRECIP_ESTACIONES,
            TOPIC_PRECIP_PRONOSTICO,
            TOPIC_MAREA_OBSERVADA,
            TOPIC_CAUDAL,
            TOPIC_SST_SEMANAL,
        )
        filas_entrantes = (
            df_batch.select("topic", "json_str")
            .where(F.col("topic").isin(*topics_riesgo))
            .collect()
        )
        for fila in filas_entrantes:
            try:
                estado.actualizar(fila["topic"], json.loads(fila["json_str"]))
            except (ValueError, TypeError) as error:
                logger.warning(
                    "payload no parseable en topic=%s: %s", fila["topic"], error,
                )

        filas = []
        for zona in zonas:
            lat = float(zona["lat_centroide"])
            lon = float(zona["lon_centroide"])
            lecturas = estado.lecturas(lat, lon)

            precip = lecturas["precip"]
            marea = lecturas["marea"]
            embalse = lecturas["embalse"]
            marea_obs = lecturas["marea_obs"]
            caudal = lecturas["caudal"]
            suelo = lecturas["suelo"]
            pronostico = lecturas["pronostico_precip"]
            enso = lecturas["enso"]
            n_est = lecturas["n_estaciones"]
            poblacion = int(zona.get("poblacion") or 0)

            resultado = calcular_indice_riesgo(
                precip_24h_mm=precip.valor,
                altura_marea_m=marea.valor,
                nivel_embalse_msnm=embalse.valor,
                cota_media_msnm=float(zona["cota_media_msnm"]),
                pendiente_clase=str(zona["pendiente_clase"]),
                cercania_estero_m=float(zona["cercania_estero_m"]),
                historicamente_inundable=bool(zona["historicamente_inundable"]),
                caudal_rio_m3s=caudal.valor,
                saturacion_antecedente_mm=suelo.valor,
                anomalia_nino12_c=enso.valor,
                poblacion=poblacion,
            )

            datos_completos = (
                precip.es_real and marea.es_real and caudal.es_real and suelo.es_real
            )

            filas.append((
                zona["zona_id"],
                zona["nombre_sector"],
                lat,
                lon,
                precip.valor,
                marea.valor,
                embalse.valor,
                precip.origen,
                marea.origen,
                embalse.origen,
                float(resultado["indice_riesgo"]),
                resultado["nivel_riesgo"],
                datos_completos,
                int(epoch_id),
                pronostico.valor,
                marea_obs.valor,
                caudal.valor,
                suelo.valor,
                caudal.origen,
                suelo.origen,
                marea_obs.origen,
                int(n_est),
                poblacion,
                float(resultado["exposicion_norm"]),
                float(resultado["indice_impacto"]),
                enso.valor,
                enso.origen,
            ))

        if not filas:
            return

        df_riesgo = (
            spark.createDataFrame(filas, schema=ESQUEMA_RIESGO)
            .withColumn("fecha", F.current_date())
            .withColumn("calculado_en", F.current_timestamp())
        )

        (
            df_riesgo.write
            .mode("append")
            .partitionBy("fecha")
            .parquet(f"{HDFS_BASE}/processed/indice_riesgo")
        )

    return _procesar


def main() -> None:
    spark = build_spark()
    spark.sparkContext.setLogLevel("WARN")

    geo_ref = (
        spark.read
        .option("header", "true")
        .option("inferSchema", "true")
        .csv(GEO_REF_PATH)
    )
    zonas = [fila.asDict() for fila in geo_ref.collect()]
    logger.info("geo_ref cargado: %s zonas", len(zonas))

    estado = EstadoFuentes()
    estado.bootstrap(spark)

    df_por_topic = {
        topic: read_topic_raw(spark, topic) for topic in TOPICS_A_FUENTES
    }

    for topic, fuente in TOPICS_A_FUENTES.items():
        write_raw_zone(df_por_topic[topic], fuente)

    topics_riesgo = (
        TOPIC_MAREA,
        TOPIC_EMBALSE,
        TOPIC_PRECIPITACION,
        TOPIC_PRECIP_ESTACIONES,
        TOPIC_PRECIP_PRONOSTICO,
        TOPIC_MAREA_OBSERVADA,
        TOPIC_CAUDAL,
        TOPIC_SST_SEMANAL,
    )
    df_riesgo_entrada = None
    for topic in topics_riesgo:
        df_topic = df_por_topic[topic]
        df_riesgo_entrada = (
            df_topic if df_riesgo_entrada is None else df_riesgo_entrada.union(df_topic)
        )

    (
        df_riesgo_entrada.writeStream
        .foreachBatch(calcular_riesgo_batch(spark, zonas, estado))
        .option("checkpointLocation", f"{CKPT_BASE}/indice_riesgo")
        .trigger(processingTime=TRIGGER_INTERVAL)
        .outputMode("update")
        .start()
    )

    spark.streams.awaitAnyTermination()


if __name__ == "__main__":
    main()
