from fastapi import APIRouter, Depends
from redis import Redis

from dependencies import get_current_user_optional, get_email_service, get_redis
from domains.email.schemas import EmailRequest, EmailVerifyRequest
from domains.email.service import EmailService
from models.model import User

router = APIRouter(prefix="/email", tags=["email"])


@router.post("/send-verification-code")
def send_verification_code(
    payload: EmailRequest,
    redis: Redis = Depends(get_redis),
    current_user: User | None = Depends(get_current_user_optional),
    email_service: EmailService = Depends(get_email_service),
):
    email_service.send_verification_code(redis, payload.email, current_user)


@router.post("/verify-code")
def verify_code(
    payload: EmailVerifyRequest,
    redis: Redis = Depends(get_redis),
    email_service: EmailService = Depends(get_email_service),
):
    email_service.verify_code(redis, payload.email, payload.code)
