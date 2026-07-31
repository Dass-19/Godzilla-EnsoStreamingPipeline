# El contexto de build es `backend/`, no `backend/producers/`: los productores
# importan `contracts.py`, el módulo compartido con el job de Spark que define
# el shape de los payloads del índice de riesgo.
FROM python:3.11-slim

WORKDIR /app

COPY producers/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY producers/ .
COPY contracts.py ./contracts.py

CMD ["python", "run_producers.py"]
