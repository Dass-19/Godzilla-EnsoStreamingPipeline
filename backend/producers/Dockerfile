FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# earthengine-api requires this to run properly in some envs
RUN pip install cryptography earthengine-api

COPY . .

CMD ["python", "run_producers.py"]
