import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from redis import Redis
from requests import Session

from errors.error_codes import ErrorCode
from errors.exceptions import AppException
from models.model import Subscription, SubscriptionPlan, SubscriptionStatus, User
from schemas.auth import (
    ConfirmAccountRequest,
    LoginRequest,
    ResetPasswordRequest,
    SignupRequest,
    UpdateEmailRequest,
    UpdatePasswordRequest,
    UserResponse,
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
)
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

LOGIN_RATE_LIMIT_MAX_ATTEMPTS = int(os.getenv("LOGIN_RATE_LIMIT_MAX_ATTEMPTS", "5"))
LOGIN_RATE_LIMIT_WINDOW_SECONDS = int(
    os.getenv("LOGIN_RATE_LIMIT_WINDOW_SECONDS", "300")
)
LOGIN_RATE_LIMIT_BLOCK_SECONDS = int(os.getenv("LOGIN_RATE_LIMIT_BLOCK_SECONDS", "300"))


class AuthService:
    def signup(
        self, db: Session, redis_client: Redis, payload: SignupRequest
    ) -> UserResponse:
        email = payload.email.strip().lower()

        if not redis_client.get(f"email_verified:{email}"):
            raise AppException(ErrorCode.USER_EMAIL_NOT_VERIFIED)

        username = payload.username.strip()
        if db.query(User).filter(User.email == email).first():
            raise AppException(ErrorCode.USER_EMAIL_ALREADY_EXISTS)
        if db.query(User).filter(User.username == username).first():
            raise AppException(ErrorCode.USER_USERNAME_ALREADY_EXISTS)

        user = User(
            email=email,
            username=username,
            password=self.hash_password(payload.password),
        )
        db.add(user)
        db.flush()

        subscription = Subscription(
            user_id=user.id,
            plan=SubscriptionPlan.FREE,
            status=SubscriptionStatus.ACTIVE,
        )
        db.add(subscription)
        db.commit()

        redis_client.delete(f"email_verified:{email}")
        return self.to_user_response(user)

    def login(
        self, db: Session, redis_client: Redis, payload: LoginRequest, client_ip: str
    ):
        email = payload.email.strip().lower()
        limit_key = f"{client_ip}:{email}"

        self._check_login_rate_limit(redis_client, limit_key)

        user = db.query(User).filter(User.email == email).first()
        if not user or not self.verify_password(payload.password, user.password):
            self._record_login_failure(redis_client, limit_key)
            raise AppException(ErrorCode.USER_INVALID_CREDENTIALS)

        if not user.is_active:
            self._record_login_failure(redis_client, limit_key)
            if user.deactivated_at is not None:
                raise AppException(ErrorCode.USER_DEACTIVATE_PENDING)
            raise AppException(ErrorCode.USER_INACTIVE)

        self._clear_login_failures(redis_client, limit_key)

        access_token, refresh_token = self._issue_tokens(redis_client, email)
        return self.to_user_response(user), access_token, refresh_token

    def refresh(self, db: Session, redis_client: Redis, refresh_token: str | None):
        if not refresh_token:
            raise AppException(ErrorCode.AUTH_REFRESH_TOKEN_MISSING)

        stored_email = redis_client.get(f"refresh_token:{refresh_token}")
        if not stored_email:
            raise AppException(ErrorCode.AUTH_REFRESH_TOKEN_EXPIRED)

        if isinstance(stored_email, bytes):
            stored_email = stored_email.decode("utf-8")

        email = self.decode_refresh_token(refresh_token)
        user = db.query(User).filter(User.email == email).first()

        if not user or not user.is_active or user.email != stored_email:
            raise AppException(ErrorCode.AUTH_USER_INVALID)

        redis_client.delete(f"refresh_token:{refresh_token}")
        new_access_token, new_refresh_token = self._issue_tokens(
            redis_client, user.email
        )

        return self.to_user_response(user), new_access_token, new_refresh_token

    def logout(self, redis_client: Redis, refresh_token: str | None):
        if refresh_token:
            redis_client.delete(f"refresh_token:{refresh_token}")

    def confirm_account(
        self, db: Session, redis_client: Redis, payload: ConfirmAccountRequest
    ) -> UserResponse:
        email = payload.email.strip().lower()

        if not redis_client.get(f"email_verified:{email}"):
            raise AppException(ErrorCode.USER_EMAIL_NOT_VERIFIED)

        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise AppException(ErrorCode.USER_ACCOUNT_NOT_FOUND)

        return self.to_user_response(user)

    def reset_password(
        self, db: Session, redis_client: Redis, payload: ResetPasswordRequest
    ):
        email = payload.email.strip().lower()

        if not redis_client.get(f"email_verified:{email}"):
            raise AppException(ErrorCode.USER_EMAIL_NOT_VERIFIED)

        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise AppException(ErrorCode.USER_NOT_FOUND)

        user.password = self.hash_password(payload.new_password)
        db.commit()

        redis_client.delete(f"email_verified:{email}")

    def deactivate_account(self, db: Session, redis_client: Redis, user_id: int):
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise AppException(ErrorCode.USER_NOT_FOUND)

        if not redis_client.get(f"email_verified:{user.email}"):
            raise AppException(ErrorCode.USER_EMAIL_NOT_VERIFIED)

        user.is_active = False
        user.deactivated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()

        redis_client.delete(f"email_verified:{user.email}")

    def reactivate_account(
        self, db: Session, redis_client: Redis, payload: LoginRequest, client_ip: str
    ):
        email = payload.email.strip().lower()
        limit_key = f"{client_ip}:{email}"

        self._check_login_rate_limit(redis_client, limit_key)

        user = db.query(User).filter(User.email == email).first()
        if not user or not self.verify_password(payload.password, user.password):
            self._record_login_failure(redis_client, limit_key)
            raise AppException(ErrorCode.USER_INVALID_CREDENTIALS)

        user.is_active = True
        user.deactivated_at = None
        db.commit()

        self._clear_login_failures(redis_client, limit_key)

        access_token, refresh_token = self._issue_tokens(redis_client, email)
        return self.to_user_response(user), access_token, refresh_token

    def update_username(
        self, db: Session, user_id: int, new_username: str
    ) -> UserResponse:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise AppException(ErrorCode.USER_NOT_FOUND)

        if new_username != user.username:
            existing = db.query(User).filter(User.username == new_username).first()
            if existing:
                raise AppException(ErrorCode.USER_USERNAME_ALREADY_EXISTS)

            user.username = new_username
            db.commit()

        return self.to_user_response(user)

    def update_password(
        self, db: Session, user_id: int, payload: UpdatePasswordRequest
    ):
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise AppException(ErrorCode.USER_NOT_FOUND)

        if not self.verify_password(payload.current_password, user.password):
            raise AppException(ErrorCode.USER_INVALID_CREDENTIALS)

        if not self.verify_password(payload.new_password, user.password):
            user.password = self.hash_password(payload.new_password)
            db.commit()
        else:
            pass

    def update_email(
        self,
        db: Session,
        redis_client: Redis,
        user_id: int,
        payload: UpdateEmailRequest,
    ) -> tuple[UserResponse, str, str]:
        new_email = payload.new_email.strip().lower()

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise AppException(ErrorCode.USER_NOT_FOUND)

        if new_email != user.email:
            if not redis_client.get(f"email_verified:{new_email}"):
                raise AppException(ErrorCode.USER_EMAIL_NOT_VERIFIED)

            user.email = new_email
            db.commit()

            redis_client.delete(f"email_verified:{new_email}")
        else:
            pass

        access_token, refresh_token = self._issue_tokens(redis_client, new_email)
        return self.to_user_response(user), access_token, refresh_token

    def update_notification_settings(
        self, db: Session, user_id: int, is_enabled: bool
    ) -> UserResponse:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise AppException(ErrorCode.USER_NOT_FOUND)

        user.is_toast_notification_enabled = is_enabled
        db.commit()
        db.refresh(user)
        return self.to_user_response(user)

    def hash_password(self, password: str) -> str:
        if len(password.encode("utf-8")) > 72:
            raise AppException(ErrorCode.USER_PASSWORD_TOO_LONG)
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        if len(plain_password.encode("utf-8")) > 72:
            return False
        return pwd_context.verify(plain_password, hashed_password)

    def create_access_token(
        self, subject: str, expire_minutes: int = JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    ) -> str:
        expire_at = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
        payload = {"sub": subject, "exp": expire_at, "type": "access"}
        return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    def create_refresh_token(
        self,
        subject: str,
        expire_minutes: int = JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60,
    ) -> str:
        expire_at = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
        payload = {"sub": subject, "exp": expire_at, "type": "refresh"}
        return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    def decode_access_token(self, token: str) -> str:
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            if payload.get("type") != "access":
                raise ValueError
            email = payload.get("sub")
            if not email:
                raise ValueError
            return email
        except (JWTError, ValueError):
            raise AppException(ErrorCode.AUTH_TOKEN_INVALID)

    def decode_refresh_token(self, token: str) -> str:
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            if payload.get("type") != "refresh":
                raise ValueError
            email = payload.get("sub")
            if not email:
                raise ValueError
            return email
        except (JWTError, ValueError):
            raise AppException(ErrorCode.AUTH_REFRESH_TOKEN_INVALID)

    def to_user_response(self, user: User) -> UserResponse:
        return UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            role=user.role.value,
            is_active=user.is_active,
            is_toast_notification_enabled=user.is_toast_notification_enabled,
            created_at=user.created_at,
        )

    def get_user_from_token(self, db: Session, token: str | None) -> User:
        if not token:
            raise AppException(ErrorCode.AUTH_TOKEN_MISSING)

        email = self.decode_access_token(token)
        user = db.query(User).filter(User.email == email).first()

        if not user or not user.is_active:
            raise AppException(ErrorCode.AUTH_USER_INVALID)
        return user

    def _issue_tokens(self, redis_client: Redis, email: str):
        access_token = self.create_access_token(email)
        refresh_token = self.create_refresh_token(email)

        ttl = JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
        redis_client.setex(f"refresh_token:{refresh_token}", ttl, email)

        return access_token, refresh_token

    def _check_login_rate_limit(self, redis_client: Redis, key: str):
        if redis_client.get(f"block:{key}"):
            raise AppException(ErrorCode.USER_RATE_LIMIT_EXCEEDED)

    def _record_login_failure(self, redis_client: Redis, key: str):
        attempt_key = f"attempts:{key}"
        block_key = f"block:{key}"
        attempts = redis_client.incr(attempt_key)
        if attempts == 1:
            redis_client.expire(attempt_key, LOGIN_RATE_LIMIT_WINDOW_SECONDS)
        if attempts >= LOGIN_RATE_LIMIT_MAX_ATTEMPTS:
            redis_client.setex(block_key, LOGIN_RATE_LIMIT_BLOCK_SECONDS, "1")
            redis_client.delete(attempt_key)

    def _clear_login_failures(self, redis_client: Redis, key: str):
        redis_client.delete(f"attempts:{key}", f"block:{key}")
