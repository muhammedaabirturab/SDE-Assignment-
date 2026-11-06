from pydantic import BaseModel, Field

from app.schemas.common import Rupees


class BalanceEntry(BaseModel):
    """Who this person owes, and how much (rupees)."""

    owes: dict[str, Rupees] = Field(examples=[{"Mohit": 400}])


# Response of GET /balances: {"Rahul": {"owes": {"Mohit": 400}}, ...}
# Only people who currently owe someone appear; settled pairs are omitted.
BalancesResponse = dict[str, BalanceEntry]
