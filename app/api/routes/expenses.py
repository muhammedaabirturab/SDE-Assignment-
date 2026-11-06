from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.expense import ExpenseCreate, ExpenseOut
from app.services import expense_service

router = APIRouter(tags=["Expenses"])


@router.post(
    "/expenses",
    response_model=ExpenseOut,
    status_code=status.HTTP_201_CREATED,
    summary="Record a shared expense",
)
def create_expense(payload: ExpenseCreate, db: Session = Depends(get_db)):
    """Record an expense and split it.

    By default the amount is split **equally among all current members** of the
    group (the payer included; the payer's own share is not a debt). Leftover
    paise go to the lowest user ids so the shares always add up exactly.

    Optional extras: `participants` (equal split among a subset of members) or
    `splits` (custom amounts that must sum to `amount`).
    """
    return ExpenseOut.from_model(expense_service.create_expense(db, payload))


@router.get(
    "/groups/{group_id}/expenses",
    response_model=list[ExpenseOut],
    summary="List a group's expenses",
)
def list_group_expenses(group_id: int, db: Session = Depends(get_db)):
    return [ExpenseOut.from_model(e) for e in expense_service.list_group_expenses(db, group_id)]
