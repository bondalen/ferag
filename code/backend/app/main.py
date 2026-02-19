"""FastAPI приложение ferag API."""
import asyncio
import json
import sys
from pathlib import Path

# graphrag-test для RAG-чата (rag_context, rag_llm)
_project_root = Path(__file__).resolve().parent.parent.parent.parent
_graphrag_test = _project_root / "graphrag-test"
if _graphrag_test.exists() and str(_graphrag_test) not in sys.path:
    sys.path.insert(0, str(_graphrag_test))

import redis.asyncio as redis
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.db import SessionLocal
from app.deps import get_current_user_ws
from app.models import Task
from app.routers import auth as auth_router, rags as rags_router, tasks as tasks_router
from app.routers.rags import _can_access_rag

app = FastAPI(title="ferag API", root_path="/ferag/api")

app.include_router(auth_router.router, prefix="/auth", tags=["auth"])
app.include_router(rags_router.router, prefix="/rags", tags=["rags"])
app.include_router(tasks_router.router, tags=["tasks"])


@app.get("/health")
def health():
    """Проверка доступности API."""
    return {"status": "ok"}


@app.websocket("/ws/tasks/{task_id}")
async def ws_task_status(
    websocket: WebSocket,
    task_id: int,
    token: str = Query(..., description="JWT для аутентификации"),
):
    """
    WebSocket: стрим статусов задачи (running/done/failed, step, error).
    Подписка на Redis channel task:{task_id}. Закрывается при status 'done' или 'failed'.
    """
    await websocket.accept()
    db = SessionLocal()
    try:
        user = get_current_user_ws(token, db)
        task = db.get(Task, task_id)
        if not task:
            db.close()
            await websocket.close(code=1008, reason="Task not found")
            return
        if not _can_access_rag(db, user, task.rag_id):
            db.close()
            await websocket.close(code=1008, reason="Access denied")
            return
    except Exception:
        db.close()
        raise
    settings = get_settings()
    r = redis.from_url(settings.redis_url, decode_responses=True)
    pubsub = r.pubsub()
    channel = f"task:{task_id}"
    try:
        await pubsub.subscribe(channel)
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True)
            if message is None:
                await asyncio.sleep(0.2)
                continue
            if message["type"] != "message":
                continue
            data = message.get("data")
            if isinstance(data, str):
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    payload = {"status": "running", "step": "", "error": None}
            else:
                payload = {"status": "running", "step": "", "error": None}
            await websocket.send_json(payload)
            if payload.get("status") in ("done", "failed"):
                break
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
        await r.close()
        db.close()
