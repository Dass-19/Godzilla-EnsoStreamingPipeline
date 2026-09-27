#!/usr/bin/env python3
"""
Script ejecutable para smoke tests rápidos de la API FastAPI.
Valida el status y el envelope RespuestaAPI de los endpoints principales sin requerir cluster en vivo.
"""

import datetime as _dt
import os
import sys
from pathlib import Path

# Shim de compatibilidad UTC para Python 3.10
if not hasattr(_dt, "UTC"):
    _dt.UTC = _dt.timezone.utc  # noqa: UP017

# Agregar backend al sys.path
RAIZ = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(RAIZ / "backend"))
os.environ.setdefault("SPARK_APP_DIR", str(RAIZ / "backend" / "spark"))

try:
    from api.app import app
    from fastapi.testclient import TestClient
except Exception as e:
    print(f"[ERROR] No se pudo importar la aplicación FastAPI: {e}", file=sys.stderr)
    sys.exit(1)


def main():
    print("=" * 60)
    print("EJECUTANDO SMOKE TESTS DE API (FASTAPI)")
    print("=" * 60)

    client = TestClient(app, follow_redirects=False)
    fallos = 0

    # 1. Test Redirección Raíz
    r_raiz = client.get("/")
    if r_raiz.status_code == 302 and "/dashboard" in r_raiz.headers.get("location", ""):
        print("[OK] GET / -> 302 /dashboard")
    else:
        print(f"[FALLO] GET / retorno {r_raiz.status_code}", file=sys.stderr)
        fallos += 1

    # 2. Test Endpoint Salud
    r_salud = client.get("/api/salud")
    if r_salud.status_code == 200:
        data = r_salud.json()
        if data.get("status") == "success" and data.get("data", {}).get("estado") == "ok":
            print("[OK] GET /api/salud -> 200 y envelope valido")
        else:
            print(f"[FALLO] GET /api/salud payload no cumple envelope: {data}", file=sys.stderr)
            fallos += 1
    else:
        print(f"[FALLO] GET /api/salud retorno {r_salud.status_code}", file=sys.stderr)
        fallos += 1

    # 3. Test OpenAPI Schema
    r_openapi = client.get("/openapi.json")
    if r_openapi.status_code == 200 and "paths" in r_openapi.json():
        print("[OK] GET /openapi.json -> 200 y schema estructurado")
    else:
        print(f"[FALLO] GET /openapi.json retorno {r_openapi.status_code}", file=sys.stderr)
        fallos += 1

    # 4. Test Simulación de Escenario
    r_sim = client.get("/api/escenario/simular?precip_24h_mm=50&altura_marea_m=2.5&caudal_rio_m3s=800")
    if r_sim.status_code == 200:
        data = r_sim.json()
        zonas = data.get("data", {}).get("zonas", [])
        if data.get("status") == "success" and len(zonas) > 0 and "indice_riesgo" in zonas[0]:
            print("[OK] GET /api/escenario/simular -> 200 y calculo correcto")
        else:
            print(f"[FALLO] GET /api/escenario/simular payload invalido: {data}", file=sys.stderr)
            fallos += 1
    else:
        print(f"[FALLO] GET /api/escenario/simular retorno {r_sim.status_code}", file=sys.stderr)
        fallos += 1

    print("=" * 60)
    if fallos == 0:
        print("[EXITO] Todos los smoke tests pasaron satisfactoriamente.")
        sys.exit(0)
    else:
        print(f"[ERROR] {fallos} prueba(s) fallaron.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
