import os
import json
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from risk_index import calcular_indice_riesgo

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
HDFS_BASE = os.environ.get("HDFS_BASE_PATH", "hdfs://localhost:8020/enso_data")
CKPT_BASE = os.environ.get("CHECKPOINT_BASE_PATH", "hdfs://localhost:8020/enso_data/_checkpoints")
GEO_REF_PATH = os.environ.get("GEO_REF_PATH", "spark/data/geo_ref/zonas_guayaquil.csv")
TRIGGER_INTERVAL = "60 seconds"


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
    return raw.selectExpr("CAST(value AS STRING) AS json_str", "timestamp AS kafka_timestamp")


def write_raw_zone(df: DataFrame, nombre_fuente: str):
    df_con_fecha = df.withColumn("fecha", F.to_date("kafka_timestamp"))
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


def calcular_riesgo_batch(spark: SparkSession, geo_ref: DataFrame):
    def _procesar(df_batch: DataFrame, epoch_id: int) -> None:
        try:
            df_inocar = spark.read.parquet(f"{HDFS_BASE}/raw/inocar_mareas")
            latest_inocar_json = df_inocar.orderBy(F.col("kafka_timestamp").desc()).select("json_str").first()["json_str"]
            inocar_data = json.loads(latest_inocar_json)
            altura_marea = float(inocar_data.get("data", {}).get("mareas", {}).get("pleamar", {}).get("altura_m", 1.8))
        except Exception:
            altura_marea = 1.8

        try:
            df_celec = spark.read.parquet(f"{HDFS_BASE}/raw/celec_embalse")
            latest_celec_json = df_celec.orderBy(F.col("kafka_timestamp").desc()).select("json_str").first()["json_str"]
            celec_data = json.loads(latest_celec_json)
            caudal_embalse = float(celec_data.get("nivel_msnm", 100.0))
        except Exception:
            caudal_embalse = 100.0

        try:
            df_inamhi = spark.read.parquet(f"{HDFS_BASE}/raw/inamhi")
            latest_inamhi_json = df_inamhi.orderBy(F.col("kafka_timestamp").desc()).select("json_str").first()["json_str"]
            inamhi_data = json.loads(latest_inamhi_json)
            # Intentamos buscar lluvia en las nuevas variables anidadas
            try:
                precip_mm = inamhi_data.get("pronostico_diario", {}).get("pronostico", [{}])[0].get("precipitacion_mm", 0.0)
            except:
                precip_mm = 0.0
        except Exception:
            precip_mm = 0.0

        def _fila_riesgo(row):
            resultado = calcular_indice_riesgo(
                precip_24h_mm=precip_mm,
                altura_marea_m=altura_marea,
                caudal_descargado_m3s=caudal_embalse,
                cota_media_msnm=row["cota_media_msnm"],
                pendiente_clase=row["pendiente_clase"],
                cercania_estero_m=row["cercania_estero_m"],
                historicamente_inundable=row["historicamente_inundable"],
            )
            return (
                row["zona_id"], row["nombre_sector"], row["lat_centroide"], row["lon_centroide"],
                precip_mm, altura_marea, caudal_embalse,
                resultado["indice_riesgo"], resultado["nivel_riesgo"],
            )

        columnas = ["zona_id", "nombre_sector", "lat_centroide", "lon_centroide", "precip_acumulada_24h_mm", "altura_marea_m", "caudal_embalse_m3s", "indice_riesgo", "nivel_riesgo"]
        filas_riesgo = geo_ref.rdd.map(_fila_riesgo)
        if filas_riesgo.isEmpty(): return

        df_riesgo = spark.createDataFrame(filas_riesgo, columnas)
        df_riesgo = df_riesgo.withColumn("fecha", F.current_date()).withColumn("calculado_en", F.current_timestamp())

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

    geo_ref = spark.read.option("header", "true").option("inferSchema", "true").csv(GEO_REF_PATH)

    topics_to_sources = {
        "gee-data": "gee",
        "noaa-data": "noaa",
        "open-meteo-data": "open_meteo",
        "nasa-power-data": "nasa_power",
        "openweathermap-data": "openweathermap",
        "enso-indexes": "enso_indexes",
        "inamhi-data": "inamhi",
        "sgr-eventos": "sgr_eventos",
        "seguraep-layers": "seguraep",
        "guayas-osm": "guayas_osm",
        "nivel-embalse-celec": "celec_embalse",
        "mareas-inocar": "inocar_mareas",
        "alertas-sngr": "sngr_alertas",
        "ndbc-buoys": "ndbc_buoys"
    }

    queries = []
    df_any = None
    for topic, source_name in topics_to_sources.items():
        df_raw = read_topic_raw(spark, topic)
        queries.append(write_raw_zone(df_raw, source_name))
        if df_any is None:
            df_any = df_raw
        else:
            df_any = df_any.union(df_raw)

    if df_any is not None:
        query_riesgo = (
            df_any.writeStream
            .foreachBatch(calcular_riesgo_batch(spark, geo_ref))
            .option("checkpointLocation", f"{CKPT_BASE}/indice_riesgo")
            .trigger(processingTime=TRIGGER_INTERVAL)
            .outputMode("update")
            .start()
        )
        queries.append(query_riesgo)

    for q in queries:
        q.awaitTermination()


if __name__ == "__main__":
    main()
