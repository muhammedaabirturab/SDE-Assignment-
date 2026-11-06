"""Balance engine.

Everything is derived from persisted rows; nothing is cached or hardcoded.

The ledger
----------
Expenses and repayments are both reduced to *ledger entries*
``(debtor, creditor, paise)`` meaning "debtor owes creditor this much":

* every expense split of user U on an expense paid by P (U != P)
  -> ``(U, P, share)``    (the payer's own share is never a debt)
* every repayment where A paid B  -> ``(A, B, -amount)``  (reduces A's debt)

From the ledger we derive two views:

* ``net_positions``     paid - owed per user (positive: is owed, negative: owes)
* ``pairwise_debts``    who owes whom after netting opposite directions and
                        cancelling circular debts (A->B->C->A)
"""

from collections import defaultdict
from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.expense import Expense
from app.models.expense_split import ExpenseSplit
from app.models.settlement import Settlement
from app.models.user import User
from app.schemas.balance import BalanceEntry, BalancesResponse
from app.services.group_service import get_group_or_404

LedgerEntry = tuple[int, int, int]  # (debtor_id, creditor_id, paise)


def net_positions(ledger: Iterable[LedgerEntry]) -> dict[int, int]:
    """Net paise per user: positive = should receive, negative = should pay."""
    net: dict[int, int] = defaultdict(int)
    for debtor, creditor, amount in ledger:
        net[creditor] += amount
        net[debtor] -= amount
    return dict(net)


def pairwise_debts(ledger: Iterable[LedgerEntry]) -> dict[tuple[int, int], int]:
    """Who owes whom, with no duplicate, contradictory or circular entries.

    Returns ``{(debtor, creditor): paise}`` with only strictly positive
    amounts:

    1. opposite directions between two users are netted into one entry;
    2. circular debts (A owes B, B owes C, C owes A) are cancelled, because
       paying them changes nobody's net position. Each user's net position is
       preserved, so a fully settled group ends up with no entries at all.

    Self-debts are ignored. For any two users at most one direction remains.
    """
    # Orient each pair as (low_id, high_id); the value is what low owes high.
    low_owes_high: dict[tuple[int, int], int] = defaultdict(int)
    for debtor, creditor, amount in ledger:
        if debtor == creditor:
            continue
        if debtor < creditor:
            low_owes_high[(debtor, creditor)] += amount
        else:
            low_owes_high[(creditor, debtor)] -= amount

    owes: dict[int, dict[int, int]] = defaultdict(dict)
    for (low, high), amount in low_owes_high.items():
        if amount > 0:
            owes[low][high] = amount
        elif amount < 0:
            owes[high][low] = -amount

    while (cycle := _find_cycle(owes)) is not None:
        edges = list(zip(cycle, cycle[1:] + cycle[:1]))
        reduction = min(owes[debtor][creditor] for debtor, creditor in edges)
        for debtor, creditor in edges:
            owes[debtor][creditor] -= reduction
            if owes[debtor][creditor] == 0:
                del owes[debtor][creditor]

    return {
        (debtor, creditor): amount
        for debtor, creditors in owes.items()
        for creditor, amount in creditors.items()
    }


def _find_cycle(owes: dict[int, dict[int, int]]) -> list[int] | None:
    """Return the users on some debt cycle (depth-first search), or None."""
    state: dict[int, int] = {}  # 1 = on the current path, 2 = fully explored
    for start in sorted(owes):
        if start in state:
            continue
        path = [start]
        stack = [iter(sorted(owes.get(start, {})))]
        state[start] = 1
        while stack:
            for neighbour in stack[-1]:
                if state.get(neighbour) == 1:
                    return path[path.index(neighbour):]
                if neighbour not in state:
                    state[neighbour] = 1
                    path.append(neighbour)
                    stack.append(iter(sorted(owes.get(neighbour, {}))))
                    break
            else:
                state[path.pop()] = 2
                stack.pop()
    return None


def load_ledger(db: Session, group_id: int | None = None) -> list[LedgerEntry]:
    """Read the ledger from the database (one group, or all groups)."""
    debts = (
        select(
            ExpenseSplit.user_id,
            Expense.paid_by,
            func.sum(ExpenseSplit.share_paise),
        )
        .join(Expense, Expense.id == ExpenseSplit.expense_id)
        .where(ExpenseSplit.user_id != Expense.paid_by)
        .group_by(ExpenseSplit.user_id, Expense.paid_by)
    )
    repayments = select(
        Settlement.paid_by, Settlement.paid_to, func.sum(Settlement.amount_paise)
    ).group_by(Settlement.paid_by, Settlement.paid_to)
    if group_id is not None:
        debts = debts.where(Expense.group_id == group_id)
        repayments = repayments.where(Settlement.group_id == group_id)

    ledger = [(debtor, creditor, int(total)) for debtor, creditor, total in db.execute(debts)]
    ledger += [(payer, receiver, -int(total)) for payer, receiver, total in db.execute(repayments)]
    return ledger


def get_net_positions(db: Session, group_id: int) -> dict[int, int]:
    return net_positions(load_ledger(db, group_id))


def get_user_names(db: Session, user_ids: Iterable[int]) -> dict[int, str]:
    ids = set(user_ids)
    if not ids:
        return {}
    return dict(db.execute(select(User.id, User.name).where(User.id.in_(ids))).all())


def get_balances(db: Session, group_id: int | None = None) -> BalancesResponse:
    """Who owes whom, in the response shape required by the assignment."""
    if group_id is not None:
        get_group_or_404(db, group_id)
    debts = pairwise_debts(load_ledger(db, group_id))
    names = get_user_names(db, {user for pair in debts for user in pair})

    balances: dict[str, BalanceEntry] = {}
    for (debtor, creditor), amount in sorted(debts.items()):
        entry = balances.setdefault(names[debtor], BalanceEntry(owes={}))
        entry.owes[names[creditor]] = amount
    return balances
