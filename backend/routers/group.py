from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from database import get_db
from models.model import User
from repositories.group_repository import GroupRepository
from routers.auth import get_current_user
from schemas.group import GroupCreateRequest, GroupDetailResponse, GroupSummaryResponse
from services.group_service import GroupService


router = APIRouter(prefix="/groups", tags=["groups"])


def get_group_service(db:Session = Depends(get_db)) -> GroupService:
    return GroupService(GroupRepository(db))


# 그룹 생성
@router.post("", response_model=GroupDetailResponse, status_code=status.HTTP_201_CREATED)
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


# 그룹 상세
@router.get("/{group_id}", response_model=GroupDetailResponse)
def get_group_detail(
    group_id: int,
    current_user: User = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
):
    return service.get_group_detail(current_user.id, group_id)



