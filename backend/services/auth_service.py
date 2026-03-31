import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from redis import Redis
from requests import Session

from errors.error_codes import ErrorCode
from errors.exceptions import AppException
from models.model import (
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
    User,
    utc_now_naive,
)
from schemas.auth import (
    CancelSubscriptionRequest,
    ConfirmAccountRequest,
    LoginRequest,
    ResetPasswordRequest,
    SignupRequest,
    UpdateEmailRequest,
    UpdatePasswordRequest,
    SubscribePremiumRequest,
    SubscriptionResponse,
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
            auto_renew=False,
        )
        db.add(subscription)
        db.commit()

        redis_client.delete(f"email_verified:{email}")
        return self.to_user_response(db, user)

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
        return self.to_user_response(db, user), access_token, refresh_token

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

        return self.to_user_response(db, user), new_access_token, new_refresh_token

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

        return self.to_user_response(db, user)

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
            
        access_token, refresh_token = self._issue_tokens(redis_client, new_email)
        return self.to_user_response(db, user), access_token, refresh_token

    def update_notification_settings(
        self, db: Session, user_id: int, is_enabled: bool
    ) -> UserResponse:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise AppException(ErrorCode.USER_NOT_FOUND)

        user.is_toast_notification_enabled = is_enabled
        db.commit()
        db.refresh(user)
        return self.to_user_response(db, user)

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

    def to_user_response(self, db: Session, user: User) -> UserResponse:
        subscription = self.get_effective_subscription(db, user.id)

        return UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            role=user.role.value,
            is_active=user.is_active,
            is_toast_notification_enabled=user.is_toast_notification_enabled,
            created_at=user.created_at,
            subscription=(
                SubscriptionResponse(
                    plan=subscription.plan.value,
                    status=subscription.status.value,
                    auto_renew=subscription.auto_renew,
                    started_at=subscription.started_at,
                    ended_at=subscription.ended_at,
                )
                if subscription
                else None
            ),
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

    def ensure_subscription_state(
        self, db: Session, subscription: Subscription | None
    ) -> Subscription | None:
        """구독 상태 보정용 함수, 구독 상태를 현재 시각 기준으로 정규화"""
        if not subscription:
            return None

        now = utc_now_naive()
        changed = False

        if subscription.plan == SubscriptionPlan.FREE:
            if subscription.auto_renew:
                subscription.auto_renew = False
                changed = True
            if subscription.ended_at is not None:
                subscription.ended_at = None
                changed = True
            if subscription.status != SubscriptionStatus.ACTIVE:
                subscription.status = SubscriptionStatus.ACTIVE
                changed = True

        elif subscription.plan == SubscriptionPlan.PREMIUM:
            if subscription.ended_at and subscription.ended_at <= now:
                if (
                    subscription.auto_renew
                    and subscription.status == SubscriptionStatus.ACTIVE
                ):
                    while subscription.ended_at and subscription.ended_at <= now:
                        previous_end = subscription.ended_at
                        subscription.started_at = previous_end
                        subscription.ended_at = previous_end + timedelta(days=30)
                    changed = True
                else:
                    if subscription.status != SubscriptionStatus.EXPIRED:
                        subscription.status = SubscriptionStatus.EXPIRED
                        changed = True

        if changed:
            db.commit()
            db.refresh(subscription)

        return subscription

    def get_subscription_or_create_free(
        self, db: Session, user_id: int
    ) -> Subscription:
        """사용자의 구독 레코드 반환"""
        subscription = (
            db.query(Subscription).filter(Subscription.user_id == user_id).first()
        )
        if subscription:
            return subscription

        subscription = Subscription(
            user_id=user_id,
            plan=SubscriptionPlan.FREE,
            status=SubscriptionStatus.ACTIVE,
            auto_renew=False,
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)
        return subscription

    def subscribe_premium(
        self, db: Session, user_id: int, payload: SubscribePremiumRequest
    ) -> UserResponse:
        """프리미엄 구독으로 변경"""
        if not payload.confirm:
            raise AppException(ErrorCode.AUTH_FORBIDDEN)

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise AppException(ErrorCode.USER_NOT_FOUND)

        subscription = self.get_subscription_or_create_free(db, user_id)
        now = utc_now_naive()

        if (
            subscription.plan == SubscriptionPlan.PREMIUM
            and subscription.ended_at
            and subscription.ended_at > now
            and subscription.status
            in (
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.CANCELED,
            )
        ):
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.auto_renew = True
        else:
            subscription.plan = SubscriptionPlan.PREMIUM
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.auto_renew = True
            subscription.started_at = now
            subscription.ended_at = now + timedelta(days=30)

        db.commit()
        db.refresh(user)
        db.refresh(subscription)
        return self.to_user_response(db, user)

    def cancel_subscription(
        self, db: Session, user_id: int, payload: CancelSubscriptionRequest
    ) -> UserResponse:
        """구독 해지(자동 갱신 해지)"""
        if not payload.confirm:
            raise AppException(ErrorCode.AUTH_FORBIDDEN)

        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            raise AppException(ErrorCode.USER_NOT_FOUND)

        subscription = self.get_subscription_or_create_free(db, user_id)
        subscription = self.ensure_subscription_state(db, subscription)

        if subscription.plan == SubscriptionPlan.FREE:
            return self.to_user_response(db, user)

        subscription.auto_renew = False

        if subscription.status == SubscriptionStatus.ACTIVE:
            subscription.status = SubscriptionStatus.CANCELED

        db.commit()
        db.refresh(user)
        db.refresh(subscription)
        return self.to_user_response(db, user)

    def get_effective_subscription(self, db: Session, user_id: int) -> Subscription:
        """현재 시각 기준으로 유효한 구독 상태를 반환"""
        subscription = self.get_subscription_or_create_free(db, user_id)
        return self.ensure_subscription_state(db, subscription)

    def is_premium_active(self, db: Session, user_id: int) -> bool:
        """사용자가 현재 프리미엄 권한을 사용할 수 있는지 반환"""
        subscription = self.get_effective_subscription(db, user_id)

        return (
            subscription.plan == SubscriptionPlan.PREMIUM
            and subscription.status == SubscriptionStatus.ACTIVE
            and subscription.ended_at is not None
        )
