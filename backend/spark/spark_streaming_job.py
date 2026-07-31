"""
Trabajo de streaming con PySpark para procesar variables ENSO en tiempo real.

Ingesta datos desde tópicos de Kafka, escribe el crudo a HDFS en formato
Parquet, calcula el índice de riesgo de inundación por sector en Guayaquil y
almacena los resultados procesados en HDFS.
"""

import json
import logging
import os

from contracts import (
    FUENTE_EMBALSE,
    FUENTE_MAREA,
    FUENTE_PRECIPITACION,
    TOPIC_EMBALSE,
    TOPIC_MAREA,
    TOPIC_PRECIPITACION,
    Lectura,
    parse_embalse,
    parse_marea,
    parse_precipitacion,
)
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

TOPICS_A_FUENTES = {
    "gee-data": "gee",
    "noaa-data": "noaa",
    "open-meteo-data": "open_meteo",
    TOPIC_PRECIPITACION: FUENTE_PRECIPITACION,
    "openweathermap-data": "openweathermap",
    "enso-indexes": "enso_indexes",
    "inamhi-data": "inamhi",
    "sgr-eventos": "sgr_eventos",
    # `seguraep-layers` no está incluido porque producer_seguraep escribe GeoJSON directo a HDFS.
    "guayas-osm": "guayas_osm",
    TOPIC_EMBALSE: FUENTE_EMBALSE,
    TOPIC_MAREA: FUENTE_MAREA,
    "alertas-sngr": "sngr_alertas",
    "ndbc-buoys": "ndbc_buoys",
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
])


def build_spark() -> SparkSession:
    return (
        SparkSession.builder
        .appName("enso-data-risk-pipeline")
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
    Últimos valores conocidos de las tres entradas dinámicas del índice.

    Se actualiza con los mensajes de cada micro-batch. Cuando una fuente
    todavía no aportó ningún dato, `lecturas()` devuelve el respaldo marcado
    como `default`, y esa marca viaja hasta el parquet: una fila calculada con
    tres respaldos deja de ser indistinguible de una fila real.
    """

    def __init__(self):
        self._marea = None
        self._embalse = None
        self._precip = None

    def actualizar(self, topic: str, payload: dict) -> None:
        if topic == TOPIC_MAREA:
            valor = parse_marea(payload)
            if valor is not None:
                self._marea = valor
        elif topic == TOPIC_EMBALSE:
            valor = parse_embalse(payload)
            if valor is not None:
                self._embalse = valor
        elif topic == TOPIC_PRECIPITACION:
            valor = parse_precipitacion(payload)
            if valor is not None:
                self._precip = valor

    def lecturas(self) -> dict:
        return {
            "precip": Lectura.desde(
                self._precip, RESPALDO_PRECIP_MM, "sin dato de NASA POWER",
            ),
            "marea": Lectura.desde(
                self._marea, RESPALDO_MAREA_M, "sin dato de INOCAR",
            ),
            "embalse": Lectura.desde(
                self._embalse, RESPALDO_EMBALSE_MSNM, "sin dato de CELEC",
            ),
        }

    def bootstrap(self, spark: SparkSession) -> None:
        """
        Rellena el estado leyendo el último registro ya persistido de cada
        fuente. Solo se ejecuta una vez al arrancar, para no partir de
        respaldos cuando el checkpoint ya consumió los mensajes históricos.
        """
        fuentes = {
            TOPIC_MAREA: FUENTE_MAREA,
            TOPIC_EMBALSE: FUENTE_EMBALSE,
            TOPIC_PRECIPITACION: FUENTE_PRECIPITACION,
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

        estado = self.lecturas()
        logger.info(
            "bootstrap completo: precip=%s marea=%s embalse=%s",
            estado["precip"], estado["marea"], estado["embalse"],
        )


def calcular_riesgo_batch(spark: SparkSession, zonas: list, estado: EstadoFuentes):
    """
    Devuelve el callback de `foreachBatch` que actualiza el estado con los
    mensajes del batch y escribe una fila de riesgo por zona.
    """

    def _procesar(df_batch: DataFrame, epoch_id: int) -> None:
        filas_entrantes = (
            df_batch.select("topic", "json_str")
            .where(F.col("topic").isin(TOPIC_MAREA, TOPIC_EMBALSE, TOPIC_PRECIPITACION))
            .collect()
        )
        for fila in filas_entrantes:
            try:
                estado.actualizar(fila["topic"], json.loads(fila["json_str"]))
            except (ValueError, TypeError) as error:
                logger.warning(
                    "payload no parseable en topic=%s: %s", fila["topic"], error,
                )

        lecturas = estado.lecturas()
        precip, marea, embalse = lecturas["precip"], lecturas["marea"], lecturas["embalse"]

        if not (precip.es_real and marea.es_real and embalse.es_real):
            faltantes = [
                nombre for nombre, lectura in lecturas.items() if not lectura.es_real
            ]
            logger.warning(
                "epoch=%s calculando riesgo con respaldos para: %s",
                epoch_id, ", ".join(faltantes),
            )

        datos_completos = all(lectura.es_real for lectura in lecturas.values())

        filas = []
        for zona in zonas:
            resultado = calcular_indice_riesgo(
                precip_24h_mm=precip.valor,
                altura_marea_m=marea.valor,
                nivel_embalse_msnm=embalse.valor,
                cota_media_msnm=float(zona["cota_media_msnm"]),
                pendiente_clase=zona["pendiente_clase"],
                cercania_estero_m=float(zona["cercania_estero_m"]),
                historicamente_inundable=bool(zona["historicamente_inundable"]),
            )
            filas.append((
                zona["zona_id"],
                zona["nombre_sector"],
                float(zona["lat_centroide"]),
                float(zona["lon_centroide"]),
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
            ))

        if not filas:
            return

        df_riesgo = (
            spark.createDataFrame(filas, schema=ESQUEMA_RIESGO)
            .withColumn("fecha", F.current_date())
            .withColumn("calculado_en", F.current_timestamp())
        )

        # `append` no es idempotente: si Spark reintenta un epoch, sus filas se
        # escriben dos veces. Por eso cada fila lleva `epoch_id`, y la API
        # deduplica por (zona_id, epoch_id) al leer.
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
    # Son 10 zonas: traerlas al driver evita el RDD.map + isEmpty + inferencia
    # de schema (tres pasadas de Spark sobre una tabla que cabe en memoria).
    zonas = [fila.asDict() for fila in geo_ref.collect()]
    logger.info("geo_ref cargado: %s zonas", len(zonas))

    estado = EstadoFuentes()
    estado.bootstrap(spark)

    df_por_topic = {
        topic: read_topic_raw(spark, topic) for topic in TOPICS_A_FUENTES
    }

    for topic, fuente in TOPICS_A_FUENTES.items():
        write_raw_zone(df_por_topic[topic], fuente)

    # El cálculo del riesgo solo necesita los tres tópicos que alimentan el
    # índice; suscribir los 14 obligaba a deserializar payloads pesados
    # (catálogo INAMHI, GeoJSON de OSM) en cada batch para descartarlos.
    df_riesgo_entrada = None
    for topic in (TOPIC_MAREA, TOPIC_EMBALSE, TOPIC_PRECIPITACION):
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

    # Termina si cualquiera de las consultas de streaming se detiene o falla.
    spark.streams.awaitAnyTermination()


if __name__ == "__main__":
    main()
