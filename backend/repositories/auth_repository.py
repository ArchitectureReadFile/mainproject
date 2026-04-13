from sqlalchemy.orm import Session

from models.model import Group, SocialAccount, Subscription, User


class AuthRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_user_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def get_user_by_username(self, username: str) -> User | None:
        return self.db.query(User).filter(User.username == username).first()

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def create_user(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        return user

    def create_social_account(self, social_account: SocialAccount) -> SocialAccount:
        self.db.add(social_account)
        self.db.flush()
        return social_account

    def create_subscription(self, subscription: Subscription) -> Subscription:
        self.db.add(subscription)
        self.db.commit()
        return subscription

    def get_subscription_by_user_id(self, user_id: int) -> Subscription | None:
        return (
            self.db.query(Subscription).filter(Subscription.user_id == user_id).first()
        )

    def get_pending_groups(
        self, owner_user_id: int, statuses: list, pending_reason
    ) -> list[Group]:
        return (
            self.db.query(Group)
            .filter(
                Group.owner_user_id == owner_user_id,
                Group.status.in_(statuses),
                Group.pending_reason == pending_reason,
            )
            .all()
        )

    def has_owned_groups(self, user_id: int) -> bool:
        return (
            self.db.query(Group).filter(Group.owner_user_id == user_id).first()
            is not None
        )

    def deactivate_user(self, user: User, deactivated_at):
        user.is_active = False
        user.deactivated_at = deactivated_at
        self.db.commit()

    def add(self, obj):
        self.db.add(obj)

    def commit(self):
        self.db.commit()

    def refresh(self, obj):
        self.db.refresh(obj)
