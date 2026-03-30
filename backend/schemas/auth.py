from datetime import datetime
from typing import Optional

from fastapi import UploadFile
from pydantic import BaseModel, EmailStr, Field, field_validator


def validate_password_bytes(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise ValueError("비밀번호는 UTF-8 기준 72바이트 이하여야 합니다.")
    return password


class SignupRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    username: str = Field(..., min_length=2, max_length=20)
    password: str = Field(..., min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def password_byte_limit(cls, v: str) -> str:
        return validate_password_bytes(v)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=72)


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    role: str
    is_active: bool
    is_toast_notification_enabled: bool
    created_at: datetime


class ConfirmAccountRequest(BaseModel):
    email: EmailStr = Field(..., min_length=5, max_length=255)


class ResetPasswordRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    new_password: str = Field(..., min_length=8, max_length=72)

    @field_validator("new_password")
    @classmethod
    def password_byte_limit(cls, v: str) -> str:
        return validate_password_bytes(v)


class UpdateAccountRequest(BaseModel):
    username: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None
    avatar_file: Optional[UploadFile] = None


class UpdateUsernameRequest(BaseModel):
    username: str = Field(
        ..., min_length=2, max_length=10
    )  # 빈 문자열 들어오는 것 방지

class UpdateNotificationRequest(BaseModel):
    is_toast_notification_enabled: bool
