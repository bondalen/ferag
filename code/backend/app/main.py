"""FastAPI приложение ferag API."""
from fastapi import FastAPI

app = FastAPI(title="ferag API", root_path="/ferag/api")


@app.get("/health")
def health():
    """Проверка доступности API."""
    return {"status": "ok"}
