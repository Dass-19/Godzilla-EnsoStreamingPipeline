"""
Los módulos del proyecto no están empaquetados: cada contenedor los recibe en
la raíz de su WORKDIR (`contracts.py` y `risk_index.py` viajan por `--py-files`
o por COPY). Para los tests se replica esa disposición agregando al path los
directorios que en runtime son la raíz de import.
"""

import sys
import types
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

for directorio in (
    RAIZ / "backend",  # contracts.py
    RAIZ / "backend" / "spark",  # risk_index.py, spark_streaming_job.py
    RAIZ / "backend" / "producers",
):
    ruta = str(directorio)
    if ruta not in sys.path:
        sys.path.insert(0, ruta)


try:  # pragma: no cover - depende del entorno
    import kafka  # noqa: F401
except ImportError:
    # Cada productor importa `common.kafka_client` (y con él `kafka`) al
    # cargarse, pero los tests de contrato solo ejercitan funciones puras.
    # Con un stub mínimo esos tests corren en cualquier checkout, sin exigir
    # kafka-python-ng: si se saltaran, el contrato dejaría de estar cubierto
    # justo donde más se rompe.
    _kafka = types.ModuleType("kafka")
    _errores = types.ModuleType("kafka.errors")
    _errores.KafkaError = type("KafkaError", (Exception,), {})
    _kafka.KafkaProducer = object
    _kafka.errors = _errores
    sys.modules["kafka"] = _kafka
    sys.modules["kafka.errors"] = _errores

try:
    import pyspark  # noqa: F401
except ImportError:
    _pyspark = types.ModuleType("pyspark")
    _sql = types.ModuleType("pyspark.sql")
    _functions = types.ModuleType("pyspark.sql.functions")
    _types = types.ModuleType("pyspark.sql.types")

    class _Dummy:
        def __init__(self, *args, **kwargs):
            pass

        def __call__(self, *args, **kwargs):
            return self

    _sql.DataFrame = _Dummy
    _sql.SparkSession = _Dummy
    _pyspark.sql = _sql
    _pyspark.sql.functions = _functions
    _pyspark.sql.types = _types

    for tname in [
        "StringType",
        "DoubleType",
        "BooleanType",
        "LongType",
        "StructField",
        "StructType",
    ]:
        setattr(_types, tname, _Dummy)

    sys.modules["pyspark"] = _pyspark
    sys.modules["pyspark.sql"] = _sql
    sys.modules["pyspark.sql.functions"] = _functions
    sys.modules["pyspark.sql.types"] = _types
