---
id: 20260927145504
type: gotcha
status: evergreen
title: "Gotcha: Compatibilidad de datetime.UTC entre Python 3.10 y Python 3.11+"
created: 2026-09-27
---

# Gotcha: `datetime.UTC` en Python 3.10 vs 3.11+

## Problema
En Python 3.11 se incorporó el alias canónico `datetime.UTC`. En entornos de ejecución que utilicen Python 3.10 (como algunos hosts de desarrollo locales), la importación:
```python
from datetime import UTC
```
produce un `ImportError: cannot import name 'UTC' from 'datetime'`.

## Solución en el Proyecto
1. En `tests/conftest.py` se implementa un shim de retrocompatibilidad antes de cargar cualquier módulo:
   ```python
   import datetime as _dt
   if not hasattr(_dt, "UTC"):
       _dt.UTC = _dt.timezone.utc
   ```
2. En código nuevo o refactorizado que deba ejecutarse fuera del contenedor, importar siempre de forma segura:
   ```python
   try:
       from datetime import UTC
   except ImportError:
       from datetime import timezone
       UTC = timezone.utc
   ```
