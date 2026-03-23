from fastapi import APIRouter, Depends
from redis import Redis

from schemas.email import EmailRequest, EmailVerifyRequest
from services.email_service import EmailService
from dependencies import get_email_service, get_redis

router = APIRouter(prefix="/email", tags=["email"])

@router.post("/send-verification-code")
def send_verification_code(
    payload: EmailRequest,
    redis: Redis = Depends(get_redis),
    email_service: EmailService = Depends(get_email_service)
):
    email_service.send_verification_code(redis, payload.email)

@router.post("/verify-code")
def verify_code(
    payload: EmailVerifyRequest,
    redis: Redis = Depends(get_redis),
    email_service: EmailService = Depends(get_email_service)
):
    email_service.verify_code(redis, payload.email, payload.code)
