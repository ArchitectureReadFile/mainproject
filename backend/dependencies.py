from fastapi import Depends, Request, WebSocket
from fastapi.security import APIKeyCookie
from redis import Redis
from sqlalchemy.orm import Session

from database import db_session, get_db
from domains.auth.repository import AuthRepository
from domains.auth.service import AuthService
from domains.chat.repository import ChatRepository
from domains.chat.service import ChatService
from domains.email.repository import EmailRepository
from domains.email.service import EmailService
from domains.notification.repository import NotificationRepository
from domains.notification.service import NotificationService
from domains.oauth.repository import OAuthRepository
from domains.oauth.service import OAuthService
from domains.workspace.repository import GroupRepository
from domains.workspace.service import GroupService
from models.model import User
from redis_client import redis_client

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


def get_user_from_websocket(websocket: WebSocket) -> User:
    """WebSocket 연결에서 access_token 쿠키로 사용자를 식별한다.

    인증 실패 시 AppException을 발생시킨다.
    호출자가 WebSocket close 처리를 담당한다.
    """
    token = websocket.cookies.get("access_token")
    with db_session() as db:
        auth_repo = AuthRepository(db)
        auth_svc = AuthService(auth_repo)
        return auth_svc.get_user_from_token(token)
