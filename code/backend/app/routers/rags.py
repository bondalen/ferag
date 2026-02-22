"""CRUD RAG-экземпляров: создание, список, по id, удаление, загрузка файла, approve цикла."""
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Body, Depends, File, HTTPException, status, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.celery_sender import send_update_chain
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
from app.models import ChatMessage, ChatSession, RagInstance, RagMember, Task, UploadCycle, User

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


class MemberAddBody(BaseModel):
    email: str
    role: Literal["viewer", "editor"]


class MemberResponse(BaseModel):
    user_id: int
    email: str
    role: str


class MemberListItem(BaseModel):
    user_id: int
    email: str
    display_name: str | None
    role: str


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


def _get_default_session(db: Session, rag_id: int, user_id: int) -> ChatSession:
    """Последняя по created_at сессия пользователя по RAG или новая с title=None."""
    session = (
        db.query(ChatSession)
        .filter(ChatSession.rag_id == rag_id, ChatSession.user_id == user_id)
        .order_by(ChatSession.created_at.desc())
        .first()
    )
    if session:
        return session
    session = ChatSession(rag_id=rag_id, user_id=user_id, title=None)
    db.add(session)
    db.flush()
    return session


def _get_session_for_user(db: Session, session_id: int, rag_id: int, user_id: int) -> ChatSession | None:
    """Сессия с проверкой: rag_id и user_id совпадают."""
    s = db.get(ChatSession, session_id)
    if not s or s.rag_id != rag_id or s.user_id != user_id:
        return None
    return s


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
    try:
        create_dataset(rag.fuseki_dataset)
    except Exception:
        # Fuseki может быть временно недоступен (например, порт ещё не поднят).
        # RAG-запись уже сохранена в БД; worker создаст датасет при необходимости.
        pass
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


class CycleInReview(BaseModel):
    cycle_id: int
    task_id: int


class UploadStatusResponse(BaseModel):
    """Есть ли цикл в статусе review (ожидает подтверждения). После перезагрузки/повторного входа фронт восстанавливает кнопку «Подтвердить»."""
    cycle_in_review: CycleInReview | None = None


