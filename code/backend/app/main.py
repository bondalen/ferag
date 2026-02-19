"""FastAPI приложение ferag API."""
from fastapi import FastAPI

from app.routers import auth as auth_router, rags as rags_router, tasks as tasks_router

app = FastAPI(title="ferag API", root_path="/ferag/api")

app.include_router(auth_router.router, prefix="/auth", tags=["auth"])
app.include_router(rags_router.router, prefix="/rags", tags=["rags"])
app.include_router(tasks_router.router, tags=["tasks"])


@app.get("/health")
def health():
    """Проверка доступности API."""
    return {"status": "ok"}
