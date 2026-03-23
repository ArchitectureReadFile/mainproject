from fastapi import APIRouter, Depends, Form, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import SessionLocal, get_db
from models.model import User, ChatSession, ChatMessage, ChatMessageRole
from tasks.chat_task import process_chat_message
from services.summary.process_service import ProcessService
from routers.auth import get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])

class RoomCreate(BaseModel):
    title: str

@router.get("/rooms")
def get_rooms(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    rooms = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )
    return rooms


@router.post("/rooms")
def create_room(
    room_data: RoomCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    new_room = ChatSession(user_id=current_user.id, title=room_data.title)
    db.add(new_room)
    db.commit()
    db.refresh(new_room)
    return new_room


@router.put("/rooms/{session_id}")
def update_room(
    session_id: int,
    room_data: RoomCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    room = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not room:
        raise HTTPException(status_code=404, detail="Room not found or unauthorized")
    room.title = room_data.title
    db.commit()
    db.refresh(room)
    return room


@router.delete("/rooms/{session_id}")
def delete_room(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    room = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not room:
        raise HTTPException(status_code=404, detail="Room not found or unauthorized")
    db.delete(room)
    db.commit()
    return {"status": "success"}


@router.get("/rooms/{session_id}/messages")
def get_messages(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    room = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not room:
        raise HTTPException(status_code=404, detail="Room not found or unauthorized")

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return messages


@router.post("/rooms/{session_id}/messages")
def send_message(
    session_id: int,
    text: str = Form(""),
    document_id: int = Form(None),
    file: UploadFile = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):


    room = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not room:
        raise HTTPException(status_code=404, detail="Room not found or unauthorized")

    user_msg = ChatMessage(
        session_id=session_id, role=ChatMessageRole.USER, content=text
    )
    db.add(user_msg)
    db.commit()

    temp_doc_text = None
    if file:
        file_bytes = file.file.read()
        try:
            process_service = ProcessService()
            pages = process_service.extract_pages_from_bytes(file_bytes)
            if process_service.is_text_too_short("\n".join(pages)):
                pages = process_service.extract_pages_from_bytes_ocr(file_bytes)
            temp_doc_text = "\n".join(pages).strip()
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"파일 파싱 중 오류 발생: {str(e)}"
            )

    payload = {
        "user_id": current_user.id,
        "session_id": session_id,
        "message": text,
        "context_options": {"doc_id": document_id, "temp_doc_text": temp_doc_text},
    }

    process_chat_message.delay(payload)
    return {"status": "success", "message": "Task queued"}
