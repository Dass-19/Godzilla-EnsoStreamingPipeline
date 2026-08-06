"""
Smoke tests de integración frontend ↔ backend.
Verifican forma de respuesta y status codes de los endpoints principales.
"""

import os
import pathlib
import sys
import pytest
from fastapi.testclient import TestClient

RAIZ_REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_REPO / "backend"))
os.environ.setdefault("SPARK_APP_DIR", str(RAIZ_REPO / "backend" / "spark"))


@pytest.fixture(scope="module")
def client():
    from api.app import app
    return TestClient(app, follow_redirects=False)


def test_redirect_root(client):
    """Cambio 1: GET / → 302 /dashboard."""
    r = client.get("/")
    assert r.status_code == 302
    assert "/dashboard" in r.headers.get("location", "")


def test_salud_envelope_contract(client):
    """El envelope RespuestaAPI tiene las 4 claves que parseResponse() espera."""
    r = client.get("/api/salud")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) >= {"status", "data", "error", "meta"}
    assert body["status"] == "success"
    assert body["data"]["estado"] == "ok"
    assert body["error"] is None
    assert "api_version" in body["meta"]


def test_openapi_schema_builds(client):
    """Verifica que el schema OpenAPI se genera sin errores."""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    assert "paths" in schema
    assert "/api/riesgo/zonas" in schema["paths"]
    assert "/api/enso/estado" in schema["paths"]
    assert "/api/mareas/actual" in schema["paths"]
    assert "/api/embalse/actual" in schema["paths"]
    assert "/api/clima/punto" in schema["paths"]
    assert "/api/escenario/simular" in schema["paths"]
    assert "/api/logs" in schema["paths"]


def test_error_response_has_envelope(client):
    """Los errores HTTP también siguen el envelope RespuestaAPI."""
    r = client.get("/api/riesgo/zonas")
    if r.status_code != 200:
        body = r.json()
        assert body["status"] == "error"
        assert body["error"]["mensaje"]
        assert body["error"]["tipo"]
