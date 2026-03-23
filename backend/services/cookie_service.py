from fastapi import Response
import os

JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

class CookieService:
    @staticmethod
    def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=False,
            secure=False,  
            samesite="lax",
            max_age=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=False, 
            samesite="lax",
            max_age=JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        )

    @staticmethod
    def delete_auth_cookies(response: Response):
        response.delete_cookie(key="refresh_token", httponly=True, samesite="lax")
        response.delete_cookie(key="access_token", samesite="lax")
