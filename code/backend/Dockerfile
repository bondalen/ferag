FROM python:3.11-slim

RUN apt-get update && apt-get install -y build-essential curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

ENV PYTHONPATH=/app

EXPOSE 47821
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "47821"]
