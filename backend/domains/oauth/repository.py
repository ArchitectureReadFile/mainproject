from sqlalchemy.orm import Session

from models.model import SocialAccount, User


class OAuthRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_social_account(
        self, provider: str, provider_id: str
    ) -> SocialAccount | None:
        return (
            self.db.query(SocialAccount)
            .filter(
                SocialAccount.provider == provider,
                SocialAccount.provider_id == provider_id,
            )
            .first()
        )

    def get_social_account_by_user(
        self, user_id: int, provider: str
    ) -> SocialAccount | None:
        return (
            self.db.query(SocialAccount)
            .filter(
                SocialAccount.user_id == user_id, SocialAccount.provider == provider
            )
            .first()
        )

    def create_social_account(
        self, user_id: int, provider: str, provider_id: str, email: str
    ) -> SocialAccount:
        social_account = SocialAccount(
            user_id=user_id, provider=provider, provider_id=provider_id, email=email
        )
        self.db.add(social_account)
        self.db.commit()
        return social_account

    def delete_social_account(self, social_account: SocialAccount):
        self.db.delete(social_account)
        self.db.commit()

    def get_user_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()
