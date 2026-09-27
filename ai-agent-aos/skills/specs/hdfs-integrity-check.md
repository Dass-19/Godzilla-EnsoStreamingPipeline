---
id: 20260927145514
type: skill-spec
status: evergreen
name: "hdfs-integrity-check"
runtime: python3
entrypoint: "backend/api/hdfs_client.py"
inputs:
  - name: path
    type: string
    description: "Ruta base en HDFS para verificar"
    required: true
outputs:
  format: "stdout | exit-code"
created: 2026-09-27
---

# Skill: HDFS Integrity Check

> **Propósito**: Verificar la accesibilidad y consistencia de las particiones Parquet y logs en HDFS a través de WebHDFS.

## Cuándo Usar
Usar para diagnosticar caídas del clúster Hadoop, particiones corruptas o verificar que Spark esté escribiendo en las rutas esperadas (`/enso_data/processed/indice_riesgo` y `/enso_data/raw/*`).

## Comando de Ejecución
```bash
python -c "from backend.api.hdfs_client import get_client, _listar; client = get_client('http://localhost:9870', 'root'); print(_listar(client, '/enso_data/processed/indice_riesgo'))"
```
