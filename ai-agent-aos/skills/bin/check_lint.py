#!/usr/bin/env python3
"""
Script cross-platform para ejecutar ruff linter y formateador sobre el repositorio.
"""

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent.parent


def main():
    print("=" * 60)
    print("EJECUTANDO RUFF LINTER Y VERIFICACION DE CODIGO")
    print("=" * 60)

    cmd = [sys.executable, "-m", "ruff", "check", str(RAIZ)]
    res = subprocess.run(cmd, cwd=RAIZ)

    print("=" * 60)
    if res.returncode == 0:
        print("[EXITO] No se encontraron errores de linting.")
    else:
        print(f"[FALLO] Ruff reporto problemas (codigo {res.returncode}).", file=sys.stderr)
    sys.exit(res.returncode)


if __name__ == "__main__":
    main()
