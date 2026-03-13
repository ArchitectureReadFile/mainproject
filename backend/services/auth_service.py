import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from errors import AppException, ErrorCode
from models.model import User
from schemas.auth import SignupRequest

load_dotenv()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY is required. Set it in environment variables.")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
)
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))


def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise AppException(ErrorCode.USER_PASSWORD_TOO_LONG)
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if len(plain_password.encode("utf-8")) > 72:
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except ValueError:
        return False


def create_access_token(subject: str) -> str:
    expire_at = datetime.now(timezone.utc) + timedelta(
        minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": subject, "exp": expire_at, "type": "access"}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(subject: str) -> str:
    expire_at = datetime.now(timezone.utc) + timedelta(
        days=JWT_REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload = {"sub": subject, "exp": expire_at, "type": "refresh"}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise ValueError("Invalid token type")
        email = payload.get("sub")
        if not email:
            raise ValueError("Missing subject")
        return email
    except (JWTError, ValueError):
        raise AppException(ErrorCode.AUTH_TOKEN_INVALID)


def decode_refresh_token(token: str) -> str:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise ValueError("Invalid token type")
        email = payload.get("sub")
        if not email:
            raise ValueError("Missing subject")
        return email
    except (JWTError, ValueError):
        raise AppException(ErrorCode.AUTH_REFRESH_TOKEN_INVALID)


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def create_user(db: Session, payload: SignupRequest) -> User:
    email = payload.email.strip().lower()
    username = payload.username.strip()

    if get_user_by_email(db, email):
        raise AppException(ErrorCode.USER_EMAIL_ALREADY_EXISTS)

    if get_user_by_username(db, username):
        raise AppException(ErrorCode.USER_USERNAME_ALREADY_EXISTS)

    user = User(
        email=email,
        username=username,
        password=hash_password(payload.password),
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    return user
