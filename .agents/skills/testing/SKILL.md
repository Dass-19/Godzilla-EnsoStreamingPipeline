---
name: testing
description: 'Use this skill when running, writing, expanding, or debugging automated pytest tests in tests/. Covers the pure-function/no-HTTP-mocking convention, contract verification (contracts.py), the pyspark/kafka import stubs in conftest.py, and the repo test-naming style. Trigger phrases: "testing", "run tests", "pytest", "unit test", "contract test", "test coverage", "write tests".'
---

# Testing & Quality Assurance Skill

## Overview
All tests live under `tests/` and run with plain `pytest`, no Docker and no live pipeline required —
`pip install -r requirements-dev.txt` is enough. This is what CI runs.

---

## 1. Directory Layout

```
tests/
├── conftest.py                   # sys.path setup + stubs for `kafka`/`pyspark` when not installed
├── test_contracts.py             # contracts.py: construir_*/parse_* round-trips, fixtures = real payload shapes
├── test_producers_contract.py     # imports real producer_*.py modules, exercises their pure functions
├── test_risk_index.py            # risk_index.py: normalizers, weights, interaction terms
├── test_interpolacion.py         # interpolacion.py: IDW correctness
└── test_estado_fuentes.py        # EstadoFuentes (spark_streaming_job.py) without a real SparkSession
```

`conftest.py` doesn't set up fixtures or sample dataframes — its whole job is making the modules
importable outside their containers: it adds `backend/`, `backend/spark/` and `backend/producers/` to
`sys.path` (they're not packaged; each container gets them via `COPY`/`--py-files` at its WORKDIR root),
and stubs `kafka`/`pyspark` with minimal fake modules if they aren't installed, so contract tests run on
any checkout without those heavy dependencies.

---

## 2. Run

```bash
pip install -r requirements-dev.txt
pytest tests -q
pytest tests/test_contracts.py::test_parse_precipitacion_toma_el_dia_mas_reciente_con_dato  # one test
ruff check .              # ruff check --fix . to auto-fix
```

(No `.venv\Scripts\pytest` assumption — whatever `pytest` resolves to on `PATH` after the `pip install`
above is what CI uses too.)

---

## 3. The load-bearing convention: zero HTTP mocking

**Tests never mock external HTTP calls or a live HDFS/Kafka cluster.** Every test — including the
producer ones — exercises a pure function: a parser, a formula, a fallback model, a fixed-input parsing
routine. `test_producers_contract.py`'s own docstring states this directly: it imports the real
`producer_*.py` modules and calls their pure functions (`_extraer_nivel_embalse`, `_ventana_fechas`,
`_modelo_armonico_fallback`, …), never the network-touching `fetch_*`/`run_producer` entry points. If a
producer needs an optional dependency to import (`pdfplumber`, `requests`), the test uses
`pytest.importorskip(...)` rather than mocking it away.

This also means: don't introduce `unittest.mock`/`monkeypatch`-based HTTP mocking to test a new producer.
Instead, extract the pure transformation logic into its own function and test that directly, the way
`producer_inocar_mareas._modelo_armonico_fallback()` and `producer_celec_embalse._extraer_nivel_embalse()`
already do.

---

## 4. Style

- **Test names**: Spanish, affirmative-sentence style —
  `test_parse_precipitacion_toma_el_dia_mas_reciente_con_dato`,
  `test_mas_lluvia_no_baja_el_riesgo`. Not `test_parse_precipitacion` / `test_case_1`.
- **Fixtures**: module-level UPPER_CASE constants shaped like the real payload
  (`PAYLOAD_MAREA_INOCAR`, `ZONA_LLANA`), not fixture factories, unless the shape needs runtime
  parameters.
- **Floats**: always `pytest.approx(...)`.
- **Regression tests carry a docstring** explaining the historical bug they pin down (e.g.
  `test_normalizar_embalse_usa_el_rango_de_operacion` explains the cota/umbral-de-alerta bug it guards
  against). A new bugfix should get the same treatment: a test whose name and docstring describe the
  failure mode, not just the current correct behavior.
- **Time-dependent parsing**: if a parser compares a payload's timestamp against "now" (e.g.
  `parse_lluvia_estaciones`'s freshness filter), thread an explicit `ahora`/`referencia` parameter through
  so the test controls the clock — never assert against `datetime.now()` at test time, the suite must
  stay green regardless of what day it's run on.

---

## 5. Risk categories, for anyone writing risk-related tests

`nivel_riesgo` is one of `"bajo" | "medio" | "alto" | "critico"` (lowercase Spanish), never
`BAJO/MEDIO/ALTO/EXTREMO`. `test_niveles_de_riesgo_cubren_las_cuatro_categorias` in
`test_risk_index.py` is the canonical check that all four are still reachable.

---

## 6. Key Files

- **Fixtures / import shims**: [tests/conftest.py](../../../tests/conftest.py)
- **Contratos**: [tests/test_contracts.py](../../../tests/test_contracts.py)
- **Productores**: [tests/test_producers_contract.py](../../../tests/test_producers_contract.py)
- **Riesgo**: [tests/test_risk_index.py](../../../tests/test_risk_index.py)
- **Interpolación**: [tests/test_interpolacion.py](../../../tests/test_interpolacion.py)
- **Estado de fuentes**: [tests/test_estado_fuentes.py](../../../tests/test_estado_fuentes.py)

---

## 7. Verification Checklist

- [ ] `pytest tests -q` — all green.
- [ ] `ruff check .` — no new findings introduced by your change (pre-existing ones aren't yours to fix
      incidentally; check with `git stash` + `ruff check <file>` if unsure whether a finding predates you).
- [ ] Any new/changed `contracts.py` field has a round-trip test in `test_contracts.py`.
- [ ] No test reaches out over the network or mocks one that does — if you found yourself needing
      `monkeypatch`/`unittest.mock` for HTTP, extract a pure function instead.
