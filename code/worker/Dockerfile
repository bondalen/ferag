FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/worker

# graphrag-test монтируется как том (см. docker-compose.yml)
ENV PYTHONPATH=/app:/app/graphrag-test

CMD ["celery", "-A", "worker.celery_app:celery", "worker", "--loglevel=info", "--concurrency=2"]
