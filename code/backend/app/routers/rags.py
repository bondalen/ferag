"""CRUD RAG-экземпляров: создание, список, по id, удаление, загрузка файла, approve цикла."""
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, status, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import get_current_user, get_db
from app.fuseki_admin import (
    create_dataset,
    delete_dataset,
    get_dataset_ttl,
    post_dataset_ttl,
    put_dataset_ttl,
    rag_ontology_dataset,
    rag_prod_dataset,
    rag_staging_dataset,
    rag_triples_dataset,
    sparql_update,
)
from app.models import RagInstance, RagMember, Task, UploadCycle, User

# Чтобы бэкенд мог вызывать start_update_chain, пакет worker должен быть на sys.path (code/)
_code_dir = Path(__file__).resolve().parent.parent.parent
if _code_dir not in [Path(p).resolve() for p in sys.path]:
    sys.path.insert(0, str(_code_dir))

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


class UploadResponse(BaseModel):
    cycle_id: int
    task_id: int


@router.post("/{rag_id}/upload", response_model=UploadResponse)
async def upload_file(
    rag_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Загрузить текстовый файл для нового цикла. Только владелец RAG.
    Создаётся UploadCycle и Task, файл сохраняется в work_dir, запускается цепочка задач.
    """
    rag = _can_access_rag(db, current_user, rag_id)
    if not rag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RAG not found")
    if not _is_owner(current_user, rag):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner can upload")
    if file.content_type and file.content_type not in ("text/plain", "application/octet-stream"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Content-Type must be text/plain or .txt file",
        )
    if file.filename and not (file.filename.endswith(".txt") or file.filename == ".txt"):
        # допускаем и без расширения
        pass  # не отклоняем
    settings = get_settings()
    work_dir = Path(settings.work_dir)
    cycle_n = rag.cycle_count + 1
    cycle = UploadCycle(rag_id=rag_id, cycle_n=cycle_n, status="pending")
    db.add(cycle)
    db.flush()
    input_dir = work_dir / f"rag_{rag_id}" / f"cycle_{cycle.id}" / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    file_path = input_dir / "source.txt"
    content = await file.read()
    file_path.write_bytes(content)
    task = Task(
        rag_id=rag_id,
        cycle_id=cycle.id,
        type="full_cycle",
        status="running",
    )
    db.add(task)
    db.commit()
    db.refresh(cycle)
    db.refresh(task)
    try:
        from worker.tasks import start_update_chain
        start_update_chain(rag_id, cycle.id, task.id, str(file_path))
    except Exception as e:
        task.status = "failed"
        task.error = str(e)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to start pipeline: {e}",
        )
    return UploadResponse(cycle_id=cycle.id, task_id=task.id)


class ApproveResponse(BaseModel):
    message: str = "approved"


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
    context_used: int


@router.post("/{rag_id}/cycles/{cycle_id}/approve", response_model=ApproveResponse)
def approve_cycle(
    rag_id: int,
    cycle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Одобрить цикл (только owner): скопировать staging (-tri, -ont) в prod, удалить staging-датасеты,
    UploadCycle.status='merged', RagInstance.cycle_count += 1.
    """
    rag = _can_access_rag(db, current_user, rag_id)
    if not rag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RAG not found")
    if not _is_owner(current_user, rag):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner can approve")
    cycle = db.get(UploadCycle, cycle_id)
    if not cycle or cycle.rag_id != rag_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cycle not found")
    if cycle.status != "review":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cycle status must be 'review', got '{cycle.status}'",
        )
    prod_ds = rag_prod_dataset(rag_id)
    cycle_n = cycle.cycle_n
    ds_tri = rag_triples_dataset(rag_id, cycle_n)
    ds_ont = rag_ontology_dataset(rag_id, cycle_n)
    ds_stg = rag_staging_dataset(rag_id, cycle_n)
    sparql_update(prod_ds, "DELETE WHERE { ?s ?p ?o }")
    tri_ttl = get_dataset_ttl(ds_tri)
    if tri_ttl.strip() and tri_ttl.strip() != "# Empty dataset\n" and tri_ttl.strip() != "# Empty\n":
        put_dataset_ttl(prod_ds, tri_ttl)
    ont_ttl = get_dataset_ttl(ds_ont)
    if ont_ttl.strip() and ont_ttl.strip() != "# Empty dataset\n" and ont_ttl.strip() != "# Empty\n":
        post_dataset_ttl(prod_ds, ont_ttl)
    for name in (ds_tri, ds_ont, ds_stg):
        try:
            delete_dataset(name)
        except Exception:
            pass
    cycle.status = "merged"
    cycle.merged_at = datetime.now(timezone.utc)
    rag.cycle_count += 1
    db.commit()
    return ApproveResponse()


@router.post("/{rag_id}/chat", response_model=ChatResponse)
def chat(
    rag_id: int,
    body: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    RAG-вопрос по графу: контекст из Fuseki (prod-датасет RAG) + ответ LLM.
    Требует graphrag-test на sys.path (rag_context, rag_llm) и доступ к LLM API.
    """
    rag = _can_access_rag(db, current_user, rag_id)
    if not rag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RAG not found")
    try:
        from rag_context import build_context_by_question
        from rag_llm import answer_from_context, get_llm_client
    except ImportError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"RAG chat unavailable (missing graphrag-test): {e}",
        )
    settings = get_settings()
    sparql_kw = {
        "url": settings.fuseki_url,
        "auth": (settings.fuseki_user, settings.fuseki_password),
        "ds": rag.fuseki_dataset,
    }
    context = build_context_by_question(body.question, **sparql_kw)
    context_used = len(context)
    client = get_llm_client(
        base_url=settings.llm_api_url,
        api_key="lm-studio",
        timeout=120,
    )
    try:
        answer = answer_from_context(
            context,
            body.question,
            client=client,
            model=settings.llm_model,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM returned empty or invalid response: {e}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM error: {e}",
        )
    return ChatResponse(answer=answer, context_used=context_used)


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
