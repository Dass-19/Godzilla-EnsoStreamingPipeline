FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY api/requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
