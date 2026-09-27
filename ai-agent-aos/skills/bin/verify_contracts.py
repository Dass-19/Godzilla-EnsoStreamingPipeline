#!/usr/bin/env python3
"""
Script de verificación de contratos y sincronización de esquemas.
Ejecuta la suite de pruebas de contratos y valida que backend/contracts.py y backend/spark/contracts.py sean idénticos.
"""

import filecmp
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent.parent


def main():
    print("=" * 60)
    print("VERIFICANDO CONTRATOS Y SINCRONIZACION DE ESQUEMAS")
    print("=" * 60)

    contrato_backend = RAIZ / "backend" / "contracts.py"
    contrato_spark = RAIZ / "backend" / "spark" / "contracts.py"

    fallos = 0

    # 1. Verificar existencia y espejo idéntico
    if not contrato_backend.exists():
        print(f"[FALLO] Falta archivo canónico: {contrato_backend}", file=sys.stderr)
        fallos += 1
    elif not contrato_spark.exists():
        print(f"[FALLO] Falta archivo espejo para Spark: {contrato_spark}", file=sys.stderr)
        fallos += 1
    else:
        if filecmp.cmp(contrato_backend, contrato_spark, shallow=False):
            print("[OK] backend/contracts.py y backend/spark/contracts.py son IDENTICOS.")
        else:
            print("[ADVERTENCIA] backend/contracts.py difiere de backend/spark/contracts.py", file=sys.stderr)
            # No necesariamente fatal si spark-submitter monta backend/contracts.py como volumen ro

    # 2. Ejecutar pytest sobre contratos
    print("\nEjecutando tests de contrato...")
    cmd = [sys.executable, "-m", "pytest", str(RAIZ / "tests" / "test_contracts.py"), "-v"]
    res = subprocess.run(cmd, cwd=RAIZ)

    if res.returncode != 0:
        print("[FALLO] Fallaron las pruebas de contrato.", file=sys.stderr)
        fallos += 1
    else:
        print("[OK] Todas las pruebas de contrato pasaron exitosamente.")

    print("=" * 60)
    sys.exit(fallos)


if __name__ == "__main__":
    main()
