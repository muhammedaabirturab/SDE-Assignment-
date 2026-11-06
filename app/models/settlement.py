from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.user import User


class Settlement(Base):
    """A real repayment: ``paid_by`` handed ``amount_paise`` to ``paid_to``.

    Settlements are append-only history. They never edit or delete expenses;
    the balance engine simply counts them as money moved between members.
    """

    __tablename__ = "settlements"
    __table_args__ = (
        CheckConstraint("amount_paise > 0", name="amount_positive"),
        CheckConstraint("paid_by <> paid_to", name="no_self_payment"),
        ForeignKeyConstraint(
            ["group_id", "paid_by"],
            ["group_members.group_id", "group_members.user_id"],
            name="fk_settlements_payer_is_member",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["group_id", "paid_to"],
            ["group_members.group_id", "group_members.user_id"],
            name="fk_settlements_receiver_is_member",
            ondelete="RESTRICT",
        ),
        Index("ix_settlements_group_id_created_at", "group_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
    )
    paid_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    paid_to: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    note: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    payer: Mapped[User] = relationship(foreign_keys=[paid_by], lazy="joined")
    receiver: Mapped[User] = relationship(foreign_keys=[paid_to], lazy="joined")
