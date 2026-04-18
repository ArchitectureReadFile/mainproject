from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from dependencies import get_chat_service, get_current_user
from domains.chat.schemas import (
    ChatMessagesResponse,
    ChatSessionReferenceResponse,
    ChatSessionRequest,
    ChatSessionResponse,
)
from domains.chat.service import ChatService
from domains.chat.workspace_selection_parser import parse_workspace_selection
from models.model import User

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/sessions", response_model=List[ChatSessionResponse])
def get_sessions(
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    return chat_service.get_sessions(current_user.id)


@router.post("/sessions", response_model=ChatSessionResponse)
def create_session(
    session_data: ChatSessionRequest,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    return chat_service.create_session(current_user.id, session_data.title)


@router.put("/sessions/{session_id}", response_model=ChatSessionResponse)
def update_session(
    session_id: int,
    session_data: ChatSessionRequest,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    return chat_service.update_session(current_user.id, session_id, session_data.title)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    chat_service.delete_session(current_user.id, session_id)


@router.get("/sessions/{session_id}/messages", response_model=ChatMessagesResponse)
def get_messages(
    session_id: int,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    return chat_service.get_messages(current_user.id, session_id)


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: int,
    text: str = Form(""),
    workspace_selection_json: str | None = Form(None),
    group_id: int | None = Form(None),
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    try:
        workspace_selection = parse_workspace_selection(workspace_selection_json)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if workspace_selection is not None and group_id is None:
        raise HTTPException(
            status_code=422,
            detail="workspace_selection 사용 시 group_id가 필요합니다.",
        )

    return chat_service.send_message(
        user_id=current_user.id,
        session_id=session_id,
        text=text,
        group_id=group_id,
        workspace_selection=workspace_selection,
    )


@router.post(
    "/sessions/{session_id}/reference-upload",
    response_model=ChatSessionReferenceResponse,
)
async def upload_reference_document(
    session_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    file_bytes = await file.read()
    return chat_service.enqueue_reference_document(
        user_id=current_user.id,
        session_id=session_id,
        file_name=file.filename or "reference.pdf",
        file_bytes=file_bytes,
    )


@router.get(
    "/sessions/{session_id}/reference",
    response_model=ChatSessionReferenceResponse | None,
)
def get_reference_document(
    session_id: int,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    return chat_service.get_reference_document(
        user_id=current_user.id,
        session_id=session_id,
    )


@router.post("/sessions/{session_id}/stop")
def stop_message(
    session_id: int,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    return chat_service.stop_message(current_user.id, session_id)


@router.delete("/sessions/{session_id}/reference", response_model=ChatSessionResponse)
def delete_reference_document(
    session_id: int,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    return chat_service.delete_reference_document(
        user_id=current_user.id,
        session_id=session_id,
    )


@router.delete(
    "/sessions/{session_id}/reference-group", response_model=ChatSessionResponse
)
def delete_reference_group(
    session_id: int,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    return chat_service.delete_reference_group(
        user_id=current_user.id,
        session_id=session_id,
    )
