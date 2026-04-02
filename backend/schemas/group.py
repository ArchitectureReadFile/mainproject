from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from models.model import GroupPendingReason, GroupStatus, MembershipRole


class GroupCreateRequest(BaseModel):
    """워크스페이스 생성 요청"""

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v):
        """이름 양끝 공백을 제거하고 빈 문자열을 막는다."""
        v = v.strip()
        if not v:
            raise ValueError("이름은 공백만 입력할 수 없습니다.")
        return v


class GroupSummaryResponse(BaseModel):
    """워크스페이스 카드(목록용)"""

    id: int
    name: str
    description: Optional[str] = None
    status: GroupStatus
    pending_reason: Optional[GroupPendingReason] = None
    my_role: MembershipRole
    owner_username: str
    member_count: int
    document_count: int
    delete_scheduled_at: Optional[datetime] = None
    created_at: datetime


class GroupDetailResponse(BaseModel):
    """워크스페이스 상세"""

    id: int
    name: str
    description: Optional[str] = None
    status: GroupStatus
    pending_reason: Optional[GroupPendingReason] = None
    my_role: MembershipRole
    owner_id: int
    owner_username: str
    member_count: int
    document_count: int
    delete_scheduled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class MyGroupsResponse(BaseModel):
    """내가 속한 워크스페이스 목록과 차단된 오너 그룹 존재 여부를 반환한다."""

    groups: list[GroupSummaryResponse]
    has_blocked_owned_group: bool = False


class MemberResponse(BaseModel):
    """ACTIVE 멤버용"""

    user_id: int
    email: str
    username: str
    role: MembershipRole
    joined_at: Optional[datetime] = None
    is_premium: bool
    has_owned_group: bool


class InvitedMemberResponse(BaseModel):
    """INVITED 멤버용"""

    user_id: int
    username: str
    role: MembershipRole
    invited_at: Optional[datetime] = None


class MemberListResponse(BaseModel):
    """멤버 목록 전체 응답"""

    members: list[MemberResponse]
    invited: list[InvitedMemberResponse]


class MemberInviteRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=20)
    role: MembershipRole = MembershipRole.VIEWER


class MemberRoleChangeRequest(BaseModel):
    role: MembershipRole


class OwnerTransferRequest(BaseModel):
    user_id: int


class InvitationResponse(BaseModel):
    """내가 초대받은 그룹 목록"""

    group_id: int
    group_name: str
    owner_username: str
    role: MembershipRole
    invited_at: Optional[datetime] = None
