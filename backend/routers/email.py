import random
import string

from fastapi import APIRouter

from errors import AppException, ErrorCode
from redis_client import redis_client
from schemas.email import EmailRequest, EmailVerifyRequest
from services.email_service import send_verification_email

router = APIRouter(prefix="/email", tags=["email"])


@router.post("/send-verification-code")
def send_verification_code(payload: EmailRequest):
    email = payload.email.strip().lower()
    code = "".join(random.choices(string.digits, k=6))

    redis_client.setex(f"email_verify:{email}", 180, code)

    try:
        send_verification_email(email, code)
    except Exception:
        redis_client.delete(f"email_verify:{email}")
        raise AppException(ErrorCode.EMAIL_SEND_FAILED)

    return {"message": "인증 코드가 발송되었습니다."}


@router.post("/verify-code")
def verify_code(payload: EmailVerifyRequest):
    email = payload.email.strip().lower()
    stored_code = redis_client.get(f"email_verify:{email}")

    if not stored_code:
        raise AppException(ErrorCode.EMAIL_CODE_NOT_FOUND)

    if stored_code != payload.code.strip():
        raise AppException(ErrorCode.EMAIL_CODE_MISMATCH)

    redis_client.delete(f"email_verify:{email}")
    redis_client.setex(f"email_verified:{email}", 600, "1")

    return {"message": "인증이 완료되었습니다."}
