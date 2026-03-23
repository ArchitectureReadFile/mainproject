from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from models.model import GroupStatus, MembershipRole


class GroupCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("이름은 공백만 입력할 수 없습니다.")
        return v


class GroupSummaryResponse(BaseModel):
    """워크스페이스 카드(목록용)"""

    id: int
    name: str
    status: GroupStatus
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
    description: Optional[str]
    status: GroupStatus
    my_role: MembershipRole
    owner_id: int
    owner_username: str
    member_count: int
    document_count: int
    delete_scheduled_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class MemberResponse(BaseModel):
    """ACTIVE 멤버용"""

    user_id: int
    email: str
    username: str
    role: MembershipRole
    joined_at: Optional[datetime] = None


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
