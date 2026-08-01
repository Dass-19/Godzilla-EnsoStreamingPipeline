---
name: testing
description: 'Use this skill when running, writing, expanding, or debugging automated pytest tests in tests/. Covers unit testing for mathematical risk algorithms (risk_index.py), spatial interpolation (interpolacion.py), contract verification (contracts.py), producer output envelopes (test_producers_contract.py), and test coverage reporting. Trigger phrases: "testing", "run tests", "pytest", "unit test", "contract test", "test coverage", "write tests".'
---

# Testing & Quality Assurance Skill

## Overview
This skill governs the automated testing strategy for the Godzilla ENSO Streaming Pipeline. All test suites reside under `tests/` and utilize `pytest` for unit, contract, and mathematical verification.

---

## 1. Test Architecture & Directory Layout

```
tests/
├── conftest.py                   # Shared pytest fixtures, sample dataframes, mock configs
├── test_contracts.py             # Validation of Pydantic models & schemas in contracts.py
├── test_producers_contract.py    # Ensures all producer outputs follow the JSON envelope specification
├── test_risk_index.py            # Unit tests for mathematical risk score equations
├── test_interpolacion.py         # Unit tests for IDW spatial interpolation algorithms
└── test_estado_fuentes.py        # Ingestion sources status and freshness checks
```

---

## 2. Test Execution Commands

Run tests using the project virtual environment:

```powershell
# Run the entire test suite
.\.venv\Scripts\pytest tests/

# Run tests with code coverage report
.\.venv\Scripts\pytest --cov=backend tests/

# Run a single test module
.\.venv\Scripts\pytest tests/test_risk_index.py

# Run specific test function by name filter
.\.venv\Scripts\pytest tests/ -k "test_calcular_indice_riesgo"
```

---

## 3. Testing Principles & Best Practices

1. **No External Network Dependencies**: Tests must NEVER make live HTTP calls to external APIs (OpenWeatherMap, NOAA) or require a live HDFS cluster. Use mock fixtures (`unittest.mock` or `monkeypatch`).
2. **Boundary & Stress Testing**:
   - **Precipitación**: Test `0.0 mm` (dry day) vs `250.0 mm` (torrential storm).
   - **Marea**: Test `0.0 m` vs `5.0 m` (high spring tide).
   - **Anomalía ENSO**: Test negative anomalies (La Niña) vs `+3.5 °C` (Extreme El Niño).
3. **Contract Enforcement**: Any new field added to `backend/contracts.py` must be accompanied by corresponding assertions in `tests/test_contracts.py` and `tests/test_producers_contract.py`.
4. **Deterministic Math**: Risk scores must satisfy $0.0 \le I_R \le 1.0$ and return predictable risk levels (`BAJO`, `MEDIO`, `ALTO`, `EXTREMO`).

---

## 4. Key Files

- **Fixtures**: [`tests/conftest.py`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/tests/conftest.py)
- **Contratos**: [`tests/test_contracts.py`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/tests/test_contracts.py)
- **Productores**: [`tests/test_producers_contract.py`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/tests/test_producers_contract.py)
- **Riesgo**: [`tests/test_risk_index.py`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/tests/test_risk_index.py)
- **Interpolación**: [`tests/test_interpolacion.py`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/tests/test_interpolacion.py)

---

## 5. Verification Checklist

Before committing code:
- [ ] Run full pytest suite: `.\.venv\Scripts\pytest tests/`
- [ ] All tests pass with zero errors or failures.
- [ ] Ensure test coverage does not regress.
