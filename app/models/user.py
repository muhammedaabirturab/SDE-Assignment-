from datetime import datetime

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class User(Base):
    """A person who can join groups, pay for expenses and owe a share."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# Names are the public handle in the balance / expense responses, so they must
# be unique, ignoring case ("Rahul" and "rahul" would be ambiguous).
Index("uq_users_name_lower", func.lower(User.name), unique=True)
