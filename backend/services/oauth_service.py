import os
import urllib.parse

import httpx
from redis import Redis
from sqlalchemy.orm import Session

from errors.error_codes import ErrorCode
from errors.exceptions import AppException
from repositories.oauth_repository import OAuthRepository
from services.auth_service import AuthService

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")


class OAuthService:
    def __init__(self):
        self.auth_service = AuthService()
        self.backend_url = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
        self.frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip(
            "/"
        )

    def get_redirect_uri(self, provider: str) -> str:
        return f"{self.backend_url}/api/auth/social/{provider}/callback"

    def get_frontend_url(self) -> str:
        return self.frontend_url

    def get_google_auth_url(self, redirect_uri: str) -> str:
        params = {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"

    def get_github_auth_url(self, redirect_uri: str) -> str:
        params = {
            "client_id": GITHUB_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "scope": "read:user user:email",
        }
        return (
            f"https://github.com/login/oauth/authorize?{urllib.parse.urlencode(params)}"
        )

    async def get_google_profile(self, code: str, redirect_uri: str) -> dict | None:
        token_url = "https://oauth2.googleapis.com/token"
        async with httpx.AsyncClient() as client:
            token_res = await client.post(
                token_url,
                data={
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
            )
            if token_res.status_code != 200:
                return None
            access_token = token_res.json().get("access_token")

            user_res = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if user_res.status_code != 200:
                return None
            user_data = user_res.json()
            return {"provider_id": user_data.get("id"), "email": user_data.get("email")}

    async def get_github_profile(self, code: str, redirect_uri: str) -> dict | None:
        token_url = "https://github.com/login/oauth/access_token"
        async with httpx.AsyncClient() as client:
            token_res = await client.post(
                token_url,
                data={
                    "client_id": GITHUB_CLIENT_ID,
                    "client_secret": GITHUB_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Accept": "application/json"},
            )

            print(f"GitHub Token Response: {token_res.status_code} {token_res.text}")

            if token_res.status_code != 200:
                return None

            token_data = token_res.json()
            if "error" in token_data:
                return None

            access_token = token_data.get("access_token")
            if not access_token:
                return None

            user_res = await client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            print(f"GitHub User Response: {user_res.status_code} {user_res.text}")
            if user_res.status_code != 200:
                return None
            user_data = user_res.json()

            email = user_data.get("email")
            if not email:
                email_res = await client.get(
                    "https://api.github.com/user/emails",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                print(
                    f"GitHub Emails Response: {email_res.status_code} {email_res.text}"
                )
                if email_res.status_code == 200:
                    emails = email_res.json()
                    primary_email = next(
                        (e["email"] for e in emails if e.get("primary")), None
                    )
                    if primary_email:
                        email = primary_email
                    elif emails:
                        email = emails[0]["email"]

            return {"provider_id": str(user_data.get("id")), "email": email}

    async def process_social_callback(
        self,
        db: Session,
        redis_client: Redis,
        provider: str,
        code: str,
        redirect_uri: str,
        current_user_token: str | None,
        frontend_url: str,
    ) -> dict:
        repository = OAuthRepository(db)

        profile = None
        if provider == "google":
            profile = await self.get_google_profile(code, redirect_uri)
        elif provider == "github":
            profile = await self.get_github_profile(code, redirect_uri)

        if not profile or not profile.get("email"):
            return {
                "action": "redirect",
                "url": f"{frontend_url}/?error=social_auth_failed",
            }

        email = profile["email"].strip().lower()
        provider_id = profile["provider_id"]

        current_user = None
        if current_user_token:
            try:
                token_email = self.auth_service.decode_access_token(current_user_token)
                current_user = repository.get_user_by_email(token_email)
            except Exception:
                pass

        if current_user and current_user.is_active:
            if email != current_user.email:
                error_message = urllib.parse.quote(
                    "현재 계정의 이메일과 일치하는 소셜 계정만 연동할 수 있습니다."
                )
                return {
                    "action": "redirect",
                    "url": f"{frontend_url}/mypage?social_error={error_message}&provider={provider}",
                }

            existing_social = repository.get_social_account(provider, provider_id)
            if existing_social and existing_social.user_id != current_user.id:
                error_message = urllib.parse.quote(
                    "해당 소셜 계정은 이미 다른 사용자와 연동되어 있습니다."
                )
                return {
                    "action": "redirect",
                    "url": f"{frontend_url}/mypage?social_error={error_message}&provider={provider}",
                }

            user_existing_social = repository.get_social_account_by_user(
                current_user.id, provider
            )
            if not user_existing_social:
                repository.create_social_account(
                    current_user.id, provider, provider_id, email
                )
            return {
                "action": "redirect",
                "url": f"{frontend_url}/mypage?social_link=success",
            }

        social_account = repository.get_social_account(provider, provider_id)

        if social_account:
            user = repository.get_user_by_id(social_account.user_id)
            if user and user.is_active:
                access_token, refresh_token = self.auth_service._issue_tokens(
                    redis_client, user.email
                )
                return {
                    "action": "login",
                    "url": f"{frontend_url}/?login=success",
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                }
            else:
                return {
                    "action": "redirect",
                    "url": f"{frontend_url}/?error=account_inactive",
                }

        user = repository.get_user_by_email(email)
        if user:
            if not user.is_active:
                return {
                    "action": "redirect",
                    "url": f"{frontend_url}/?error=account_inactive",
                }

            repository.create_social_account(user.id, provider, provider_id, email)
            access_token, refresh_token = self.auth_service._issue_tokens(
                redis_client, user.email
            )
            return {
                "action": "login",
                "url": f"{frontend_url}/?login=success",
                "access_token": access_token,
                "refresh_token": refresh_token,
            }
        else:
            redis_client.setex(
                f"email_verified:{email}", 1800, f"social:{provider}:{provider_id}"
            )

            return {
                "action": "redirect",
                "url": f"{frontend_url}/?error=not_registered&email={urllib.parse.quote(email)}&provider={provider}",
            }

    def unlink_social_account(self, db: Session, user_id: int, provider: str):
        repository = OAuthRepository(db)
        social_account = repository.get_social_account_by_user(user_id, provider)
        if not social_account:
            raise AppException(ErrorCode.AUTH_FORBIDDEN)
        repository.delete_social_account(social_account)
