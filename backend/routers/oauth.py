from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from redis import Redis

from dependencies import get_current_user, get_oauth_service, get_redis
from models.model import User
from services.cookie_service import CookieService
from services.oauth_service import OAuthService

router = APIRouter(prefix="/auth/social", tags=["oauth"])


@router.get("/{provider}/login")
def social_login(
    provider: str, oauth_service: OAuthService = Depends(get_oauth_service)
):
    redirect_uri = oauth_service.get_redirect_uri(provider)

    if provider == "google":
        return RedirectResponse(url=oauth_service.get_google_auth_url(redirect_uri))
    elif provider == "github":
        return RedirectResponse(url=oauth_service.get_github_auth_url(redirect_uri))

    frontend_url = oauth_service.get_frontend_url()
    return RedirectResponse(url=f"{frontend_url}/?error=invalid_provider")


@router.get("/{provider}/callback")
async def social_callback(
    provider: str,
    code: str,
    request: Request,
    redis: Redis = Depends(get_redis),
    oauth_service: OAuthService = Depends(get_oauth_service),
):
    redirect_uri = oauth_service.get_redirect_uri(provider)
    frontend_url = oauth_service.get_frontend_url()
    current_user_token = request.cookies.get("access_token")

    result = await oauth_service.process_social_callback(
        redis_client=redis,
        provider=provider,
        code=code,
        redirect_uri=redirect_uri,
        current_user_token=current_user_token,
        frontend_url=frontend_url,
    )

    res = RedirectResponse(url=result["url"])
    if result["action"] == "login":
        CookieService.set_auth_cookies(
            res, result.get("access_token"), result.get("refresh_token")
        )
    return res


@router.delete("/{provider}/unlink")
def unlink_social_account(
    provider: str,
    current_user: User = Depends(get_current_user),
    oauth_service: OAuthService = Depends(get_oauth_service),
):
    oauth_service.unlink_social_account(current_user.id, provider)
    return {"message": f"{provider} 연동해제되었습니다."}
