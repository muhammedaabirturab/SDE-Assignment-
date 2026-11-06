"""Initial schema: users, groups, members, expenses, splits, settlements.

Revision ID: 0001
Revises:
Create Date: 2026-11-06
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

NOW = sa.func.now()


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
    )
    op.create_index("uq_users_name_lower", "users", [sa.text("lower(name)")], unique=True)

    op.create_table(
        "groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_groups"),
    )

    op.create_table(
        "group_members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.ForeignKeyConstraint(
            ["group_id"], ["groups.id"], name="fk_group_members_group_id_groups", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_group_members_user_id_users", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_group_members"),
        sa.UniqueConstraint("group_id", "user_id", name="uq_group_members_group_user"),
    )
    op.create_index("ix_group_members_user_id", "group_members", ["user_id"])

    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("paid_by", sa.Integer(), nullable=False),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.CheckConstraint("amount_paise > 0", name=op.f("ck_expenses_amount_positive")),
        sa.ForeignKeyConstraint(
            ["group_id"], ["groups.id"], name="fk_expenses_group_id_groups", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["paid_by"], ["users.id"], name="fk_expenses_paid_by_users", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["group_id", "paid_by"],
            ["group_members.group_id", "group_members.user_id"],
            name="fk_expenses_payer_is_member",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_expenses"),
        sa.UniqueConstraint("id", "group_id", name="uq_expenses_id_group_id"),
    )
    op.create_index("ix_expenses_paid_by", "expenses", ["paid_by"])
    op.create_index("ix_expenses_group_id_created_at", "expenses", ["group_id", "created_at"])

    op.create_table(
        "expense_splits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("expense_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("share_paise", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("share_paise >= 0", name=op.f("ck_expense_splits_share_non_negative")),
        sa.ForeignKeyConstraint(
            ["expense_id"],
            ["expenses.id"],
            name="fk_expense_splits_expense_id_expenses",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_expense_splits_user_id_users", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["expense_id", "group_id"],
            ["expenses.id", "expenses.group_id"],
            name="fk_expense_splits_expense_same_group",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["group_id", "user_id"],
            ["group_members.group_id", "group_members.user_id"],
            name="fk_expense_splits_participant_is_member",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_expense_splits"),
        sa.UniqueConstraint("expense_id", "user_id", name="uq_expense_splits_expense_user"),
    )
    op.create_index("ix_expense_splits_user_id", "expense_splits", ["user_id"])

    op.create_table(
        "settlements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("paid_by", sa.Integer(), nullable=False),
        sa.Column("paid_to", sa.Integer(), nullable=False),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.CheckConstraint("amount_paise > 0", name=op.f("ck_settlements_amount_positive")),
        sa.CheckConstraint("paid_by <> paid_to", name=op.f("ck_settlements_no_self_payment")),
        sa.ForeignKeyConstraint(
            ["group_id"], ["groups.id"], name="fk_settlements_group_id_groups", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["paid_by"], ["users.id"], name="fk_settlements_paid_by_users", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["paid_to"], ["users.id"], name="fk_settlements_paid_to_users", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["group_id", "paid_by"],
            ["group_members.group_id", "group_members.user_id"],
            name="fk_settlements_payer_is_member",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["group_id", "paid_to"],
            ["group_members.group_id", "group_members.user_id"],
            name="fk_settlements_receiver_is_member",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_settlements"),
    )
    op.create_index("ix_settlements_paid_by", "settlements", ["paid_by"])
    op.create_index("ix_settlements_paid_to", "settlements", ["paid_to"])
    op.create_index("ix_settlements_group_id_created_at", "settlements", ["group_id", "created_at"])


def downgrade() -> None:
    op.drop_table("settlements")
    op.drop_table("expense_splits")
    op.drop_table("expenses")
    op.drop_table("group_members")
    op.drop_table("groups")
    op.drop_index("uq_users_name_lower", table_name="users")
    op.drop_table("users")
