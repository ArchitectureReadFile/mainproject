from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from database import get_db
from models.model import User
from repositories.group_repository import GroupRepository
from routers.auth import get_current_user
from schemas.group import (
    GroupCreateRequest,
    GroupDetailResponse,
    InvitationResponse,
    InvitedMemberResponse,
    MemberInviteRequest,
    MemberListResponse,
    MemberRoleChangeRequest,
    MyGroupsResponse,
)
from services.group_service import GroupService

router = APIRouter(prefix="/groups", tags=["groups"])


def get_group_service(db: Session = Depends(get_db)) -> GroupService:
    return GroupService(GroupRepository(db), db)


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


@router.get("", response_model=MyGroupsResponse)
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


@router.get("/{group_id}", response_model=GroupDetailResponse)
def get_group_detail(
    group_id: int,
    current_user: User = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
):
    return service.get_group_detail(current_user.id, group_id)


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


@router.get("/{group_id}/members", response_model=MemberListResponse)
def get_members(
    group_id: int,
    current_user: User = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
):
    return service.get_members(current_user.id, group_id)


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


@router.post("/{group_id}/members/accept", status_code=status.HTTP_204_NO_CONTENT)
def accept_invite(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
):
    service.accept_invite(current_user.id, group_id)
    db.commit()


@router.post("/{group_id}/members/decline", status_code=status.HTTP_204_NO_CONTENT)
def decline_invite(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
):
    service.decline_invite(current_user.id, group_id)
    db.commit()


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
