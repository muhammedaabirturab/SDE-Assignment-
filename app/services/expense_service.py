from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError
from app.models.expense import Expense
from app.models.expense_split import ExpenseSplit
from app.schemas.expense import ExpenseCreate
from app.services.group_service import get_group_or_404, get_member_ids
from app.services.user_service import get_user_or_404
from app.utils.db import commit_or_raise
from app.utils.money import rupees_to_paise, split_equally


def calculate_shares(
    payload: ExpenseCreate, amount_paise: int, member_ids: set[int]
) -> dict[int, int]:
    """Decide each participant's share (in paise) and validate the allocation.

    * ``splits``       -> custom amounts, must add up exactly to the total
    * ``participants`` -> equal split between those members only
    * neither          -> equal split between all current group members
    """
    if payload.splits is not None:
        shares = {split.user_id: rupees_to_paise(split.amount) for split in payload.splits}
        _require_members(shares, member_ids)
        if sum(shares.values()) != amount_paise:
            raise BusinessRuleError("The split amounts must add up exactly to the expense amount")
        return shares

    participants = set(payload.participants) if payload.participants is not None else member_ids
    _require_members(participants, member_ids)
    return split_equally(amount_paise, participants)


def _require_members(participant_ids, member_ids: set[int]) -> None:
    outsiders = sorted(set(participant_ids) - member_ids)
    if outsiders:
        raise BusinessRuleError(f"Users {outsiders} are not members of this group")


def create_expense(db: Session, payload: ExpenseCreate) -> Expense:
    """Create an expense and its splits in a single atomic transaction."""
    # Lock the group so concurrent writes to the same ledger are serialised.
    get_group_or_404(db, payload.group_id, lock=True)
    get_user_or_404(db, payload.paid_by)

    member_ids = get_member_ids(db, payload.group_id)
    if payload.paid_by not in member_ids:
        raise BusinessRuleError(
            f"Payer {payload.paid_by} is not a member of group {payload.group_id}"
        )

    amount_paise = rupees_to_paise(payload.amount)
    shares = calculate_shares(payload, amount_paise, member_ids)

    expense = Expense(
        group_id=payload.group_id,
        paid_by=payload.paid_by,
        amount_paise=amount_paise,
        description=payload.description,
        splits=[
            ExpenseSplit(group_id=payload.group_id, user_id=user_id, share_paise=share)
            for user_id, share in shares.items()
        ],
    )
    db.add(expense)
    commit_or_raise(db)  # expense + all splits are written together, or not at all
    return db.get(Expense, expense.id, populate_existing=True)


def list_group_expenses(db: Session, group_id: int) -> list[Expense]:
    get_group_or_404(db, group_id)
    statement = (
        select(Expense).where(Expense.group_id == group_id).order_by(Expense.created_at, Expense.id)
    )
    return list(db.scalars(statement))
