---
id: 20260927145507
type: gotcha
status: evergreen
title: "Gotcha: Parseo de Fechas de INAMHI y Huso Horario UTC-5 de Ecuador"
created: 2026-09-27
---

# Gotcha: Parseo de Fechas de INAMHI y Huso Horario

## Problema
La API Visor de INAMHI entrega el campo `fecha_ultimo_dato` o `fecha_observacion` en formato ISO sin sufijo de huso horario (ej: `"2026-07-31T14:00:00"`), correspondiente a la hora local de Ecuador (`America/Guayaquil`, UTC-5). Si se compara ingenuamente contra `datetime.utcnow()`, se produce un desfasaje de 5 horas que descarta erróneamente mediciones recientes por superar el umbral de antigüedad (`max_antiguedad_horas`).

## Solución en el Proyecto
En `backend/contracts.py` (`parse_lluvia_estaciones`):
```python
momento_actual = ahora if ahora is not None else datetime.utcnow() - timedelta(hours=5)
```
1. Si no se provee un timestamp explícito, se ajusta el reloj de referencia restando 5 horas a UTC.
2. La función admite el argumento `ahora` para permitir pruebas unitarias deterministas y desacopladas del reloj del sistema.
