from fastapi import Depends, Request
from sqlalchemy.orm import Session
from redis import Redis

from database import get_db
from redis_client import redis_client
from models.model import User
from services.auth_service import AuthService
from services.chat_service import ChatService
from services.email_service import EmailService

# 서비스 주입
def get_auth_service():
    return AuthService()


def get_chat_service():
    return ChatService()

def get_email_service():
    return EmailService()

def get_redis() -> Redis:
    return redis_client

# HTTP 데이터 추출
def get_client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"

def get_refresh_token_cookie(request: Request) -> str | None:
    return request.cookies.get("refresh_token")

# 공통 인증
def get_current_user(
    request: Request, 
    db: Session = Depends(get_db)
) -> User:
    token = request.cookies.get("access_token")
    # AuthService 인스턴스를 생성하여 메서드 호출 (상태가 없으므로 가볍습니다)
    return AuthService().get_user_from_token(db, token)
