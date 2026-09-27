---
id: 20260927152006
type: skill-spec
status: evergreen
name: "testing"
runtime: python3 / pytest
entrypoint: "pytest -v"
inputs:
  - name: test_path
    type: string
    description: "Ruta de la suite o archivo de pruebas a ejecutar"
    required: false
outputs:
  format: "stdout / pytest-report"
created: 2026-09-27
updated: 2026-09-27
---

# Skill: Testing & Quality Assurance

> **Propósito**: Guiar la ejecución, escritura y mantenimiento de pruebas automatizadas con pytest en [`tests/`](file:///c:/Users/H%20P/Desktop/Dass/university/6S/IDED%20&%20VD/Godzilla-EnsoStreamingPipeline/tests/).

---

## 1. Convenciones Fundamentales de Testing

1. **Cero Mocks HTTP**:
   - Nunca usar `unittest.mock` ni `monkeypatch` para simular llamadas de red.
   - Las pruebas de contrato prueban funciones puras de transformación y parseo (`parse_*`, `construir_*`) contra fixtures estáticas reales.
2. **Nombres de Tests en Español Afirmativo**:
   - Estilo: `test_parse_precipitacion_toma_el_dia_mas_reciente_con_dato`, `test_mas_lluvia_no_baja_el_riesgo`.
3. **Docstrings de Regresión**:
   - Cada test que previene un bug histórico documenta la causa raíz y el caso borde en su docstring.
4. **Independencia del Reloj en Parseos Temporales**:
   - Si una función compara fechas con la hora actual (ej. `parse_lluvia_estaciones`), pasar un argumento explícito `ahora` en el test para evitar fallos intermitentes.
5. **Aislamiento en `conftest.py`**:
   - Provee stubs mínimos para `kafka` y `pyspark` cuando no están instalados en el host local.

---

## 2. Checklist de Verificación
- [ ] `pytest tests -q` pasa al 100%.
- [ ] `ruff check .` no arroja errores.
- [ ] Todo cambio en contratos incluye su test de round-trip en `tests/test_contracts.py`.
