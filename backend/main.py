import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from domains.admin.router import router as admin_router
from domains.auth.router import router as auth_router
from domains.chat.router import router as chat_router
from domains.chat.ws_router import router as ws_router
from domains.document.router import router as group_document_router
from domains.document.summary_router import router as summarize_router
from domains.email.router import router as email_router
from domains.export.router import router as export_router
from domains.notification.router import router as notification_router
from domains.oauth.router import router as oauth_router
from domains.workspace.router import router as group_router
from errors.exceptions import AppException

app = FastAPI(title="Team Project API", redirect_slashes=False)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message},
    )


cors_origins = os.getenv(
    "CORS_ALLOW_ORIGINS",
    "http://127.0.0.1:5173,http://localhost:5173",
).split(",")
cors_origins = [origin.strip() for origin in cors_origins if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


app.include_router(auth_router, prefix="/api")
app.include_router(oauth_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(summarize_router, prefix="/api")
app.include_router(group_document_router, prefix="/api")
app.include_router(email_router, prefix="/api")
app.include_router(ws_router, prefix="/api")
app.include_router(group_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(notification_router, prefix="/api")
app.include_router(export_router, prefix="/api")
