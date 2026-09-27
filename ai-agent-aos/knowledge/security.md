---
id: 20260927145503
type: knowledge
status: evergreen
title: "Base de Conocimiento: Seguridad, Secretos y Sanitización"
created: 2026-09-27
---

# Base de Conocimiento: Seguridad

## 1. Manejo de Secretos y Credenciales

1. **Variables de Entorno**:
   - Todas las credenciales sensibles residen exclusivamente en `backend/env/.env`.
   - `.env` está en `.gitignore` y **nunca debe comitearse**.
   - Se mantiene un archivo de plantilla `backend/env/.env.example` con valores ficticios.
2. **Google Earth Engine (GEE)**:
   - Requiere un archivo JSON de Service Account montado en el contenedor en `/app/ensostreamingpipeline-7f414895f6f4.json`.
   - El script `producer_gee.py` inicializa las credenciales de forma segura y no expone el contenido del JSON.
3. **OpenWeatherMap API Key**:
   - Vive en el entorno del servidor backend (`OPENWEATHERMAP_API_KEY`).
   - **Prohibido en Frontend**: El frontend jamás realiza peticiones directas a OpenWeatherMap con la key. Utiliza el endpoint proxy `/api/clima/punto` y `/api/clima/tiles/...`.

---

## 2. Sanitización y Validación de Entradas

1. **Modelos Pydantic (`backend/api/schemas.py`)**:
   - Todas las respuestas y parámetros son validados mediante esquemas Pydantic estrictos.
2. **Parámetros Query / Path**:
   - Nombres de productores restringidos por regex `^[a-z0-9_]+$`.
   - Coordenadas geográficas validadas en rangos $[-90, 90]$ y $[-180, 180]$.
   - Niveles de log acotados a enum `(DEBUG|INFO|WARNING|ERROR|CRITICAL)`.
3. **CORS (Cross-Origin Resource Sharing)**:
   - Configurado en `backend/api/helpers.py` permitiendo solo los orígenes configurados en la variable de entorno `CORS_ORIGINS` (por defecto `http://localhost:8000`, `http://127.0.0.1:8000`).

---

## 3. Resiliencia y Control de Excepciones

- **Manejador de Errores Unificado**: FastAPI intercepta excepciones y devuelve el envelope `RespuestaAPI` con códigos normalizados:
  - `400`: `SOLICITUD_INVALIDA`
  - `404`: `RECURSO_NO_ENCONTRADO`
  - `502`: `PROVEEDOR_NO_DISPONIBLE`
  - `503`: `SERVICIO_HDFS_NO_DISPONIBLE`
- **Sin Fugas de Traza Interna**: Los errores de conexión HDFS o APIs externas no deben exponer stack traces completos al cliente REST, sino un detalle estructurado y controlado.
