from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from database import get_db
from models.model import User
from repositories.document_repository import DocumentRepository
from repositories.group_repository import GroupRepository
from routers.auth import get_current_user
from schemas.document import DocumentDetailResponse, DocumentRejectRequest
from schemas.group import (
    GroupCreateRequest,
    GroupDetailResponse,
    GroupSummaryResponse,
    InvitationResponse,
    InvitedMemberResponse,
    MemberInviteRequest,
    MemberListResponse,
    MemberRoleChangeRequest,
)
from services.document_service import DocumentService
from services.group_service import GroupService

router = APIRouter(prefix="/groups", tags=["groups"])


def get_group_service(db: Session = Depends(get_db)) -> GroupService:
    return GroupService(GroupRepository(db))


def get_document_service(db: Session = Depends(get_db)) -> DocumentService:
    return DocumentService(DocumentRepository(db))


# 그룹 생성
@router.post(
    "", response_model=GroupDetailResponse, status_code=status.HTTP_201_CREATED
)
def create_group(
    payload: GroupCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
):
    result = service.create_group(current_user.id, payload.name, payload.description)
    db.commit()

    return result


# 내 그룹 목록 조회
@router.get("", response_model=list[GroupSummaryResponse])
def get_my_groups(
    current_user: User = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
):
    return service.get_my_groups(current_user.id)


@router.get("/invitations", response_model=list[InvitationResponse])
def get_my_invitations(
    current_user: User = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
):
    return service.get_my_invitations(current_user.id)


# 그룹 상세
@router.get("/{group_id}", response_model=GroupDetailResponse)
def get_group_detail(
    group_id: int,
    current_user: User = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
):
    return service.get_group_detail(current_user.id, group_id)


# 그룹 삭제 요청
@router.delete("/{group_id}", response_model=GroupDetailResponse)
def request_delete_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
):
    result = service.request_delete_group(current_user.id, group_id)
    db.commit()

    return result


# 그룹 삭제 취소
@router.post("/{group_id}/cancel-delete", response_model=GroupDetailResponse)
def cancel_delete_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
):
    result = service.cancel_delete_group(current_user.id, group_id)
    db.commit()

    return result


# 멤버 목록 조회 GET /api/groups/{group_id}/members
@router.get("/{group_id}/members", response_model=MemberListResponse)
def get_members(
    group_id: int,
    current_user: User = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
):
    return service.get_members(current_user.id, group_id)


# 초대 POST /api/groups/{group_id}/members
@router.post(
    "/{group_id}/members",
    response_model=InvitedMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def invite_member(
    group_id: int,
    payload: MemberInviteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
):
    result = service.invite_member(
        group_id, current_user.id, payload.username, payload.role
    )
    db.commit()
    return result


# 초대 수락
@router.post("/{group_id}/members/accept", status_code=status.HTTP_204_NO_CONTENT)
def accept_invite(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
):
    service.accept_invite(current_user.id, group_id)
    db.commit()


# 초대 거절
@router.post("/{group_id}/members/decline", status_code=status.HTTP_204_NO_CONTENT)
def decline_invite(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
):
    service.decline_invite(current_user.id, group_id)
    db.commit()


# 추방 DELETE /api/groups/{group_id}/members/{user_id}
@router.delete(
    "/{group_id}/members/{target_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_member(
    group_id: int,
    target_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
):
    service.remove_member(target_id, group_id, current_user.id)
    db.commit()


# 권한 변경 PATCH /api/groups/{group_id}/members/{user_id}
@router.patch("/{group_id}/members/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
def change_member_role(
    group_id: int,
    target_id: int,
    payload: MemberRoleChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
):
    service.change_member_role(current_user.id, target_id, group_id, payload.role)
    db.commit()


# 오너 양도
@router.post(
    "/{group_id}/members/{target_id}/transfer", status_code=status.HTTP_204_NO_CONTENT
)
def transfer_owner(
    group_id: int,
    target_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
):
    service.transfer_owner(current_user.id, group_id, target_id)
    db.commit()


@router.get("/{group_id}/documents")
def list_documents(
    group_id: int,
    skip: int = 0,
    limit: int = 5,
    keyword: str = "",
    status: str = "",
    view_type: str = "all",
    category: str = "전체",
    service: DocumentService = Depends(get_document_service),
    group_service: GroupService = Depends(get_group_service),
    current_user: User = Depends(get_current_user),
):
    group_service.assert_view_permission(current_user.id, group_id)

    items, total = service.get_list(
        skip,
        limit,
        keyword,
        status,
        user_id=current_user.id,
        view_type=view_type,
        category=category,
        group_id=group_id,
    )
    return {"items": items, "total": total}


# 그룹 내 승인 대기 문서 전체 조회
@router.get("/{group_id}/documents/pending")
def list_pending_documents(
    group_id: int,
    skip: int = 0,
    limit: int = 5,
    keyword: str = "",
    service: DocumentService = Depends(get_document_service),
    group_service: GroupService = Depends(get_group_service),
    current_user: User = Depends(get_current_user),
):
    group_service.assert_review_permission(current_user.id, group_id)
    items, total = service.get_pending_list(
        skip,
        limit,
        keyword,
        group_id,
    )

    return {"items": items, "total": total}


@router.get("/{group_id}/documents/deleted")
def list_deleted_documents(
    group_id: int,
    skip: int = 0,
    limit: int = 5,
    service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user),
    group_service: GroupService = Depends(get_group_service),
):
    group_service.assert_view_permission(current_user.id, group_id)

    items, total = service.get_deleted_list(
        skip,
        limit,
        user_id=current_user.id,
        group_id=group_id,
    )

    return {"items": items, "total": total}


@router.get("/{group_id}/documents/{doc_id}", response_model=DocumentDetailResponse)
def get_detail_document(
    group_id: int,
    doc_id: int,
    group_service: GroupService = Depends(get_group_service),
    document_service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user),
):
    _, role = group_service.assert_view_permission(current_user.id, group_id)

    return document_service.get_detail_in_group(
        doc_id=doc_id,
        group_id=group_id,
        current_user_id=current_user.id,
        current_user_role=role,
    )


@router.delete("/{group_id}/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    group_id: int,
    doc_id: int,
    service: DocumentService = Depends(get_document_service),
    group_service: GroupService = Depends(get_group_service),
    current_user: User = Depends(get_current_user),
):
    group_service.assert_view_permission(current_user.id, group_id)
    service.delete_document(doc_id, current_user.id, group_id)


@router.post("/{group_id}/documents/{doc_id}/approve")
def approve_document(
    group_id: int,
    doc_id: int,
    service: DocumentService = Depends(get_document_service),
    group_service: GroupService = Depends(get_group_service),
    current_user: User = Depends(get_current_user),
):
    group_service.assert_review_permission(current_user.id, group_id)
    return service.approve_document(doc_id, current_user.id, group_id)


@router.post("/{group_id}/documents/{doc_id}/reject")
def reject_document(
    group_id: int,
    doc_id: int,
    payload: DocumentRejectRequest,
    service: DocumentService = Depends(get_document_service),
    group_service: GroupService = Depends(get_group_service),
    current_user: User = Depends(get_current_user),
):
    group_service.assert_review_permission(current_user.id, group_id)
    return service.reject_document(doc_id, current_user.id, group_id, payload.feedback)
