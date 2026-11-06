"""Smart settlement suggestions and recording of real repayments."""

import heapq

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError
from app.models.settlement import Settlement
from app.schemas.settlement import (
    NetBalanceOut,
    SettlementCreate,
    SettlementPlanOut,
    SuggestedPayment,
)
from app.services import balance_service
from app.services.group_service import get_group_or_404, get_member_ids
from app.services.user_service import get_user_or_404
from app.utils.db import commit_or_raise
from app.utils.money import paise_to_json_number, rupees_to_paise

Payment = tuple[int, int, int]  # (from_user_id, to_user_id, paise)


def compute_settlement_plan(net: dict[int, int]) -> list[Payment]:
    """Greedy debt simplification.

    ``net`` maps user id -> net paise (positive: should receive, negative:
    should pay). Repeatedly match the largest debtor with the largest creditor
    and transfer ``min(debt, credit)``; at least one of the two is settled by
    every payment, so a group of n people with non-zero balances needs at most
    n - 1 payments. Ties are broken by user id, so the output is deterministic.

    This is a practical heuristic: it is fast (O(n log n)) and never worse
    than n - 1 payments, but it does not guarantee the global minimum number
    of payments (that problem is NP-hard in general).
    """
    if sum(net.values()) != 0:
        raise ValueError("Net balances must add up to zero")

    # heapq is a min-heap, so amounts are negated to pop the largest first.
    creditors = [(-amount, user) for user, amount in net.items() if amount > 0]
    debtors = [(amount, user) for user, amount in net.items() if amount < 0]
    heapq.heapify(creditors)
    heapq.heapify(debtors)

    payments: list[Payment] = []
    while creditors and debtors:
        neg_credit, creditor = heapq.heappop(creditors)
        neg_debt, debtor = heapq.heappop(debtors)
        credit, debt = -neg_credit, -neg_debt
        transfer = min(credit, debt)
        payments.append((debtor, creditor, transfer))
        if credit > transfer:
            heapq.heappush(creditors, (-(credit - transfer), creditor))
        if debt > transfer:
            heapq.heappush(debtors, (-(debt - transfer), debtor))
    return payments


def get_settlement_plan(db: Session, group_id: int) -> SettlementPlanOut:
    get_group_or_404(db, group_id)
    ledger = balance_service.load_ledger(db, group_id)
    net = balance_service.net_positions(ledger)
    payments = compute_settlement_plan(net)
    pairwise = balance_service.pairwise_debts(ledger)

    member_ids = get_member_ids(db, group_id)
    names = balance_service.get_user_names(db, member_ids | set(net))
    return SettlementPlanOut(
        group_id=group_id,
        net_balances=[
            NetBalanceOut(user_id=user, name=names[user], net_balance=net.get(user, 0))
            for user in sorted(member_ids)
        ],
        payments=[
            SuggestedPayment(
                from_user_id=debtor,
                from_user=names[debtor],
                to_user_id=creditor,
                to_user=names[creditor],
                amount=amount,
            )
            for debtor, creditor, amount in payments
        ],
        transaction_count=len(payments),
        pairwise_transaction_count=len(pairwise),
    )


def record_settlement(db: Session, payload: SettlementCreate) -> Settlement:
    """Persist a real repayment after checking it cannot over-settle anything.

    A repayment is valid when the payer currently owes money overall (net < 0),
    the receiver is currently owed money overall (net > 0) and the amount does
    not exceed either of those. Checking net positions (rather than a single
    pairwise debt) also lets members pay exactly what the smart settlement
    plan suggests.
    """
    get_group_or_404(db, payload.group_id, lock=True)
    get_user_or_404(db, payload.paid_by)
    get_user_or_404(db, payload.paid_to)

    member_ids = get_member_ids(db, payload.group_id)
    outsiders = sorted({payload.paid_by, payload.paid_to} - member_ids)
    if outsiders:
        raise BusinessRuleError(f"Users {outsiders} are not members of group {payload.group_id}")

    amount_paise = rupees_to_paise(payload.amount)
    net = balance_service.get_net_positions(db, payload.group_id)
    payer_owes = max(-net.get(payload.paid_by, 0), 0)
    receiver_is_owed = max(net.get(payload.paid_to, 0), 0)
    allowed = min(payer_owes, receiver_is_owed)
    if amount_paise > allowed:
        raise BusinessRuleError(
            "Settlement exceeds what can be settled between these users "
            f"(payer owes {paise_to_json_number(payer_owes)}, "
            f"receiver is owed {paise_to_json_number(receiver_is_owed)})"
        )

    settlement = Settlement(
        group_id=payload.group_id,
        paid_by=payload.paid_by,
        paid_to=payload.paid_to,
        amount_paise=amount_paise,
        note=payload.note or None,
    )
    db.add(settlement)
    commit_or_raise(db)
    return db.get(Settlement, settlement.id, populate_existing=True)


def list_settlements(db: Session, group_id: int) -> list[Settlement]:
    get_group_or_404(db, group_id)
    statement = (
        select(Settlement)
        .where(Settlement.group_id == group_id)
        .order_by(Settlement.created_at, Settlement.id)
    )
    return list(db.scalars(statement))
