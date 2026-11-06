from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.balance import BalancesResponse
from app.services import balance_service

router = APIRouter(tags=["Balances"])


@router.get("/balances", response_model=BalancesResponse, summary="Who owes whom")
def get_balances(
    group_id: int | None = Query(
        default=None, gt=0, description="Limit to one group; omit to combine all groups."
    ),
    db: Session = Depends(get_db),
):
    """Pairwise balances, e.g. `{"Rahul": {"owes": {"Mohit": 400}}}`.

    Amounts are rupees. Opposite debts between two people are netted into a
    single entry, self-debts never appear and settled (zero) pairs are omitted.
    """
    return balance_service.get_balances(db, group_id)
