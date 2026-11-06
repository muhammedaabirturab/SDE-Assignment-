from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.user import User


class ExpenseSplit(Base):
    """One participant's share of an expense, frozen at creation time.

    Balances are computed from these rows, never from the *current* group
    membership, so members who join later are not charged for old expenses.
    ``group_id`` is stored redundantly so composite foreign keys can force
    both the expense and the participant to belong to that same group.
    """

    __tablename__ = "expense_splits"
    __table_args__ = (
        UniqueConstraint("expense_id", "user_id", name="uq_expense_splits_expense_user"),
        CheckConstraint("share_paise >= 0", name="share_non_negative"),
        ForeignKeyConstraint(
            ["expense_id", "group_id"],
            ["expenses.id", "expenses.group_id"],
            name="fk_expense_splits_expense_same_group",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["group_id", "user_id"],
            ["group_members.group_id", "group_members.user_id"],
            name="fk_expense_splits_participant_is_member",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    expense_id: Mapped[int] = mapped_column(
        ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False
    )
    group_id: Mapped[int] = mapped_column(nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    share_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)

    user: Mapped[User] = relationship(lazy="joined")
