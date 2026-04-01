from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, ValidationInfo, field_validator


def validate_password_bytes(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise ValueError("비밀번호는 UTF-8 기준 72바이트 이하여야 합니다.")
    return password


class SubscriptionResponse(BaseModel):
    plan: str
    status: str
    auto_renew: bool
    started_at: datetime
    ended_at: datetime | None = None


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
    created_at: datetime
    subscription: SubscriptionResponse | None = None


class ConfirmAccountRequest(BaseModel):
    email: EmailStr = Field(..., min_length=5, max_length=255)


class ResetPasswordRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    new_password: str = Field(..., min_length=8, max_length=72)

    @field_validator("new_password")
    @classmethod
    def password_byte_limit(cls, v: str) -> str:
        return validate_password_bytes(v)


class UpdateUsernameRequest(BaseModel):
    new_username: str = Field(..., min_length=2, max_length=10)


class UpdatePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=8, max_length=72)
    new_password: str = Field(..., min_length=8, max_length=72)
    confirm_new_password: str = Field(..., min_length=8, max_length=72)

    @field_validator("new_password")
    @classmethod
    def password_byte_limit(cls, v: str) -> str:
        return validate_password_bytes(v)

    @field_validator("confirm_new_password")
    @classmethod
    def passwords_match(cls, v: str, info: ValidationInfo) -> str:
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("새 비밀번호와 비밀번호 확인이 일치하지 않습니다.")
        return v


class UpdateEmailRequest(BaseModel):
    new_email: EmailStr = Field(..., min_length=5, max_length=255)


class SubscribePremiumRequest(BaseModel):
    confirm: bool = True


class CancelSubscriptionRequest(BaseModel):
    confirm: bool = True
