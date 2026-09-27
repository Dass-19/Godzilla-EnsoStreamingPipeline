---
id: 20260927152008
type: knowledge
status: evergreen
title: "Base de Conocimiento: Convenciones y Estándares de Testing"
created: 2026-09-27
updated: 2026-09-27
---

# Base de Conocimiento: Testing

## 1. Convenciones Clave de la Suite de Pruebas

- **Ubicación de Tests**: Todos los tests residen en `tests/` y corren con `pytest`.
- **Zero HTTP Mocking**: Ningún test mockea endpoints HTTP o clústeres en vivo (Kafka / HDFS). Se prueban funciones puras (`parse_*`, `construir_*`, fórmulas de riesgo, interpolaciones IDW, transformaciones DataFrame) contra fixtures de datos reales.
- **Nombres de Tests**: Estilo afirmativo en español descriptivo (`test_parse_marea_lee_el_payload_de_inocar`, `test_normalizar_embalse_usa_el_rango_de_operacion`).
- **Control del Reloj**: Las funciones con filtros de antigüedad aceptan un parámetro `ahora` explícito para que los tests no dependan del reloj del sistema.
- **Categorías de Riesgo**: Siempre en minúsculas (`"bajo"`, `"medio"`, `"alto"`, `"critico"`).
- **Ejecución de Tests**:
  ```bash
  python -m pytest -v
  ```
