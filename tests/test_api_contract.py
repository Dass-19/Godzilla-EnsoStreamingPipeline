"""
Tests del contrato API ↔ Frontend.
Verifican que la estructura de RespuestaAPI y los cambios de refactoring
no rompen lo que parseResponse() espera en client.js.
"""

import pathlib
import sys

from fastapi.testclient import TestClient

RAIZ_REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_REPO / "backend"))


def _make_client():
    """Crea el TestClient importando app con las vars de entorno correctas."""
    import os

    os.environ.setdefault("SPARK_APP_DIR", str(RAIZ_REPO / "backend" / "spark"))
    from api.app import app

    return TestClient(app, follow_redirects=False)


class TestRedirect:
    """Cambio 1: GET / redirige a /dashboard."""

    def test_raiz_redirige_a_dashboard(self):
        client = _make_client()
        r = client.get("/")
        assert r.status_code == 302
        assert r.headers["location"] == "/dashboard"

    def test_raiz_no_aparece_en_openapi(self):
        from api.app import app

        paths = app.openapi()["paths"]
        assert "/" not in paths


class TestEnvelopeContract:
    """
    parseResponse() en client.js espera:
    - body.status === 'success'
    - body.data   (el payload)
    - body.error  (null en éxito)
    - body.meta   (objeto con api_version, timestamp, fuente, total_registros)
    """

    def test_salud_envelope_shape(self):
        client = _make_client()
        r = client.get("/api/salud")
        assert r.status_code == 200
        body = r.json()

        assert "status" in body
        assert "data" in body
        assert body["status"] == "success"
        assert "meta" in body
        meta = body["meta"]
        assert "api_version" in meta
        assert "timestamp" in meta


class TestFrontendFieldContract:
    """
    Verifica que los modelos Pydantic con `extra='allow'` no filtran campos
    que el frontend necesita (especialmente `json_str`).
    """

    def test_extra_allow_preserva_json_str(self):
        from pydantic import BaseModel, ConfigDict

        class EstadoENSO(BaseModel):
            model_config = ConfigDict(extra="allow")
            sst_nino12: float | None = None
            kafka_timestamp: str | None = None

        row = {
            "json_str": '{"data": [{"regions": {}}]}',
            "kafka_timestamp": "2026-08-01T12:00:00Z",
        }
        out = EstadoENSO(**row).model_dump()
        assert "json_str" in out, "json_str fue filtrado"

    def test_extra_allow_preserva_campos_futuros(self):
        from pydantic import BaseModel, ConfigDict

        class MareaActual(BaseModel):
            model_config = ConfigDict(extra="allow")
            altura_m: float | None = None

        row = {"altura_m": 3.5, "campo_nuevo_del_producer": "valor"}
        out = MareaActual(**row).model_dump()
        assert "campo_nuevo_del_producer" in out



class TestCacheDoesNotAlterPayload:
    """
    Cambio 3: La caché TTL devuelve el mismo dict que _respuesta_exitosa().
    """

    def test_cache_ttl_devuelve_mismo_dict(self):
        from api.app import _CacheTTL

        cache = _CacheTTL(ttl_segundos=15.0)
        payload = {
            "status": "success",
            "data": {"zonas": [{"zona_id": "ZONA_001", "indice_riesgo": 0.7}]},
            "meta": {"api_version": "1.2.0"},
        }
        cache.set("test", payload)
        assert cache.get("test") is payload
        assert cache.get("test")["data"]["zonas"][0]["zona_id"] == "ZONA_001"
