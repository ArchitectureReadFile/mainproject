from fastapi import APIRouter, Depends, Form, UploadFile, File, status
from typing import List
from sqlalchemy.orm import Session

from dependencies import get_chat_service, get_current_user, get_db, get_redis
from services.chat_service import ChatService
from models.model import User
from schemas.chat import ChatSessionRequest, ChatSessionResponse, ChatMessageResponse

router = APIRouter(prefix="/chat", tags=["chat"])

@router.get("/sessions", response_model=List[ChatSessionResponse])
def get_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    return chat_service.get_sessions(db, current_user.id)

@router.post("/sessions", response_model=ChatSessionResponse)
def create_session(
    session_data: ChatSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    return chat_service.create_session(db, current_user.id, session_data.title)

@router.put("/sessions/{session_id}", response_model=ChatSessionResponse)
def update_session(
    session_id: int,
    session_data: ChatSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    return chat_service.update_session(db, current_user.id, session_id, session_data.title)

@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    chat_service.delete_session(db, current_user.id, session_id)

@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse])
def get_messages(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    return chat_service.get_messages(db, current_user.id, session_id)

@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: int,
    text: str = Form(""),
    document_id: int = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    file_bytes = None
    if file:
        file_bytes = await file.read()

    return chat_service.send_message(
        db=db,
        user_id=current_user.id,
        session_id=session_id,
        text=text,
        document_id=document_id,
        file_bytes=file_bytes,
    )