@router.get("/{rag_id}/upload-status", response_model=UploadStatusResponse)
def get_upload_status(
    rag_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Последний цикл в статусе review и его task_id (для восстановления UI после перезагрузки)."""
    rag = _can_access_rag(db, current_user, rag_id)
    if not rag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RAG not found")
    cycle = (
        db.query(UploadCycle)
        .filter(UploadCycle.rag_id == rag_id, UploadCycle.status == "review")
        .order_by(UploadCycle.id.desc())
        .first()
    )
    if not cycle:
        return UploadStatusResponse(cycle_in_review=None)
    task = db.query(Task).filter(Task.rag_id == rag_id, Task.cycle_id == cycle.id).first()
    if not task:
        return UploadStatusResponse(cycle_in_review=None)
    return UploadStatusResponse(
        cycle_in_review=CycleInReview(cycle_id=cycle.id, task_id=task.id)
    )


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
    cycle.source_content = content.decode("utf-8")
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
        send_update_chain(rag_id, cycle.id, task.id, str(file_path))
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
    session_id: int | None = None


class ChatSessionCreate(BaseModel):
    title: str | None = None


class ChatSessionListItem(BaseModel):
    id: int
    title: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionDetail(BaseModel):
    id: int
    rag_id: int
    user_id: int
    title: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionUpdate(BaseModel):
    title: str | None = None


class ChatResponse(BaseModel):
    answer: str
    context_used: int


class ChatMessageListItem(BaseModel):
    id: int
    role: str
    content: str
    context_used: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


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
    if body.session_id is not None:
        session = _get_session_for_user(db, body.session_id, rag_id, current_user.id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    else:
        session = _get_default_session(db, rag_id, current_user.id)
    db.add(
        ChatMessage(
            session_id=session.id,
            rag_id=rag_id,
            user_id=current_user.id,
            role="user",
            content=body.question,
            context_used=None,
        )
    )
    db.add(
        ChatMessage(
            session_id=session.id,
            rag_id=rag_id,
            user_id=current_user.id,
            role="assistant",
            content=answer,
            context_used=context_used,
        )
    )
    db.commit()
    return ChatResponse(answer=answer, context_used=context_used)


@router.get("/{rag_id}/chat/messages", response_model=list[ChatMessageListItem])
def get_chat_messages(
    rag_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    session_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """
    Сообщения диалога: при session_id — этой сессии (своей); иначе — последняя/дефолтная сессия пользователя по RAG.
    """
    rag = _can_access_rag(db, current_user, rag_id)
    if not rag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RAG not found")
    if session_id is not None:
        session = _get_session_for_user(db, session_id, rag_id, current_user.id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    else:
        session = _get_default_session(db, rag_id, current_user.id)
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return rows


@router.post("/{rag_id}/chat/sessions", response_model=ChatSessionDetail, status_code=status.HTTP_201_CREATED)
def create_chat_session(
    rag_id: int,
    body: ChatSessionCreate | None = Body(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Создать сессию диалога. user_id = current_user.id."""
    rag = _can_access_rag(db, current_user, rag_id)
    if not rag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RAG not found")
    title = body.title if body else None
    session = ChatSession(rag_id=rag_id, user_id=current_user.id, title=title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/{rag_id}/chat/sessions", response_model=list[ChatSessionListItem])
def list_chat_sessions(
    rag_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список сессий текущего пользователя по RAG (по created_at DESC)."""
    rag = _can_access_rag(db, current_user, rag_id)
    if not rag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RAG not found")
    rows = (
        db.query(ChatSession)
        .filter(ChatSession.rag_id == rag_id, ChatSession.user_id == current_user.id)
        .order_by(ChatSession.created_at.desc())
        .all()
    )
    return rows


@router.get("/{rag_id}/chat/sessions/{session_id}/messages", response_model=list[ChatMessageListItem])
def get_session_messages(
    rag_id: int,
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
):
    """Сообщения сессии. Проверка: сессия своя и rag_id совпадает."""
    rag = _can_access_rag(db, current_user, rag_id)
    if not rag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RAG not found")
    session = _get_session_for_user(db, session_id, rag_id, current_user.id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return rows


@router.patch("/{rag_id}/chat/sessions/{session_id}", response_model=ChatSessionListItem)
def update_chat_session(
    rag_id: int,
    session_id: int,
    body: ChatSessionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Обновить title сессии. Только своя сессия."""
    rag = _can_access_rag(db, current_user, rag_id)
    if not rag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RAG not found")
    session = _get_session_for_user(db, session_id, rag_id, current_user.id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if body.title is not None:
        session.title = body.title
    db.commit()
    db.refresh(session)
    return session


@router.delete("/{rag_id}/chat/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat_session(
    rag_id: int,
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Удалить сессию и её сообщения (CASCADE). Только своя сессия."""
    rag = _can_access_rag(db, current_user, rag_id)
    if not rag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RAG not found")
    session = _get_session_for_user(db, session_id, rag_id, current_user.id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    db.delete(session)
    db.commit()


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


@router.get("/{rag_id}/members", response_model=list[MemberListItem])
def list_members(
    rag_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список участников RAG (владелец + участники). Доступен владельцу и любому участнику."""
    rag = _can_access_rag(db, current_user, rag_id)
    if not rag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RAG not found")
    owner = db.get(User, rag.owner_id)
    result: list[MemberListItem] = []
    if owner:
        result.append(
            MemberListItem(
                user_id=owner.id,
                email=owner.email,
                display_name=owner.display_name,
                role="owner",
            )
        )
    for m in db.query(RagMember).filter(RagMember.rag_id == rag_id).all():
        u = db.get(User, m.user_id)
        if u:
            result.append(
                MemberListItem(
                    user_id=u.id,
                    email=u.email,
                    display_name=u.display_name,
                    role=m.role,
                )
            )
    return result


@router.post("/{rag_id}/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
def add_member(
    rag_id: int,
    body: MemberAddBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Добавить участника по email. Только владелец RAG."""
    rag = _can_access_rag(db, current_user, rag_id)
    if not rag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RAG not found")
    if not _is_owner(current_user, rag):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner can add members")
    target = db.query(User).filter(User.email == body.email).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if target.id == rag.owner_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already the owner",
        )
    if db.get(RagMember, (rag_id, target.id)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member",
        )
    member = RagMember(rag_id=rag_id, user_id=target.id, role=body.role)
    db.add(member)
    db.commit()
    return MemberResponse(user_id=target.id, email=target.email, role=body.role)


@router.delete("/{rag_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    rag_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Удалить участника из RAG. Только владелец; нельзя удалить самого себя (владельца)."""
    rag = _can_access_rag(db, current_user, rag_id)
    if not rag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RAG not found")
    if not _is_owner(current_user, rag):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner can remove members")
    if user_id == rag.owner_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the owner",
        )
    member = db.get(RagMember, (rag_id, user_id))
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    db.delete(member)
    db.commit()
    return None


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
