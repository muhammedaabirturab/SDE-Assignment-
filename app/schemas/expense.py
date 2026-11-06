from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.models.expense import Expense
from app.schemas.common import Rupees, RupeesInput


class SplitInput(BaseModel):
    user_id: int = Field(gt=0)
    amount: RupeesInput


class ExpenseCreate(BaseModel):
    """Create an expense. Without ``splits`` / ``participants`` it is split
    equally among *all current members* of the group (the default)."""

    group_id: int = Field(gt=0, examples=[1])
    paid_by: int = Field(gt=0, examples=[1])
    amount: RupeesInput
    description: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ] = Field(examples=["Dinner"])
    participants: list[int] | None = Field(
        default=None,
        description="Optional: split equally among only these group members.",
        min_length=1,
    )
    splits: list[SplitInput] | None = Field(
        default=None,
        description="Optional: custom (unequal) split; must add up to `amount`.",
        min_length=1,
    )

    @model_validator(mode="after")
    def _check_split_options(self) -> "ExpenseCreate":
        if self.participants is not None and self.splits is not None:
            raise ValueError("Provide either 'participants' or 'splits', not both")
        if self.participants is not None:
            if len(set(self.participants)) != len(self.participants):
                raise ValueError("'participants' must not contain duplicates")
            if any(user_id <= 0 for user_id in self.participants):
                raise ValueError("'participants' must contain positive user ids")
        if self.splits is not None:
            ids = [split.user_id for split in self.splits]
            if len(set(ids)) != len(ids):
                raise ValueError("'splits' must not contain the same user twice")
        return self


class SplitOut(BaseModel):
    user_id: int
    name: str
    amount: Rupees


class ExpenseOut(BaseModel):
    id: int
    group_id: int
    description: str
    amount: Rupees
    paid_by: str
    paid_by_id: int
    created_at: datetime
    splits: list[SplitOut]

    @classmethod
    def from_model(cls, expense: Expense) -> "ExpenseOut":
        return cls(
            id=expense.id,
            group_id=expense.group_id,
            description=expense.description,
            amount=expense.amount_paise,
            paid_by=expense.payer.name,
            paid_by_id=expense.paid_by,
            created_at=expense.created_at,
            splits=[
                SplitOut(user_id=s.user_id, name=s.user.name, amount=s.share_paise)
                for s in expense.splits
            ],
        )
