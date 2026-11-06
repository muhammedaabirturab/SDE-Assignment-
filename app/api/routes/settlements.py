from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.settlement import SettlementCreate, SettlementOut, SettlementPlanOut
from app.services import settlement_service

router = APIRouter(tags=["Settlements"])


@router.get(
    "/groups/{group_id}/settlements/suggestions",
    response_model=SettlementPlanOut,
    summary="Smart settlement plan (fewest payments)",
)
def get_settlement_plan(group_id: int, db: Session = Depends(get_db)):
    """Simplify the group's debts with a greedy algorithm.

    Returns each member's net balance and a short list of payments that, if all
    made, bring every net balance to zero. This only *suggests*; nothing is
    saved until a payment is recorded with `POST /settlements`.
    """
    return settlement_service.get_settlement_plan(db, group_id)


@router.post(
    "/settlements",
    response_model=SettlementOut,
    status_code=status.HTTP_201_CREATED,
    summary="Record a repayment",
)
def record_settlement(payload: SettlementCreate, db: Session = Depends(get_db)):
    """Record that one member actually paid another (e.g. Rahul pays Mohit 400).

    Rejected (422) if the payer does not owe money, the receiver is not owed
    money, or the amount is more than either of them can settle.
    """
    return SettlementOut.from_model(settlement_service.record_settlement(db, payload))


@router.get(
    "/groups/{group_id}/settlements",
    response_model=list[SettlementOut],
    summary="Repayment history of a group",
)
def list_settlements(group_id: int, db: Session = Depends(get_db)):
    return [SettlementOut.from_model(s) for s in settlement_service.list_settlements(db, group_id)]
