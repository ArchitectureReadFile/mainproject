from fastapi import Depends, Request
from fastapi.security import APIKeyCookie
from redis import Redis
from sqlalchemy.orm import Session

from database import get_db
from models.model import User
from redis_client import redis_client
from repositories.auth_repository import AuthRepository
from repositories.chat_repository import ChatRepository
from repositories.email_repository import EmailRepository
from repositories.group_repository import GroupRepository
from repositories.notification_repository import NotificationRepository
from repositories.oauth_repository import OAuthRepository
from services.auth_service import AuthService
from services.chat.chat_service import ChatService
from services.email_service import EmailService
from services.group_service import GroupService
from services.notification_service import NotificationService
from services.oauth_service import OAuthService

cookie_scheme = APIKeyCookie(name="access_token", auto_error=False)


# 주입
def get_auth_repository(db: Session = Depends(get_db)):
    return AuthRepository(db)


def get_chat_repository(db: Session = Depends(get_db)):
    return ChatRepository(db)


def get_email_repository(db: Session = Depends(get_db)):
    return EmailRepository(db)


def get_group_repository(db: Session = Depends(get_db)):
    return GroupRepository(db)


def get_oauth_repository(db: Session = Depends(get_db)):
    return OAuthRepository(db)


def get_notification_repository(db: Session = Depends(get_db)):
    return NotificationRepository(db)


def get_auth_service(auth_repo: AuthRepository = Depends(get_auth_repository)):
    return AuthService(auth_repo)


def get_oauth_service(
    oauth_repo: OAuthRepository = Depends(get_oauth_repository),
    auth_service: AuthService = Depends(get_auth_service),
):
    return OAuthService(oauth_repo, auth_service)


def get_notification_service(
    notification_repo: NotificationRepository = Depends(get_notification_repository),
):
    return NotificationService(notification_repo)


def get_group_service(
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
    notification_service: NotificationService = Depends(get_notification_service),
):
    return GroupService(GroupRepository(db), auth_service, notification_service, db)


def get_chat_service(
    chat_repo: ChatRepository = Depends(get_chat_repository),
    auth_service: AuthService = Depends(get_auth_service),
    notification_service: NotificationService = Depends(get_notification_service),
    db: Session = Depends(get_db),
):
    group_service = GroupService(
        GroupRepository(db), auth_service, notification_service, db
    )
    return ChatService(chat_repo, auth_service, group_service)


def get_email_service(email_repo: EmailRepository = Depends(get_email_repository)):
    return EmailService(email_repo)


def get_oauth_service_dep(
    oauth_repo: OAuthRepository = Depends(get_oauth_repository),
    auth_service: AuthService = Depends(get_auth_service),
):
    return OAuthService(oauth_repo, auth_service)


def get_redis() -> Redis:
    return redis_client


def get_current_user_optional(
    token: str | None = Depends(cookie_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> User | None:
    if not token:
        return None
    try:
        email = auth_service.decode_access_token(token)
        user = auth_service.auth_repo.get_user_by_email(email)
        if not user or not user.is_active:
            return None
        return user
    except Exception:
        return None


# HTTP 데이터 추출
def get_client_ip(request: Request) -> str:
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.split(",")[0].strip()

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    return request.client.host if request.client else "unknown"


def get_refresh_token_cookie(request: Request) -> str | None:
    return request.cookies.get("refresh_token")


# 공통 인증
def get_current_user(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    token = request.cookies.get("access_token")
    return auth_service.get_user_from_token(token)
