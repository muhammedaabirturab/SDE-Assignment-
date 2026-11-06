from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.models.settlement import Settlement
from app.schemas.common import Rupees, RupeesInput


class SettlementCreate(BaseModel):
    """Record that ``paid_by`` really paid ``paid_to`` (e.g. Rahul pays Mohit)."""

    group_id: int = Field(gt=0, examples=[1])
    paid_by: int = Field(gt=0, description="User id of the person who paid.", examples=[2])
    paid_to: int = Field(gt=0, description="User id of the person who received.", examples=[1])
    amount: RupeesInput
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None = None

    @model_validator(mode="after")
    def _no_self_payment(self) -> "SettlementCreate":
        if self.paid_by == self.paid_to:
            raise ValueError("'paid_by' and 'paid_to' must be different users")
        return self


class SettlementOut(BaseModel):
    id: int
    group_id: int
    paid_by: str
    paid_by_id: int
    paid_to: str
    paid_to_id: int
    amount: Rupees
    note: str | None
    created_at: datetime

    @classmethod
    def from_model(cls, settlement: Settlement) -> "SettlementOut":
        return cls(
            id=settlement.id,
            group_id=settlement.group_id,
            paid_by=settlement.payer.name,
            paid_by_id=settlement.paid_by,
            paid_to=settlement.receiver.name,
            paid_to_id=settlement.paid_to,
            amount=settlement.amount_paise,
            note=settlement.note,
            created_at=settlement.created_at,
        )


class NetBalanceOut(BaseModel):
    user_id: int
    name: str
    net_balance: Rupees = Field(
        description="Paid minus owed (after repayments). Positive: is owed money; "
        "negative: owes money."
    )


class SuggestedPayment(BaseModel):
    from_user_id: int
    from_user: str
    to_user_id: int
    to_user: str
    amount: Rupees


class SettlementPlanOut(BaseModel):
    group_id: int
    net_balances: list[NetBalanceOut]
    payments: list[SuggestedPayment]
    transaction_count: int = Field(description="Payments in the simplified plan.")
    pairwise_transaction_count: int = Field(
        description="Payments needed if every outstanding pairwise debt were paid separately."
    )
