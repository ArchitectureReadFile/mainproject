from fastapi import APIRouter, Depends, Response, status
from redis import Redis
from sqlalchemy.orm import Session

from dependencies import (
    get_auth_service,
    get_client_ip,
    get_current_user,
    get_db,
    get_redis,
    get_refresh_token_cookie,
)
from models.model import User
from schemas.auth import (
    ConfirmAccountRequest,
    LoginRequest,
    ResetPasswordRequest,
    SignupRequest,
    UpdateNotificationRequest,
    UpdateUsernameRequest,
    UserResponse,
)
from services.auth_service import AuthService
from services.cookie_service import CookieService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/signup", status_code=status.HTTP_201_CREATED, response_model=UserResponse
)
def signup(
    payload: SignupRequest,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    auth_service: AuthService = Depends(get_auth_service),
):
    return auth_service.signup(db, redis, payload)


@router.post("/login", response_model=UserResponse)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    client_ip: str = Depends(get_client_ip),
    auth_service: AuthService = Depends(get_auth_service),
):
    user_resp, access_token, refresh_token = auth_service.login(
        db, redis, payload, client_ip
    )
    CookieService.set_auth_cookies(response, access_token, refresh_token)
    return user_resp


@router.post("/refresh", response_model=UserResponse)
def refresh(
    response: Response,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    refresh_token: str | None = Depends(get_refresh_token_cookie),
    auth_service: AuthService = Depends(get_auth_service),
):
    user_resp, access_token, refresh_token = auth_service.refresh(
        db, redis, refresh_token
    )
    CookieService.set_auth_cookies(response, access_token, refresh_token)
    return user_resp


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    redis: Redis = Depends(get_redis),
    refresh_token: str | None = Depends(get_refresh_token_cookie),
    auth_service: AuthService = Depends(get_auth_service),
):
    auth_service.logout(redis, refresh_token)
    CookieService.delete_auth_cookies(response)


@router.get("/me", response_model=UserResponse)
def me(
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    return auth_service.to_user_response(current_user)


@router.post("/confirm-account", response_model=UserResponse)
def confirm_account(
    payload: ConfirmAccountRequest,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    auth_service: AuthService = Depends(get_auth_service),
):
    return auth_service.confirm_account(db, redis, payload)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    auth_service: AuthService = Depends(get_auth_service),
):
    auth_service.reset_password(db, redis, payload)


@router.patch("/username", response_model=UserResponse)
def update_username(
    payload: UpdateUsernameRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    return auth_service.update_username(db, current_user.id, payload.username)


@router.patch("/notification", response_model=UserResponse)
def update_notification_settings(
    payload: UpdateNotificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    return auth_service.update_notification_settings(
        db, current_user.id, payload.is_toast_notification_enabled
    )
