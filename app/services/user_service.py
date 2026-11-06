from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models.user import User
from app.schemas.user import UserCreate
from app.utils.db import commit_or_raise


def create_user(db: Session, payload: UserCreate) -> User:
    taken = db.scalar(select(User.id).where(func.lower(User.name) == payload.name.lower()))
    if taken is not None:
        raise ConflictError(f"A user named '{payload.name}' already exists")
    user = User(name=payload.name)
    db.add(user)
    # A concurrent duplicate is still caught by the unique index on lower(name).
    commit_or_raise(db)
    db.refresh(user)
    return user


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)))


def get_user_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} not found")
    return user
