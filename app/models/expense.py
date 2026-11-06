from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.expense_split import ExpenseSplit
from app.models.user import User


class Expense(Base):
    """A payment made by one group member on behalf of the group.

    ``amount_paise`` is an integer number of paise (1 INR = 100 paise), so no
    floating point is ever involved in money arithmetic.
    """

    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("amount_paise > 0", name="amount_positive"),
        # Target of the composite FK from expense_splits, which guarantees a
        # split always carries the same group as its parent expense.
        UniqueConstraint("id", "group_id", name="uq_expenses_id_group_id"),
        # The payer must be a member of the expense's group (DB-level rule).
        ForeignKeyConstraint(
            ["group_id", "paid_by"],
            ["group_members.group_id", "group_members.user_id"],
            name="fk_expenses_payer_is_member",
            ondelete="RESTRICT",
        ),
        Index("ix_expenses_group_id_created_at", "group_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
    )
    paid_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    payer: Mapped[User] = relationship(lazy="joined")
    # expense_splits has two foreign keys into expenses (plain + same-group
    # composite); the plain expense_id one defines this relationship.
    splits: Mapped[list[ExpenseSplit]] = relationship(
        foreign_keys=[ExpenseSplit.expense_id],
        lazy="selectin",
        order_by=ExpenseSplit.user_id,
        cascade="all, delete-orphan",
    )
