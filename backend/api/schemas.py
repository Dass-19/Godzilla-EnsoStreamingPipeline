"""
Modelos Pydantic y Esquema de Respuesta Estandarizado (Envelope Pattern).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class MetaAPI(BaseModel):
    api_version: str = Field("1.2.0", description="Versión activa de la API REST", example="1.2.0")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="Marca de tiempo ISO-8601 del servidor API",
        example="2026-08-01T13:20:00Z",
    )
    fuente: str | None = Field(
        None,
        description="Origen HDFS o servicio externo de donde se extrajo la información",
        example="/enso_data/processed/indice_riesgo",
    )
    total_registros: int | None = Field(
        None,
        description="Cantidad de registros o elementos cuando la carga útil es una lista",
        example=45,
    )


class ErrorInfo(BaseModel):
    codigo: int = Field(
        ..., description="Código de estado HTTP del error (404, 502, 503, etc.)", example=404
    )
    tipo: str = Field(
        ..., description="Categorización del tipo de error", example="RECURSO_NO_ENCONTRADO"
    )
    mensaje: str = Field(
        ...,
        description="Mensaje legible de error para el usuario o frontend",
        example="Aún no hay datos de índice de riesgo procesados",
    )
    detalle: str | None = Field(
        None,
        description="Detalle técnico adicional o causa raíz",
        example="No se encontraron particiones Parquet en HDFS",
    )


class RespuestaAPI(BaseModel, Generic[T]):
    status: str = Field(
        "success", description="Estado de la respuesta: 'success' o 'error'", example="success"
    )
    data: T | None = Field(None, description="Carga útil principal de la respuesta")
    error: ErrorInfo | None = Field(None, description="Detalles del error si status == 'error'")
    meta: MetaAPI = Field(
        default_factory=MetaAPI, description="Metadatos contextuales del servidor y pipeline"
    )


class ZonaRiesgo(BaseModel):
    zona_id: str = Field(
        ..., description="Identificador único de la zona o sector urbano", example="ZONA_001"
    )
    nombre_sector: str | None = Field(
        None, description="Nombre legible del sector o parroquia", example="Urdesa Central"
    )
    lat_centroide: float | None = Field(
        None, description="Latitud del centroide geográfico", example=-2.167
    )
    lon_centroide: float | None = Field(
        None, description="Longitud del centroide geográfico", example=-79.916
    )
    indice_riesgo: float = Field(
        ..., description="Índice de riesgo ponderado normalizado (0.0 a 1.0)", example=0.74
    )
    nivel_riesgo: str = Field(
        ..., description="Categoría de riesgo: BAJO, MEDIO, ALTO, EXTREMO", example="ALTO"
    )
    precip_acumulada_24h_mm: float | None = Field(
        None, description="Precipitación acumulada en las últimas 24h en mm", example=45.5
    )
    altura_marea_m: float | None = Field(
        None, description="Altura de marea astronómica/observada en metros", example=3.85
    )
    nivel_embalse_msnm: float | None = Field(
        None, description="Nivel del embalse Daule-Peripa en msnm", example=84.2
    )
    origen_precip: str | None = Field(
        None,
        description="Fuente del dato de precipitación (estacion|satelite|respaldo)",
        example="estacion",
    )
    origen_marea: str | None = Field(None, description="Fuente del dato de marea", example="inocar")
    origen_embalse: str | None = Field(
        None, description="Fuente del dato de embalse", example="celec"
    )
    datos_completos: bool | None = Field(
        None,
        description="False si alguna variable utilizó un valor de respaldo por falta de telemetría en vivo.",
        example=True,
    )
    precip_pronostico_24h_mm: float | None = Field(
        None, description="Pronóstico de lluvia a 24 horas", example=55.0
    )
    marea_observada_m: float | None = Field(
        None, description="Marea observada en tiempo real", example=3.90
    )
    caudal_rio_m3s: float | None = Field(
        None, description="Caudal estimado del río Guayas en m3/s", example=1250.0
    )
    saturacion_antecedente_mm: float | None = Field(
        None, description="Índice de humedad antecedente del suelo", example=35.2
    )
    origen_rio: str | None = Field(
        None, description="Fuente del dato de caudal", example="geoglows"
    )
    origen_suelo: str | None = Field(
        None, description="Fuente del dato de saturación del suelo", example="copernicus"
    )
    origen_marea_obs: str | None = Field(
        None, description="Fuente de marea observada", example="inocar_realtime"
    )
    n_estaciones_precip: int | None = Field(
        None, description="Número de estaciones meteorológicas interpoladas", example=4
    )
    poblacion: int | None = Field(None, description="Población estimada en la zona", example=15200)
    exposicion_norm: float | None = Field(
        None, description="Índice de exposición poblacional/infraestructura (0 a 1)", example=0.68
    )
    indice_impacto: float | None = Field(
        None, description="Índice de impacto estimado (Riesgo × Exposición)", example=0.50
    )
    anomalia_nino12_c: float | None = Field(
        None, description="Anomalía de temperatura superficial del mar Niño 1+2 en °C", example=1.8
    )
    origen_enso: str | None = Field(
        None, description="Fuente del indicador ENSO", example="noaa_sst"
    )


class RespuestaZonas(BaseModel):
    actualizado_en: str | None = Field(
        None,
        description="Timestamp ISO-8601 de la última ejecución/batch de Spark Streaming",
        example="2026-08-01T12:00:00Z",
    )
    zonas: list[ZonaRiesgo] = Field(
        ..., description="Lista con el estado y puntuación de riesgo de cada zona urbana"
    )


class ParametrosEscenario(BaseModel):
    precip_24h_mm: float = Field(
        ..., description="Precipitación simulada en mm acumulados en 24h", example=80.0
    )
    altura_marea_m: float = Field(
        ..., description="Altura de marea astronómica simulada en metros", example=4.2
    )
    caudal_rio_m3s: float = Field(
        500.0, description="Caudal del río Guayas simulado en m3/s", example=1800.0
    )
    saturacion_antecedente_mm: float = Field(
        0.0, description="Saturación del suelo antecedente simulada en mm", example=50.0
    )
    anomalia_nino12_c: float = Field(
        0.0, description="Anomalía de TSM en región Niño 1+2 en °C", example=2.5
    )


class RespuestaEscenario(BaseModel):
    parametros: ParametrosEscenario = Field(
        ..., description="Parámetros hipotéticos introducidos en la simulación"
    )
    zonas: list[ZonaRiesgo] = Field(..., description="Evaluación simulada por cada zona urbana")


class ZonaPronostico(BaseModel):
    zona_id: str = Field(..., description="Identificador de la zona urbana", example="ZONA_001")
    nombre_sector: str | None = Field(
        None, description="Nombre legible del sector", example="Urdesa Central"
    )
    lat_centroide: float | None = Field(None, description="Latitud del centroide", example=-2.167)
    lon_centroide: float | None = Field(None, description="Longitud del centroide", example=-79.916)
    indice_riesgo: float = Field(
        ..., description="Índice de riesgo proyectado (0.0 a 1.0)", example=0.82
    )
    nivel_riesgo: str = Field(
        ..., description="Nivel de riesgo proyectado: BAJO, MEDIO, ALTO, EXTREMO", example="EXTREMO"
    )
    indice_impacto: float | None = Field(
        None, description="Índice de impacto estimado", example=0.65
    )
    horizonte_h: int = Field(
        ..., description="Horizonte del pronóstico en horas (+24h o +48h)", example=24
    )


class RespuestaPronostico(BaseModel):
    horizonte_h: int = Field(
        ..., description="Horizonte temporal del pronóstico (+24h/+48h)", example=24
    )
    zonas: list[ZonaPronostico] = Field(..., description="Resultados proyectados por zona urbana")


class ClimaPuntoResponse(BaseModel):
    temperatura_c: float | None = Field(
        None, description="Temperatura ambiente en °C", example=28.5
    )
    humedad_pct: float | None = Field(
        None, description="Humedad relativa en porcentaje (%)", example=82.0
    )
    viento_ms: float | None = Field(None, description="Velocidad del viento en m/s", example=3.4)
    descripcion: str | None = Field(
        None, description="Descripción meteorológica en español", example="lluvia moderada"
    )


class Salud(BaseModel):
    estado: str = Field("ok", description="Estado del servicio API REST", example="ok")


# --- Modelos para datos Raw de telemetría y logs ---


class EstadoENSO(BaseModel):
    """Último registro de SST/ENSO de NOAA."""

    model_config = ConfigDict(extra="allow")

    sst_nino12: float | None = Field(None, description="SST Niño 1+2 en °C")
    sst_nino34: float | None = Field(None, description="SST Niño 3.4 en °C")
    anomalia_nino12: float | None = Field(None, description="Anomalía TSM Niño 1+2 en °C")
    anomalia_nino34: float | None = Field(None, description="Anomalía TSM Niño 3.4 en °C")
    kafka_timestamp: Any | None = Field(None, description="Timestamp de ingestión Kafka")


class MareaActual(BaseModel):
    """Última lectura de marea INOCAR."""

    model_config = ConfigDict(extra="allow")

    altura_m: float | None = Field(None, description="Altura de marea en metros")
    tipo: str | None = Field(None, description="Tipo de marea (astronómica/observada)")
    kafka_timestamp: Any | None = Field(None, description="Timestamp de ingestión Kafka")


class EmbalseActual(BaseModel):
    """Nivel del embalse Daule-Peripa."""

    model_config = ConfigDict(extra="allow")

    nivel_msnm: float | None = Field(None, description="Nivel en msnm")
    kafka_timestamp: Any | None = Field(None, description="Timestamp de ingestión Kafka")


class RegistroHistoricoZona(BaseModel):
    """Un punto en la serie temporal de riesgo de una zona."""

    model_config = ConfigDict(extra="allow")

    calculado_en: Any = Field(..., description="Timestamp ISO-8601 del cálculo")
    indice_riesgo: float = Field(..., description="Índice de riesgo (0.0 a 1.0)")
    nivel_riesgo: str = Field(..., description="BAJO, MEDIO, ALTO, EXTREMO")
    precip_acumulada_24h_mm: float | None = None
    altura_marea_m: float | None = None
    nivel_embalse_msnm: float | None = None
    datos_completos: bool | None = None


class RegistroAlerta(BaseModel):
    """Alerta o boletín de la SNGR."""

    model_config = ConfigDict(extra="allow")

    titulo: str | None = Field(None, description="Título del boletín")
    descripcion: str | None = Field(None, description="Cuerpo del boletín")
    fecha: Any | None = Field(None, description="Fecha de emisión")
    kafka_timestamp: Any | None = Field(None, description="Timestamp de ingestión Kafka")



class RegistroLog(BaseModel):
    """Línea de log parseada de un producer."""

    model_config = ConfigDict(extra="allow")

    fecha: str = Field(..., description="Timestamp del log")
    nivel: str = Field(..., description="Nivel: DEBUG, INFO, WARNING, ERROR, CRITICAL")
    logger: str = Field(..., description="Nombre del logger")
    mensaje: str = Field(..., description="Contenido del mensaje")


DatoTelemetriaRaw = dict[str, Any] | list[Any]
