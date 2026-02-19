"""CRUD RAG-экземпляров: создание, список, по id, удаление."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.fuseki_admin import create_dataset, delete_dataset, rag_prod_dataset
from app.models import RagInstance, RagMember, Task, User

router = APIRouter()


class RAGCreateBody(BaseModel):
    name: str
    description: str | None = None


class RAGResponse(BaseModel):
    id: int
    owner_id: int
    name: str
    description: str | None
    fuseki_dataset: str
    cycle_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


def _can_access_rag(db: Session, user: User, rag_id: int) -> RagInstance | None:
    """Проверить доступ (owner или member). Вернуть RAG или None."""
    rag = db.get(RagInstance, rag_id)
    if not rag:
        return None
    if rag.owner_id == user.id:
        return rag
    member = db.get(RagMember, (rag_id, user.id))
    if member:
        return rag
    return None


def _is_owner(user: User, rag: RagInstance) -> bool:
    return rag.owner_id == user.id


@router.post("", response_model=RAGResponse)
def create_rag(
    body: RAGCreateBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Создать RAG. Текущий пользователь — владелец. В Fuseki создаётся prod-датасет."""
    rag = RagInstance(
        owner_id=current_user.id,
        name=body.name,
        description=body.description,
        fuseki_dataset="ferag-00000",  # placeholder, перезапишем после flush
    )
    db.add(rag)
    db.flush()
    rag.fuseki_dataset = rag_prod_dataset(rag.id)
    db.commit()
    db.refresh(rag)
    create_dataset(rag.fuseki_dataset)
    return rag


@router.get("", response_model=list[RAGResponse])
def list_rags(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список RAG текущего пользователя (владелец или участник)."""
    owned = db.query(RagInstance).filter(RagInstance.owner_id == current_user.id).all()
    member_rag_ids = [m.rag_id for m in db.query(RagMember).filter(RagMember.user_id == current_user.id).all()]
    if member_rag_ids:
        member_rags = db.query(RagInstance).filter(RagInstance.id.in_(member_rag_ids)).all()
        owned_ids = {r.id for r in owned}
        for r in member_rags:
            if r.id not in owned_ids:
                owned.append(r)
    return owned


@router.get("/{rag_id}", response_model=RAGResponse)
def get_rag(
    rag_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """RAG по id. Доступ только у владельца или участника."""
    rag = _can_access_rag(db, current_user, rag_id)
    if not rag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RAG not found")
    return rag


@router.delete("/{rag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rag(
    rag_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Удалить RAG. Только владелец. Запущенных задач быть не должно. Prod-датасет в Fuseki удаляется (ошибку не поднимаем)."""
    rag = _can_access_rag(db, current_user, rag_id)
    if not rag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RAG not found")
    if not _is_owner(current_user, rag):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner can delete")
    running = db.query(Task).filter(Task.rag_id == rag_id, Task.status == "running").first()
    if running:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete: there are running tasks",
        )
    ds_name = rag.fuseki_dataset
    db.delete(rag)
    db.commit()
    try:
        delete_dataset(ds_name)
    except Exception:
        pass
    return None
