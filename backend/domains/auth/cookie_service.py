"""
cookie_service.py

인증 쿠키 설정 서비스.

## 환경변수 제어

| 변수                        | 기본값  | 설명                                                      |
|-----------------------------|---------|-----------------------------------------------------------|
| AUTH_COOKIE_SECURE          | false   | 로컬: false / 운영(HTTPS): true                           |
| AUTH_COOKIE_SAMESITE        | lax     | 로컬: lax / 운영: lax 또는 strict                         |
| AUTH_COOKIE_PATH            | /       | 쿠키 유효 경로                                            |
| AUTH_ACCESS_COOKIE_HTTPONLY | true    | access_token HttpOnly 여부 (프론트가 JS로 읽지 않으므로 true) |
| AUTH_REFRESH_COOKIE_HTTPONLY| true    | refresh_token HttpOnly 여부                               |

## 로컬 / 운영 권장 설정

로컬 (.env):
    AUTH_COOKIE_SECURE=false
    AUTH_COOKIE_SAMESITE=lax

운영 (backend.env):
    AUTH_COOKIE_SECURE=true
    AUTH_COOKIE_SAMESITE=lax

## 전제
- 프론트엔드는 access_token을 document.cookie나 JS로 직접 읽지 않는다.
- 인증 상태는 /api/auth/me API 응답으로만 판단한다.
- 따라서 access_token도 HttpOnly=true가 기본값이다.
"""

import os

from fastapi import Response

JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
)
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

_SECURE = os.getenv("AUTH_COOKIE_SECURE", "false").strip().lower() in {
    "1",
    "true",
    "yes",
}
_SAMESITE = os.getenv("AUTH_COOKIE_SAMESITE", "lax").strip().lower()
_PATH = os.getenv("AUTH_COOKIE_PATH", "/").strip()
_ACCESS_HTTPONLY = os.getenv(
    "AUTH_ACCESS_COOKIE_HTTPONLY", "true"
).strip().lower() not in {"0", "false", "no"}
_REFRESH_HTTPONLY = os.getenv(
    "AUTH_REFRESH_COOKIE_HTTPONLY", "true"
).strip().lower() not in {"0", "false", "no"}


class CookieService:
    @staticmethod
    def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=_ACCESS_HTTPONLY,
            secure=_SECURE,
            samesite=_SAMESITE,
            path=_PATH,
            max_age=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=_REFRESH_HTTPONLY,
            secure=_SECURE,
            samesite=_SAMESITE,
            path=_PATH,
            max_age=JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        )

    @staticmethod
    def delete_auth_cookies(response: Response):
        response.delete_cookie(
            key="access_token",
            httponly=_ACCESS_HTTPONLY,
            secure=_SECURE,
            samesite=_SAMESITE,
            path=_PATH,
        )
        response.delete_cookie(
            key="refresh_token",
            httponly=_REFRESH_HTTPONLY,
            secure=_SECURE,
            samesite=_SAMESITE,
            path=_PATH,
        )
