"""Эндпоинты статуса задач: по id и список по RAG (для polling)."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models import Task, User
from app.routers.rags import _can_access_rag

router = APIRouter()


class TaskResponse(BaseModel):
    id: int
    rag_id: int
    cycle_id: int | None
    type: str
    status: str
    error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Статус задачи по id. Доступ только если пользователь имеет доступ к RAG задачи."""
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    rag = _can_access_rag(db, current_user, task.rag_id)
    if not rag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.get("/rags/{rag_id}/tasks", response_model=list[TaskResponse])
def list_rag_tasks(
    rag_id: int,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список задач RAG с пагинацией. Доступ только у владельца или участника RAG."""
    rag = _can_access_rag(db, current_user, rag_id)
    if not rag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RAG not found")
    tasks = db.query(Task).filter(Task.rag_id == rag_id).order_by(Task.id.desc()).offset(skip).limit(limit).all()
    return tasks
