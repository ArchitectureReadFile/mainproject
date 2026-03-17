import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database import init_db
from errors.exceptions import AppException
from routers.admin import router as admin_router
from routers.auth import router as auth_router
from routers.document import router as document_router
from routers.email import router as email_router
from routers.summarize import router as summarize_router
from routers.ws import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Team Project API", lifespan=lifespan, redirect_slashes=False)


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
app.include_router(admin_router, prefix="/api")
app.include_router(summarize_router, prefix="/api")
app.include_router(document_router, prefix="/api")
app.include_router(email_router, prefix="/api")
app.include_router(ws_router, prefix="/api")
