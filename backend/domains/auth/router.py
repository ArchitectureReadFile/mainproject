from fastapi import APIRouter, Depends, Response, status
from redis import Redis

from dependencies import (
    get_auth_service,
    get_client_ip,
    get_current_user,
    get_redis,
    get_refresh_token_cookie,
)
from domains.auth.cookie_service import CookieService
from domains.auth.schemas import (
    CancelSubscriptionRequest,
    ConfirmAccountRequest,
    LoginRequest,
    ResetPasswordRequest,
    SignupRequest,
    SubscribePremiumRequest,
    UpdatePasswordRequest,
    UpdateUsernameRequest,
    UserResponse,
)
from domains.auth.service import AuthService
from models.model import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/signup", status_code=status.HTTP_201_CREATED, response_model=UserResponse
)
def signup(
    payload: SignupRequest,
    redis: Redis = Depends(get_redis),
    auth_service: AuthService = Depends(get_auth_service),
):
    return auth_service.signup(redis, payload)


@router.post("/login", response_model=UserResponse)
def login(
    payload: LoginRequest,
    response: Response,
    redis: Redis = Depends(get_redis),
    client_ip: str = Depends(get_client_ip),
    auth_service: AuthService = Depends(get_auth_service),
):
    user_resp, access_token, refresh_token = auth_service.login(
        redis, payload, client_ip
    )
    CookieService.set_auth_cookies(response, access_token, refresh_token)
    return user_resp


@router.post("/refresh", response_model=UserResponse)
def refresh(
    response: Response,
    redis: Redis = Depends(get_redis),
    refresh_token: str | None = Depends(get_refresh_token_cookie),
    auth_service: AuthService = Depends(get_auth_service),
):
    user_resp, access_token, refresh_token = auth_service.refresh(redis, refresh_token)
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
    redis: Redis = Depends(get_redis),
    auth_service: AuthService = Depends(get_auth_service),
):
    return auth_service.confirm_account(redis, payload)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    payload: ResetPasswordRequest,
    redis: Redis = Depends(get_redis),
    auth_service: AuthService = Depends(get_auth_service),
):
    auth_service.reset_password(redis, payload)


@router.delete("/deactivate", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_account(
    response: Response,
    redis: Redis = Depends(get_redis),
    refresh_token: str | None = Depends(get_refresh_token_cookie),
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    auth_service.deactivate_account(redis, current_user.id)
    auth_service.logout(redis, refresh_token)
    CookieService.delete_auth_cookies(response)


@router.post("/reactivate", response_model=UserResponse)
def reactivate_account_route(
    payload: LoginRequest,
    response: Response,
    redis: Redis = Depends(get_redis),
    client_ip: str = Depends(get_client_ip),
    auth_service: AuthService = Depends(get_auth_service),
):
    user_resp, access_token, refresh_token = auth_service.reactivate_account(
        redis, payload, client_ip
    )
    CookieService.set_auth_cookies(response, access_token, refresh_token)
    return user_resp


@router.patch("/username", response_model=UserResponse)
def update_username(
    payload: UpdateUsernameRequest,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    return auth_service.update_username(current_user.id, payload.new_username)


@router.patch("/password", status_code=status.HTTP_204_NO_CONTENT)
def update_password(
    payload: UpdatePasswordRequest,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    auth_service.update_password(current_user.id, payload)


@router.post("/subscription/subscribe", response_model=UserResponse)
def subscribe_premium(
    payload: SubscribePremiumRequest,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    return auth_service.subscribe_premium(current_user.id, payload)


@router.post("/subscription/cancel", response_model=UserResponse)
def cancel_subscription(
    payload: CancelSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    return auth_service.cancel_subscription(current_user.id, payload)
