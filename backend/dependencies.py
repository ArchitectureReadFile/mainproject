from fastapi import Depends, Request
from fastapi.security import APIKeyCookie
from redis import Redis
from sqlalchemy.orm import Session

from database import get_db
from models.model import User
from redis_client import redis_client
from repositories.notification_repository import NotificationRepository
from services.auth_service import AuthService
from services.chat.chat_service import ChatService
from services.email_service import EmailService
from services.notification_service import NotificationService

cookie_scheme = APIKeyCookie(name="access_token", auto_error=False)


# 주입
def get_auth_service():
    return AuthService()


def get_chat_service():
    return ChatService()


def get_email_service():
    return EmailService()


def get_redis() -> Redis:
    return redis_client


def get_notification_repository(db: Session = Depends(get_db)):
    return NotificationRepository(db)


def get_notification_service():
    return NotificationService()


def get_current_user_optional(
    db: Session = Depends(get_db),
    token: str | None = Depends(cookie_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> User | None:
    if not token:
        return None
    try:
        email = auth_service.decode_access_token(token)
        user = db.query(User).filter(User.email == email).first()
        if not user or not user.is_active:
            return None
        return user
    except Exception:
        return None


# HTTP 데이터 추출
def get_client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def get_refresh_token_cookie(request: Request) -> str | None:
    return request.cookies.get("refresh_token")


# 공통 인증
def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("access_token")
    return AuthService().get_user_from_token(db, token)
