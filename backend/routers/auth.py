import os

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from database import get_db
from errors import AppException, ErrorCode
from models.model import User
from redis_client import redis_client
from schemas.auth import (
    ConfirmAccountRequest,
    LoginRequest,
    ResetPasswordRequest,
    SignupRequest,
    UpdateUsernameRequest,
    UserResponse,
)
from services.auth_service import (
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token,
    create_refresh_token,
    create_user,
    decode_access_token,
    decode_refresh_token,
    get_user_by_email,
    get_user_by_username,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])
LOGIN_RATE_LIMIT_MAX_ATTEMPTS = int(os.getenv("LOGIN_RATE_LIMIT_MAX_ATTEMPTS", "5"))
LOGIN_RATE_LIMIT_WINDOW_SECONDS = int(
    os.getenv("LOGIN_RATE_LIMIT_WINDOW_SECONDS", "300")
)
LOGIN_RATE_LIMIT_BLOCK_SECONDS = int(os.getenv("LOGIN_RATE_LIMIT_BLOCK_SECONDS", "300"))


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise AppException(ErrorCode.AUTH_TOKEN_MISSING)
    email = decode_access_token(token)
    user = get_user_by_email(db, email)
    if not user or not user.is_active:
        raise AppException(ErrorCode.AUTH_USER_INVALID)
    return user


def to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at,
    )


def _client_key(request: Request, email: str) -> str:
    ip = request.client.host if request.client else "unknown"
    return f"{ip}:{email.strip().lower()}"


def _check_login_rate_limit(key: str):
    if redis_client.get(f"block:{key}"):
        raise AppException(ErrorCode.USER_RATE_LIMIT_EXCEEDED)


def _record_login_failure(key: str):
    attempt_key = f"attempts:{key}"
    block_key = f"block:{key}"

    attempts = redis_client.incr(attempt_key)
    if attempts == 1:
        redis_client.expire(attempt_key, LOGIN_RATE_LIMIT_WINDOW_SECONDS)

    if attempts >= LOGIN_RATE_LIMIT_MAX_ATTEMPTS:
        redis_client.setex(block_key, LOGIN_RATE_LIMIT_BLOCK_SECONDS, "1")
        redis_client.delete(attempt_key)


def _clear_login_failures(key: str):
    redis_client.delete(f"attempts:{key}", f"block:{key}")


def _set_refresh_cookie(response: Response, refresh_token: str):
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=JWT_REFRESH_TOKEN_EXPIRE_DAYS * 60 * 60 * 24,
    )


def _set_access_cookie(response: Response, access_token: str):
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=False,
        secure=False,
        samesite="lax",
        max_age=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    if not redis_client.get(f"email_verified:{email}"):
        raise AppException(ErrorCode.USER_EMAIL_NOT_VERIFIED)

    create_user(db, payload)
    redis_client.delete(f"email_verified:{email}")


@router.post("/login", response_model=UserResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    email = payload.email.strip().lower()
    key = _client_key(request, email)
    _check_login_rate_limit(key)
    user = get_user_by_email(db, email)

    if not user or not verify_password(payload.password, user.password):
        _record_login_failure(key)
        raise AppException(ErrorCode.USER_INVALID_CREDENTIALS)

    if not user.is_active:
        _record_login_failure(key)
        raise AppException(ErrorCode.USER_INACTIVE)

    _clear_login_failures(key)

    access_token = create_access_token(user.email)
    refresh_token = create_refresh_token(user.email)

    ttl_seconds = JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    redis_client.setex(f"refresh_token:{refresh_token}", ttl_seconds, user.email)

    _set_access_cookie(response, access_token)
    _set_refresh_cookie(response, refresh_token)

    return to_user_response(user)


@router.post("/refresh", response_model=UserResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise AppException(ErrorCode.AUTH_REFRESH_TOKEN_MISSING)

    stored_email = redis_client.get(f"refresh_token:{refresh_token}")
    if not stored_email:
        raise AppException(ErrorCode.AUTH_REFRESH_TOKEN_EXPIRED)

    redis_client.delete(f"refresh_token:{refresh_token}")

    email = decode_refresh_token(refresh_token)
    user = get_user_by_email(db, email)

    if not user or not user.is_active or user.email != stored_email:
        raise AppException(ErrorCode.AUTH_USER_INVALID)

    new_access_token = create_access_token(user.email)
    new_refresh_token = create_refresh_token(user.email)

    ttl_seconds = JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    redis_client.setex(f"refresh_token:{new_refresh_token}", ttl_seconds, user.email)

    _set_access_cookie(response, new_access_token)
    _set_refresh_cookie(response, new_refresh_token)

    return to_user_response(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response):
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        redis_client.delete(f"refresh_token:{refresh_token}")

    response.delete_cookie(key="refresh_token", httponly=True, samesite="lax")
    response.delete_cookie(key="access_token", samesite="lax")


@router.get("/me", response_model=UserResponse)
def me(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        raise AppException(ErrorCode.AUTH_TOKEN_MISSING)
    email = decode_access_token(token)
    user = get_user_by_email(db, email)
    if not user:
        raise AppException(ErrorCode.USER_NOT_FOUND)
    return to_user_response(user)


@router.post("/confirm-account")
def confirm_account(payload: ConfirmAccountRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()

    if not redis_client.get(f"email_verified:{email}"):
        raise AppException(ErrorCode.USER_EMAIL_NOT_VERIFIED)

    user = get_user_by_email(db, email)
    if not user:
        raise AppException(ErrorCode.USER_ACCOUNT_NOT_FOUND)

    return {
        "email": user.email,
        "username": user.username,
        "message": "가입된 계정 정보가 확인되었습니다.",
    }


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()

    if not redis_client.get(f"email_verified:{email}"):
        raise AppException(ErrorCode.USER_EMAIL_NOT_VERIFIED)

    user = get_user_by_email(db, email)
    if not user:
        raise AppException(ErrorCode.USER_NOT_FOUND)

    user.password = hash_password(payload.new_password)
    db.commit()

    redis_client.delete(f"email_verified:{email}")

    return {"message": "비밀번호가 성공적으로 변경되었습니다."}


@router.patch("/username")
def update_username(
    data: UpdateUsernameRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = get_user_by_username(db, data.username)
    if existing and existing.id != current_user.id:
        raise AppException(ErrorCode.USER_USERNAME_ALREADY_EXISTS)

    current_user.username = data.username
    db.commit()
    db.refresh(current_user)

    return {"username": current_user.username}
